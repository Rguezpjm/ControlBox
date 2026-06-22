import logging
from datetime import timedelta
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.identity.domain.entities import AuditLog
from controlbox.modules.staging_sites.application.commands import (
    BlockStagingAccessCommand,
    CreateStagingSiteCommand,
    DeleteStagingSiteCommand,
    RestartStagingSiteCommand,
    SyncStagingCommand,
    UpdateStagingSecurityCommand,
)
from controlbox.modules.staging_sites.application.queries import (
    GetStagingSiteQuery,
    ListStagingSitesQuery,
    StagingSiteResponse,
)
from controlbox.modules.staging_sites.domain.entities import (
    StagingDomainMode,
    StagingSite,
    StagingSourceType,
    StagingStackType,
    StagingStatus,
    SyncDirection,
    SyncType,
)
from controlbox.modules.staging_sites.domain.services import StagingDomainService
from controlbox.modules.staging_sites.infrastructure.provisioner import StagingProvisioner
from controlbox.shared.application.cqrs import CommandHandler, QueryHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError, ValidationError, utc_now

logger = logging.getLogger("controlbox.staging")


def _to_response(staging: StagingSite) -> StagingSiteResponse:
    security = staging.settings.get("security", {})
    sanitized = {
        "password_protection": {
            "enabled": security.get("password_protection", {}).get("enabled", False),
            "username": security.get("password_protection", {}).get("username", "staging"),
        },
        "ip_restriction": {
            "enabled": security.get("ip_restriction", {}).get("enabled", False),
            "allowed_ips": security.get("ip_restriction", {}).get("allowed_ips", []),
        },
        "temp_access": {
            "enabled": security.get("temp_access", {}).get("enabled", False),
            "expires_at": security.get("temp_access", {}).get("expires_at"),
        },
    }
    return StagingSiteResponse(
        id=staging.id,
        tenant_id=staging.tenant_id,
        source_type=staging.source_type.value,
        source_id=staging.source_id,
        source_domain=staging.source_domain,
        name=staging.name,
        domain=staging.domain,
        domain_mode=staging.domain_mode.value,
        stack_type=staging.stack_type.value,
        runtime_version=staging.runtime_version,
        status=staging.status.value,
        ssl_enabled=staging.ssl_enabled,
        ssl_status=staging.ssl_status.value,
        container_name=staging.container_name,
        nginx_container_name=staging.nginx_container_name,
        php_container_name=staging.php_container_name,
        site_path=staging.site_path,
        traefik_router=staging.traefik_router,
        public_access_blocked=staging.public_access_blocked,
        last_sync_at=staging.last_sync_at,
        last_sync_type=staging.last_sync_type,
        last_sync_direction=staging.last_sync_direction,
        cpu_usage_percent=staging.cpu_usage_percent,
        memory_used_mb=staging.memory_used_mb,
        disk_used_mb=staging.disk_used_mb,
        security=sanitized,
        error_message=staging.error_message,
        task_id=staging.task_id,
        created_at=staging.created_at,
        updated_at=staging.updated_at,
    )


