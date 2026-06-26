from datetime import datetime, timezone
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.identity.domain.entities import AuditLog
from controlbox.modules.joomla.application.responses import to_joomla_site_response
from controlbox.modules.joomla.application.commands import (
    ChangePhpVersionCommand,
    ChangeJoomlaAdminPasswordCommand,
    CloneJoomlaSiteCommand,
    CreateStagingCommand,
    CreateJoomlaBackupCommand,
    CreateJoomlaSiteCommand,
    DeleteJoomlaSiteCommand,
    RestoreJoomlaBackupCommand,
    RestartJoomlaSiteCommand,
    ToggleMaintenanceCommand,
)
from controlbox.modules.joomla.application.queries import JoomlaSiteResponse
from controlbox.modules.joomla.domain.entities import (
    DEFAULT_PHP_VERSION,
    JOOMLA_VERSION,
    JoomlaBackup,
    JoomlaBackupStatus,
    JoomlaSite,
    JoomlaSslStatus,
    JoomlaStatus,
)
from controlbox.modules.databases.domain.services import DatabaseDomainService
from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.modules.joomla.domain.services import JoomlaDomainService
from controlbox.modules.joomla.infrastructure.provisioner import JoomlaProvisioner
from controlbox.modules.joomla.workers.tasks import (
    provision_joomla_site,
    restore_joomla_backup,
    run_joomla_backup,
)
from controlbox.shared.application.cqrs import CommandHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ForbiddenError, NotFoundError, ConflictError, ValidationError
from controlbox.shared.infrastructure.resource_isolation import set_owner_in_settings


def _to_response(site: JoomlaSite, settings: Settings | None = None) -> JoomlaSiteResponse:
    return to_joomla_site_response(site, settings)


class CreateJoomlaSiteHandler(CommandHandler[CreateJoomlaSiteCommand, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: CreateJoomlaSiteCommand) -> JoomlaSiteResponse:
        if not command.tenant_id:
            raise ForbiddenError("Tenant context required")

        domain_service = JoomlaDomainService(
            self._uow.joomla_sites,
            runtime_catalog=RuntimeCatalogManager(self._settings),
        )
        domain = domain_service.validate_domain(command.domain)
        php_version = domain_service.validate_php_version(command.php_version or DEFAULT_PHP_VERSION)
        admin_user = domain_service.validate_admin_user(command.admin_user)
        await domain_service.ensure_domain_available(domain, command.tenant_id)

        existing_website = await self._uow.websites.get_by_domain(domain, command.tenant_id)
        if existing_website:
            raise ConflictError(f"Domain '{domain}' is already used by a website")

        site = JoomlaSite(
            tenant_id=command.tenant_id,
            owner_user_id=command.user_id,
            name=command.name.strip(),
            domain=domain,
            status=JoomlaStatus.PENDING,
            php_version=php_version,
            joomla_version=JOOMLA_VERSION,
            url=domain_service.build_site_url(domain, command.ssl_enabled),
            admin_user=admin_user,
            admin_email=command.admin_email,
            ssl_enabled=command.ssl_enabled,
            ssl_status=JoomlaSslStatus.PENDING if command.ssl_enabled else JoomlaSslStatus.ACTIVE,
            settings=set_owner_in_settings({}, command.user_id),
        )
        if command.create_ftp_account:
            site.settings["create_ftp_account"] = True
        nginx_name, php_name = domain_service.build_container_names(site.id)
        site.site_path = str(self._provisioner.get_site_path(command.tenant_id, site.id))
        site.nginx_container_name = nginx_name
        site.php_container_name = php_name

        db_domain = DatabaseDomainService(self._uow.managed_databases)
        if command.db_name:
            site.settings["requested_db_name"] = db_domain.validate_name(command.db_name)
            await db_domain.ensure_name_available(site.settings["requested_db_name"], command.tenant_id)
        if command.db_user:
            site.settings["requested_db_user"] = db_domain.validate_username(command.db_user)
        if command.db_password:
            if len(command.db_password) < 8:
                raise ValidationError("Database password must be at least 8 characters")
            site.settings["requested_db_password"] = command.db_password

        await self._uow.joomla_sites.add(site)

        try:
            task = provision_joomla_site.delay(str(site.id), command.admin_password)
        except Exception as exc:
            raise ValidationError(
                "Could not queue Joomla deployment. Verify Redis and the worker "
                f"(controlbox-worker) are running. ({exc})"
            ) from exc

        site.mark_provisioning(task.id)

        await self._uow.joomla_sites.save(site)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="joomla.created",
                resource_type="joomla_site",
                resource_id=str(site.id),
                metadata={"domain": domain, "php_version": php_version},
            )
        )
        await self._uow.commit()
        return _to_response(site, self._settings)


class DeleteJoomlaSiteHandler(CommandHandler[DeleteJoomlaSiteCommand, None]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: DeleteJoomlaSiteCommand) -> None:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        site.status = JoomlaStatus.DELETING
        await self._uow.joomla_sites.save(site)
        try:
            await self._provisioner.destroy(site)
        except Exception:
            pass
        await self._uow.joomla_sites.delete(site.id)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="joomla.deleted",
                resource_type="joomla_site",
                resource_id=str(site.id),
            )
        )
        await self._uow.commit()


