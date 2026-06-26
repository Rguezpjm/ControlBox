from controlbox.modules.joomla.application.responses import to_joomla_site_response
from controlbox.modules.joomla.application.queries import (
    GetJoomlaSiteQuery,
    ListJoomlaBackupsQuery,
    ListJoomlaSitesQuery,
    JoomlaBackupResponse,
    JoomlaOptionsResponse,
    JoomlaSiteResponse,
)
from controlbox.config.settings import Settings
from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.modules.joomla.domain.entities import DEFAULT_PHP_VERSION, JOOMLA_VERSION
from controlbox.modules.joomla.infrastructure.provisioner import JoomlaProvisioner
from controlbox.shared.application.cqrs import QueryHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


class ListJoomlaSitesHandler(QueryHandler[ListJoomlaSitesQuery, list[JoomlaSiteResponse]]):
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, query: ListJoomlaSitesQuery) -> list[JoomlaSiteResponse]:
        sites = await self._uow.joomla_sites.list_by_tenant(query.tenant_id, query.limit, query.offset)
        if not query.can_manage_all:
            sites = [
                site for site in sites
                if site.owner_user_id is not None and site.owner_user_id == query.requester_user_id
            ]
        if self._settings:
            provisioner = JoomlaProvisioner(self._settings)
            for site in sites:
                site.disk_used_mb = provisioner.measure_disk_mb(site)
        return [to_joomla_site_response(s, self._settings) for s in sites]


class GetJoomlaSiteHandler(QueryHandler[GetJoomlaSiteQuery, JoomlaSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, query: GetJoomlaSiteQuery) -> JoomlaSiteResponse:
        site = await self._uow.joomla_sites.get_by_id_and_tenant(query.site_id, query.tenant_id)
        if site is None:
            raise NotFoundError("Joomla site not found")
        if not query.can_manage_all and site.owner_user_id != query.requester_user_id:
            raise NotFoundError("Joomla site not found")
        if self._settings:
            provisioner = JoomlaProvisioner(self._settings)
            site.disk_used_mb = provisioner.measure_disk_mb(site)
        return to_joomla_site_response(site, self._settings)


class ListJoomlaBackupsHandler(QueryHandler[ListJoomlaBackupsQuery, list[JoomlaBackupResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListJoomlaBackupsQuery) -> list[JoomlaBackupResponse]:
        backups = await self._uow.joomla_backups.list_by_site(query.site_id, query.tenant_id)
        return [
            JoomlaBackupResponse(
                id=b.id,
                site_id=b.site_id,
                name=b.name,
                status=b.status.value if hasattr(b.status, "value") else b.status,
                size_mb=b.size_mb,
                checksum=b.checksum,
                includes_database=b.includes_database,
                includes_files=b.includes_files,
                error_message=b.error_message,
                completed_at=b.completed_at,
                created_at=b.created_at,
                updated_at=b.updated_at,
            )
            for b in backups
        ]


class GetJoomlaOptionsHandler(QueryHandler[None, JoomlaOptionsResponse]):
    def __init__(self, settings: Settings) -> None:
        self._runtimes = RuntimeCatalogManager(settings)

    async def handle(self, query: None = None) -> JoomlaOptionsResponse:
        php_versions = self._runtimes.get_php_versions()
        return JoomlaOptionsResponse(
            php_versions=php_versions or ["8.2", "8.3"],
            joomla_version=JOOMLA_VERSION,
        )
