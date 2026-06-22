from datetime import datetime, timezone
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.identity.domain.entities import AuditLog
from controlbox.modules.wordpress.application.commands import (
    ChangePhpVersionCommand,
    CloneWordPressSiteCommand,
    CreateStagingCommand,
    CreateWordPressBackupCommand,
    CreateWordPressSiteCommand,
    DeleteWordPressSiteCommand,
    RestoreWordPressBackupCommand,
    RestartWordPressSiteCommand,
    ToggleMaintenanceCommand,
)
from controlbox.modules.wordpress.application.queries import WordPressSiteResponse
from controlbox.modules.wordpress.domain.entities import (
    DEFAULT_PHP_VERSION,
    WORDPRESS_VERSION,
    WordPressBackup,
    WordPressBackupStatus,
    WordPressSite,
    WordPressSslStatus,
    WordPressStatus,
)
from controlbox.modules.wordpress.domain.services import WordPressDomainService
from controlbox.modules.wordpress.infrastructure.provisioner import WordPressProvisioner
from controlbox.modules.wordpress.workers.tasks import (
    provision_wordpress_site,
    restore_wordpress_backup,
    run_wordpress_backup,
)
from controlbox.shared.application.cqrs import CommandHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ForbiddenError, NotFoundError, ConflictError, ValidationError


def _to_response(site: WordPressSite) -> WordPressSiteResponse:
    return WordPressSiteResponse(
        id=site.id,
        tenant_id=site.tenant_id,
        name=site.name,
        domain=site.domain,
        status=site.status.value,
        php_version=site.php_version,
        wordpress_version=site.wordpress_version,
        url=site.url,
        admin_user=site.admin_user,
        admin_email=site.admin_email,
        ssl_enabled=site.ssl_enabled,
        ssl_status=site.ssl_status.value,
        maintenance_mode=site.maintenance_mode,
        disk_used_mb=site.disk_used_mb,
        db_size_mb=site.db_size_mb,
        is_staging=site.is_staging,
        parent_site_id=site.parent_site_id,
        error_message=site.error_message,
        task_id=site.task_id,
        created_at=site.created_at,
        updated_at=site.updated_at,
    )


class CreateWordPressSiteHandler(CommandHandler[CreateWordPressSiteCommand, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = WordPressProvisioner(settings)

    async def handle(self, command: CreateWordPressSiteCommand) -> WordPressSiteResponse:
        if not command.tenant_id:
            raise ForbiddenError("Tenant context required")

        domain_service = WordPressDomainService(self._uow.wordpress_sites)
        domain = domain_service.validate_domain(command.domain)
        php_version = domain_service.validate_php_version(command.php_version or DEFAULT_PHP_VERSION)
        admin_user = domain_service.validate_admin_user(command.admin_user)
        await domain_service.ensure_domain_available(domain, command.tenant_id)

        existing_website = await self._uow.websites.get_by_domain(domain, command.tenant_id)
        if existing_website:
            raise ConflictError(f"Domain '{domain}' is already used by a website")

        site = WordPressSite(
            tenant_id=command.tenant_id,
            name=command.name.strip(),
            domain=domain,
            status=WordPressStatus.PENDING,
            php_version=php_version,
            wordpress_version=WORDPRESS_VERSION,
            url=domain_service.build_site_url(domain, command.ssl_enabled),
            admin_user=admin_user,
            admin_email=command.admin_email,
            ssl_enabled=command.ssl_enabled,
            ssl_status=WordPressSslStatus.PENDING if command.ssl_enabled else WordPressSslStatus.ACTIVE,
        )
        nginx_name, php_name = domain_service.build_container_names(site.id)
        site.site_path = str(self._provisioner.get_site_path(command.tenant_id, site.id))
        site.nginx_container_name = nginx_name
        site.php_container_name = php_name

        await self._uow.wordpress_sites.add(site)

        try:
            task = provision_wordpress_site.delay(str(site.id), command.admin_password)
        except Exception as exc:
            raise ValidationError(
                "Could not queue WordPress deployment. Verify Redis and the worker "
                f"(controlbox-worker) are running, then run: controlbox repair. ({exc})"
            ) from exc

        site.mark_provisioning(task.id)

        await self._uow.wordpress_sites.save(site)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="wordpress.created",
                resource_type="wordpress_site",
                resource_id=str(site.id),
                metadata={"domain": domain, "php_version": php_version},
            )
        )
        await self._uow.commit()
        return _to_response(site)


class DeleteWordPressSiteHandler(CommandHandler[DeleteWordPressSiteCommand, None]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = WordPressProvisioner(settings)

    async def handle(self, command: DeleteWordPressSiteCommand) -> None:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("WordPress site not found")
        site.status = WordPressStatus.DELETING
        await self._uow.wordpress_sites.save(site)
        try:
            await self._provisioner.destroy(site)
        except Exception:
            pass
        await self._uow.wordpress_sites.delete(site.id)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="wordpress.deleted",
                resource_type="wordpress_site",
                resource_id=str(site.id),
            )
        )
        await self._uow.commit()