class RestartJoomlaSiteHandler(CommandHandler[RestartJoomlaSiteCommand, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: RestartJoomlaSiteCommand) -> JoomlaSiteResponse:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        await self._provisioner.restart(site)
        site.status = JoomlaStatus.RUNNING
        await self._uow.joomla_sites.save(site)
        await self._uow.commit()
        return _to_response(site, self._settings)


class ChangePhpVersionHandler(CommandHandler[ChangePhpVersionCommand, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: ChangePhpVersionCommand) -> JoomlaSiteResponse:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        version = JoomlaDomainService(
            self._uow.joomla_sites,
            runtime_catalog=RuntimeCatalogManager(self._settings),
        ).validate_php_version(command.php_version)
        await self._provisioner.change_php_version(site, version)
        site.php_version = version
        await self._uow.joomla_sites.save(site)
        await self._uow.commit()
        return _to_response(site, self._settings)


class ToggleMaintenanceHandler(CommandHandler[ToggleMaintenanceCommand, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: ToggleMaintenanceCommand) -> JoomlaSiteResponse:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        await self._provisioner.set_maintenance(site, command.enabled)
        site.set_maintenance(command.enabled)
        await self._uow.joomla_sites.save(site)
        await self._uow.commit()
        return _to_response(site, self._settings)


class ChangeJoomlaAdminPasswordHandler(
    CommandHandler[ChangeJoomlaAdminPasswordCommand, JoomlaSiteResponse]
):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: ChangeJoomlaAdminPasswordCommand) -> JoomlaSiteResponse:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        if site.status != JoomlaStatus.RUNNING:
            raise ValidationError("El sitio debe estar en ejecución para cambiar la contraseña de Joomla")
        await self._provisioner.change_admin_password(site, command.new_password)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="joomla.admin_password_changed",
                resource_type="joomla",
                resource_id=str(site.id),
                metadata={"domain": site.domain},
            )
        )
        await self._uow.commit()
        return _to_response(site, self._settings)


class CloneJoomlaSiteHandler(CommandHandler[CloneJoomlaSiteCommand, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioner = JoomlaProvisioner(settings)

    async def handle(self, command: CloneJoomlaSiteCommand) -> JoomlaSiteResponse:
        source = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if source is None:
            raise NotFoundError("Joomla site not found")

        domain_service = JoomlaDomainService(
            self._uow.joomla_sites,
            runtime_catalog=RuntimeCatalogManager(self._settings),
        )
        domain = domain_service.validate_domain(command.new_domain)
        await domain_service.ensure_domain_available(domain, command.tenant_id)

        clone = JoomlaSite(
            tenant_id=command.tenant_id,
            owner_user_id=command.user_id,
            name=command.new_name.strip(),
            domain=domain,
            status=JoomlaStatus.CLONING,
            php_version=source.php_version,
            joomla_version=source.joomla_version,
            url=domain_service.build_site_url(domain, source.ssl_enabled),
            admin_user=source.admin_user,
            admin_email=source.admin_email,
            ssl_enabled=source.ssl_enabled,
            ssl_status=source.ssl_status,
            parent_site_id=source.id,
            settings=set_owner_in_settings(dict(source.settings), command.user_id),
        )
        nginx_name, php_name = domain_service.build_container_names(clone.id)
        clone.nginx_container_name = nginx_name
        clone.php_container_name = php_name
        clone.site_path = str(self._provisioner.get_site_path(command.tenant_id, clone.id))

        await self._uow.joomla_sites.add(clone)
        await self._provisioner.clone_site_files(source, self._provisioner.get_site_path(command.tenant_id, clone.id))

        db_password = self._provisioner.decrypt_db_password(source.settings["db_password_enc"])
        await self._provisioner.deploy(
            clone, db_password, source.settings["db_name"], source.settings["db_user"], db_password,
            nginx_name, php_name,
        )
        clone.mark_running(nginx_name, php_name)
        clone.disk_used_mb = self._provisioner.measure_disk_mb(clone)
        await self._uow.joomla_sites.save(clone)
        await self._uow.commit()
        return _to_response(clone, self._settings)


class CreateStagingHandler(CommandHandler[CreateStagingCommand, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, command: CreateStagingCommand) -> JoomlaSiteResponse:
        source = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if source is None:
            raise NotFoundError("Joomla site not found")
        staging_domain = f"staging-{source.domain}"
        handler = CloneJoomlaSiteHandler(self._uow, self._settings)
        result = await handler.handle(
            CloneJoomlaSiteCommand(
                site_id=command.site_id,
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                new_domain=staging_domain,
                new_name=f"{source.name} (Staging)",
            )
        )
        staging = await self._uow.joomla_sites.get_by_id_and_tenant(result.id, command.tenant_id)
        if staging:
            staging.is_staging = True
            staging.parent_site_id = source.id
            await self._uow.joomla_sites.save(staging)
            await self._uow.commit()
            return _to_response(staging, self._settings)
        return result


class CreateJoomlaBackupHandler(CommandHandler[CreateJoomlaBackupCommand, UUID]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: CreateJoomlaBackupCommand) -> UUID:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        name = command.name or f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        backup = JoomlaBackup(
            site_id=site.id,
            tenant_id=command.tenant_id,
            name=name,
            status=JoomlaBackupStatus.PENDING,
        )
        await self._uow.joomla_backups.add(backup)
        await self._uow.commit()
        run_joomla_backup.delay(str(backup.id), str(site.id), str(command.tenant_id))
        return backup.id


class RestoreJoomlaBackupHandler(CommandHandler[RestoreJoomlaBackupCommand, None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: RestoreJoomlaBackupCommand) -> None:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(command.site_id, command.tenant_id)
        backup = await self._uow.joomla_backups.get_by_id_and_tenant(command.backup_id, command.tenant_id)
        if site is None or backup is None or backup.site_id != site.id:
            raise NotFoundError("Backup not found")
        restore_joomla_backup.delay(str(backup.id), str(site.id), str(command.tenant_id))
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="joomla.restore",
                resource_type="joomla_backup",
                resource_id=str(backup.id),
            )
        )
        await self._uow.commit()