class CreateStagingSiteHandler(CommandHandler[CreateStagingSiteCommand, StagingSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, command: CreateStagingSiteCommand) -> StagingSiteResponse:
        source_type = StagingSourceType(command.source_type)
        domain_mode = StagingDomainMode(command.domain_mode)
        domain_service = StagingDomainService(self._uow.staging_sites)

        await domain_service.ensure_source_available(source_type, command.source_id, command.tenant_id)
        source_domain = await domain_service.get_source_domain(
            self._uow, source_type, command.source_id, command.tenant_id
        )
        staging_domain = domain_service.build_staging_domain(source_domain, domain_mode)
        staging_domain = domain_service.validate_domain(staging_domain)
        await domain_service.ensure_domain_available(staging_domain, command.tenant_id)

        stack_type = StagingStackType.WORDPRESS
        runtime_version = "8.3"
        source_name = source_domain

        if source_type == StagingSourceType.WEBSITE:
            website = await self._uow.websites.get_by_id_and_tenant(command.source_id, command.tenant_id)
            if website is None:
                raise NotFoundError("Source website not found")
            stack_type = StagingStackType(domain_service.resolve_stack_from_website_runtime(website.runtime.value))
            runtime_version = website.runtime_version
            source_name = website.name
        else:
            wp = await self._uow.wordpress_sites.get_by_id_and_tenant(command.source_id, command.tenant_id)
            if wp is None:
                raise NotFoundError("Source WordPress site not found")
            runtime_version = wp.php_version
            source_name = wp.name

        name = command.name.strip() or f"{source_name} (Staging)"

        staging = StagingSite(
            tenant_id=command.tenant_id,
            source_type=source_type,
            source_id=command.source_id,
            source_domain=source_domain,
            name=name,
            domain=staging_domain,
            domain_mode=domain_mode,
            stack_type=stack_type,
            runtime_version=runtime_version,
            status=StagingStatus.PENDING,
        )

        container_name, nginx_name, php_name = domain_service.build_container_names(staging.id, stack_type.value)
        staging.container_name = container_name
        staging.nginx_container_name = nginx_name
        staging.php_container_name = php_name
        staging.traefik_router = domain_service.build_traefik_router(staging.id)
        staging.site_path = domain_service.build_site_path(
            self._settings.sites_base_path, command.tenant_id, staging.id
        )

        await self._uow.staging_sites.add(staging)

        from controlbox.modules.staging_sites.workers.tasks import provision_staging_site

        task = provision_staging_site.delay(str(staging.id))
        staging.mark_provisioning(task.id)

        await self._uow.staging_sites.save(staging)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="staging.created",
                resource_type="staging_site",
                resource_id=str(staging.id),
                metadata={"domain": staging.domain, "source_type": source_type.value},
            )
        )
        await self._uow.commit()
        return _to_response(staging)


class SyncStagingHandler(CommandHandler[SyncStagingCommand, StagingSiteResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: SyncStagingCommand) -> StagingSiteResponse:
        staging = await self._uow.staging_sites.get_by_id_and_tenant(command.staging_id, command.tenant_id)
        if staging is None:
            raise NotFoundError("Staging site not found")
        if staging.status not in (StagingStatus.RUNNING, StagingStatus.ERROR):
            raise ValidationError("Staging site is not ready for sync")

        sync_type = SyncType(command.sync_type)
        direction = SyncDirection(command.direction)

        from controlbox.modules.staging_sites.workers.tasks import sync_staging_site

        task = sync_staging_site.delay(str(staging.id), sync_type.value, direction.value)
        staging.mark_syncing(direction, sync_type)
        staging.task_id = task.id
        await self._uow.staging_sites.save(staging)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action=f"staging.sync_{direction.value}",
                resource_type="staging_site",
                resource_id=str(staging.id),
                metadata={"sync_type": sync_type.value},
            )
        )
        await self._uow.commit()
        return _to_response(staging)


class DeleteStagingSiteHandler(CommandHandler[DeleteStagingSiteCommand, None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: DeleteStagingSiteCommand) -> None:
        staging = await self._uow.staging_sites.get_by_id_and_tenant(command.staging_id, command.tenant_id)
        if staging is None:
            raise NotFoundError("Staging site not found")

        from controlbox.modules.staging_sites.workers.tasks import delete_staging_site

        task = delete_staging_site.delay(str(staging.id))
        staging.mark_deleting()
        staging.task_id = task.id
        await self._uow.staging_sites.save(staging)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="staging.deleted",
                resource_type="staging_site",
                resource_id=str(staging.id),
            )
        )
        await self._uow.commit()


class RestartStagingSiteHandler(CommandHandler[RestartStagingSiteCommand, StagingSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = StagingProvisioner(settings)

    async def handle(self, command: RestartStagingSiteCommand) -> StagingSiteResponse:
        staging = await self._uow.staging_sites.get_by_id_and_tenant(command.staging_id, command.tenant_id)
        if staging is None:
            raise NotFoundError("Staging site not found")
        await self._provisioner.restart(staging)
        cpu, mem, disk = await self._provisioner.collect_metrics(staging)
        staging.update_metrics(cpu, mem, disk)
        await self._uow.staging_sites.save(staging)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="staging.restarted",
                resource_type="staging_site",
                resource_id=str(staging.id),
            )
        )
        await self._uow.commit()
        return _to_response(staging)