class RestartWordPressSiteHandler(CommandHandler[RestartWordPressSiteCommand, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = WordPressProvisioner(settings)

    async def handle(self, command: RestartWordPressSiteCommand) -> WordPressSiteResponse:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("WordPress site not found")
        await self._provisioner.restart(site)
        site.status = WordPressStatus.RUNNING
        await self._uow.wordpress_sites.save(site)
        await self._uow.commit()
        return _to_response(site)


class ChangePhpVersionHandler(CommandHandler[ChangePhpVersionCommand, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = WordPressProvisioner(settings)

    async def handle(self, command: ChangePhpVersionCommand) -> WordPressSiteResponse:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("WordPress site not found")
        version = WordPressDomainService(self._uow.wordpress_sites).validate_php_version(command.php_version)
        await self._provisioner.change_php_version(site, version)
        site.php_version = version
        await self._uow.wordpress_sites.save(site)
        await self._uow.commit()
        return _to_response(site)


class ToggleMaintenanceHandler(CommandHandler[ToggleMaintenanceCommand, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = WordPressProvisioner(settings)

    async def handle(self, command: ToggleMaintenanceCommand) -> WordPressSiteResponse:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("WordPress site not found")
        await self._provisioner.set_maintenance(site, command.enabled)
        site.set_maintenance(command.enabled)
        await self._uow.wordpress_sites.save(site)
        await self._uow.commit()
        return _to_response(site)


class CloneWordPressSiteHandler(CommandHandler[CloneWordPressSiteCommand, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = WordPressProvisioner(settings)

    async def handle(self, command: CloneWordPressSiteCommand) -> WordPressSiteResponse:
        source = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if source is None:
            raise NotFoundError("WordPress site not found")

        domain_service = WordPressDomainService(self._uow.wordpress_sites)
        domain = domain_service.validate_domain(command.new_domain)
        await domain_service.ensure_domain_available(domain, command.tenant_id)

        clone = WordPressSite(
            tenant_id=command.tenant_id,
            name=command.new_name.strip(),
            domain=domain,
            status=WordPressStatus.CLONING,
            php_version=source.php_version,
            wordpress_version=source.wordpress_version,
            url=domain_service.build_site_url(domain, source.ssl_enabled),
            admin_user=source.admin_user,
            admin_email=source.admin_email,
            ssl_enabled=source.ssl_enabled,
            ssl_status=source.ssl_status,
            parent_site_id=source.id,
            settings=dict(source.settings),
        )
        nginx_name, php_name = domain_service.build_container_names(clone.id)
        clone.nginx_container_name = nginx_name
        clone.php_container_name = php_name
        clone.site_path = str(self._provisioner.get_site_path(command.tenant_id, clone.id))

        await self._uow.wordpress_sites.add(clone)
        await self._provisioner.clone_site_files(source, self._provisioner.get_site_path(command.tenant_id, clone.id))

        db_password = self._provisioner.decrypt_db_password(source.settings["db_password_enc"])
        await self._provisioner.deploy(
            clone, db_password, source.settings["db_name"], source.settings["db_user"], db_password,
            nginx_name, php_name,
        )
        clone.mark_running(nginx_name, php_name)
        clone.disk_used_mb = self._provisioner.measure_disk_mb(clone)
        await self._uow.wordpress_sites.save(clone)
        await self._uow.commit()
        return _to_response(clone)


class CreateStagingHandler(CommandHandler[CreateStagingCommand, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, command: CreateStagingCommand) -> WordPressSiteResponse:
        source = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if source is None:
            raise NotFoundError("WordPress site not found")
        staging_domain = f"staging-{source.domain}"
        handler = CloneWordPressSiteHandler(self._uow, self._settings)
        result = await handler.handle(
            CloneWordPressSiteCommand(
                site_id=command.site_id,
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                new_domain=staging_domain,
                new_name=f"{source.name} (Staging)",
            )
        )
        staging = await self._uow.wordpress_sites.get_by_id_and_tenant(result.id, command.tenant_id)
        if staging:
            staging.is_staging = True
            staging.parent_site_id = source.id
            await self._uow.wordpress_sites.save(staging)
            await self._uow.commit()
            return _to_response(staging)
        return result


class CreateWordPressBackupHandler(CommandHandler[CreateWordPressBackupCommand, UUID]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: CreateWordPressBackupCommand) -> UUID:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("WordPress site not found")
        name = command.name or f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        backup = WordPressBackup(
            site_id=site.id,
            tenant_id=command.tenant_id,
            name=name,
            status=WordPressBackupStatus.PENDING,
        )
        await self._uow.wordpress_backups.add(backup)
        await self._uow.commit()
        run_wordpress_backup.delay(str(backup.id), str(site.id), str(command.tenant_id))
        return backup.id


class RestoreWordPressBackupHandler(CommandHandler[RestoreWordPressBackupCommand, None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: RestoreWordPressBackupCommand) -> None:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        backup = await self._uow.wordpress_backups.get_by_id_and_tenant(command.backup_id, command.tenant_id)
        if site is None or backup is None or backup.site_id != site.id:
            raise NotFoundError("Backup not found")
        restore_wordpress_backup.delay(str(backup.id), str(site.id), str(command.tenant_id))
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="wordpress.restore",
                resource_type="wordpress_backup",
                resource_id=str(backup.id),
            )
        )
        await self._uow.commit()
