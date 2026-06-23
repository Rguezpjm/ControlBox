from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.identity.domain.entities import AuditLog
from controlbox.modules.websites.application.commands import (
    CreateWebsiteCommand,
    DeleteWebsiteCommand,
    StartWebsiteCommand,
    StopWebsiteCommand,
)
from controlbox.modules.websites.application.queries import WebsiteResponse
from controlbox.modules.websites.domain.entities import (
    RUNTIME_PORTS,
    DatabaseEngine,
    SslStatus,
    Website,
    WebsiteRuntime,
    WebsiteStatus,
)
from controlbox.config.settings import Settings
from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.modules.websites.domain.services import WebsiteDomainService
from controlbox.modules.websites.infrastructure.provisioner import DatabaseProvisioner, DockerProvisioner
from controlbox.shared.application.cqrs import CommandHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ForbiddenError, NotFoundError
from controlbox.shared.infrastructure.resource_isolation import set_owner_in_settings


def _to_response(website: Website) -> WebsiteResponse:
    return WebsiteResponse(
        id=website.id,
        tenant_id=website.tenant_id,
        name=website.name,
        domain=website.domain,
        runtime=website.runtime.value,
        runtime_version=website.runtime_version,
        status=website.status.value,
        container_id=website.container_id,
        container_name=website.container_name,
        document_root=website.document_root,
        ssl_enabled=website.ssl_enabled,
        ssl_status=website.ssl_status.value,
        database_engine=website.database_engine.value,
        database_config={
            k: v for k, v in website.database_config.items() if k != "password"
        },
        monitoring_enabled=website.monitoring_enabled,
        logs_enabled=website.logs_enabled,
        logs_path=website.logs_path,
        port=website.port,
        disk_used_mb=website.disk_used_mb,
        disk_limit_mb=website.disk_limit_mb,
        error_message=website.error_message,
        created_at=website.created_at,
        updated_at=website.updated_at,
    )


class CreateWebsiteHandler(CommandHandler[CreateWebsiteCommand, WebsiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._docker = DockerProvisioner(settings)
        self._database = DatabaseProvisioner(settings)

    async def handle(self, command: CreateWebsiteCommand) -> WebsiteResponse:
        if not command.tenant_id:
            raise ForbiddenError("Tenant context required")

        domain_service = WebsiteDomainService(
            self._uow.websites,
            runtime_catalog=RuntimeCatalogManager(self._settings),
        )
        domain = domain_service.validate_domain(command.domain)
        await domain_service.ensure_domain_available(domain, command.tenant_id)

        runtime = WebsiteRuntime(command.runtime)
        runtime_version = domain_service.validate_runtime_version(runtime, command.runtime_version)
        database_engine = domain_service.validate_database_engine(DatabaseEngine(command.database_engine))

        website = Website(
            tenant_id=command.tenant_id,
            owner_user_id=command.user_id,
            name=command.name.strip(),
            domain=domain,
            runtime=runtime,
            runtime_version=runtime_version,
            status=WebsiteStatus.PROVISIONING,
            ssl_enabled=command.ssl_enabled,
            ssl_status=SslStatus.PENDING if command.ssl_enabled else SslStatus.ACTIVE,
            database_engine=database_engine,
            port=RUNTIME_PORTS.get(runtime.value, 80),
            disk_limit_mb=command.disk_limit_mb,
            monitoring_enabled=True,
            logs_enabled=True,
            traefik_router=f"site-{domain.replace('.', '-')}",
            settings=set_owner_in_settings({}, command.user_id),
        )
        website.container_name = domain_service.build_container_name(command.tenant_id, website.id)

        if database_engine != DatabaseEngine.NONE:
            website.database_config = self._database.provision(website)

        site_path = self._docker.get_site_path(command.tenant_id, website.id)
        website.document_root = str(site_path / "public")
        website.logs_path = str(site_path / "logs")

        await self._uow.websites.add(website)

        try:
            container_id, container_name = await self._docker.provision(website)
            website.mark_running(container_id, container_name)
            if command.ssl_enabled:
                website.activate_ssl()
        except Exception as exc:
            website.mark_error(str(exc))

        await self._uow.websites.save(website)

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="website.created",
                resource_type="website",
                resource_id=str(website.id),
                metadata={
                    "domain": domain,
                    "runtime": runtime.value,
                    "database_engine": database_engine.value,
                },
            )
        )
        await self._uow.commit()
        return _to_response(website)


class DeleteWebsiteHandler(CommandHandler[DeleteWebsiteCommand, None]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._docker = DockerProvisioner(settings)

    async def handle(self, command: DeleteWebsiteCommand) -> None:
        website = await self._uow.websites.get_by_id_and_tenant(command.website_id, command.tenant_id)
        if website is None:
            raise NotFoundError("Website not found")

        website.status = WebsiteStatus.DELETING
        await self._uow.websites.save(website)

        try:
            await self._docker.destroy(website)
        except Exception:
            pass

        await self._uow.websites.delete(website.id)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="website.deleted",
                resource_type="website",
                resource_id=str(website.id),
            )
        )
        await self._uow.commit()


class StartWebsiteHandler(CommandHandler[StartWebsiteCommand, WebsiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._docker = DockerProvisioner(settings)

    async def handle(self, command: StartWebsiteCommand) -> WebsiteResponse:
        website = await self._uow.websites.get_by_id_and_tenant(command.website_id, command.tenant_id)
        if website is None:
            raise NotFoundError("Website not found")

        await self._docker.start(website)
        website.mark_running(website.container_id or "", website.container_name or "")
        await self._uow.websites.save(website)
        await self._uow.commit()
        return _to_response(website)


class StopWebsiteHandler(CommandHandler[StopWebsiteCommand, WebsiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._docker = DockerProvisioner(settings)

    async def handle(self, command: StopWebsiteCommand) -> WebsiteResponse:
        website = await self._uow.websites.get_by_id_and_tenant(command.website_id, command.tenant_id)
        if website is None:
            raise NotFoundError("Website not found")

        await self._docker.stop(website)
        website.mark_stopped()
        await self._uow.websites.save(website)
        await self._uow.commit()
        return _to_response(website)