class BlockStagingAccessHandler(CommandHandler[BlockStagingAccessCommand, StagingSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = StagingProvisioner(settings)

    async def handle(self, command: BlockStagingAccessCommand) -> StagingSiteResponse:
        staging = await self._uow.staging_sites.get_by_id_and_tenant(command.staging_id, command.tenant_id)
        if staging is None:
            raise NotFoundError("Staging site not found")
        staging.set_public_blocked(command.blocked)
        if staging.stack_type == StagingStackType.WORDPRESS and staging.settings.get("db_name"):
            db_password = self._provisioner._crypto.decrypt(staging.settings["db_password_enc"])
            await self._provisioner.deploy_wordpress(
                staging,
                staging.settings["db_name"],
                staging.settings["db_user"],
                db_password,
            )
        else:
            await self._provisioner.deploy_website(staging)
        await self._uow.staging_sites.save(staging)
        await self._uow.commit()
        return _to_response(staging)


class UpdateStagingSecurityHandler(CommandHandler[UpdateStagingSecurityCommand, StagingSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = StagingProvisioner(settings)

    async def handle(self, command: UpdateStagingSecurityCommand) -> StagingSiteResponse:
        staging = await self._uow.staging_sites.get_by_id_and_tenant(command.staging_id, command.tenant_id)
        if staging is None:
            raise NotFoundError("Staging site not found")

        security = staging.settings.setdefault("security", {})
        security["password_protection"] = {
            "enabled": command.password_protection_enabled,
            "username": command.password_protection_username,
            "password": command.password_protection_password,
        }
        security["ip_restriction"] = {
            "enabled": command.ip_restriction_enabled,
            "allowed_ips": command.allowed_ips or [],
        }
        if command.temp_access_enabled:
            security["temp_access"] = {
                "enabled": True,
                "expires_at": (utc_now() + timedelta(hours=command.temp_access_hours)).isoformat(),
            }
        else:
            security["temp_access"] = {"enabled": False, "expires_at": None}

        if staging.stack_type == StagingStackType.WORDPRESS and staging.settings.get("db_name"):
            db_password = self._provisioner._crypto.decrypt(staging.settings["db_password_enc"])
            await self._provisioner.deploy_wordpress(
                staging,
                staging.settings["db_name"],
                staging.settings["db_user"],
                db_password,
            )
        else:
            await self._provisioner.deploy_website(staging)

        await self._uow.staging_sites.save(staging)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="staging.security_updated",
                resource_type="staging_site",
                resource_id=str(staging.id),
            )
        )
        await self._uow.commit()
        return _to_response(staging)


class ListStagingSitesHandler(QueryHandler[ListStagingSitesQuery, list[StagingSiteResponse]]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = StagingProvisioner(settings)

    async def handle(self, query: ListStagingSitesQuery) -> list[StagingSiteResponse]:
        if query.source_type and query.source_id:
            sites = await self._uow.staging_sites.list_by_source(
                StagingSourceType(query.source_type), query.source_id, query.tenant_id
            )
        else:
            sites = await self._uow.staging_sites.list_by_tenant(
                query.tenant_id, query.limit, query.offset
            )
        results = []
        for site in sites:
            if site.status == StagingStatus.RUNNING:
                cpu, mem, disk = await self._provisioner.collect_metrics(site)
                site.update_metrics(cpu, mem, disk)
            results.append(_to_response(site))
        return results


class GetStagingSiteHandler(QueryHandler[GetStagingSiteQuery, StagingSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._provisioner = StagingProvisioner(settings)

    async def handle(self, query: GetStagingSiteQuery) -> StagingSiteResponse:
        staging = await self._uow.staging_sites.get_by_id_and_tenant(query.staging_id, query.tenant_id)
        if staging is None:
            raise NotFoundError("Staging site not found")
        if staging.status == StagingStatus.RUNNING:
            cpu, mem, disk = await self._provisioner.collect_metrics(staging)
            staging.update_metrics(cpu, mem, disk)
        return _to_response(staging)
