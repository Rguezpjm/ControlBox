from controlbox.modules.wordpress.application.queries import (
    GetWordPressSiteQuery,
    ListWordPressBackupsQuery,
    ListWordPressSitesQuery,
    WordPressBackupResponse,
    WordPressOptionsResponse,
    WordPressSiteResponse,
)
from controlbox.config.settings import Settings
from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.modules.wordpress.domain.entities import DEFAULT_PHP_VERSION, WORDPRESS_VERSION
from controlbox.modules.wordpress.infrastructure.provisioner import WordPressProvisioner
from controlbox.config.settings import Settings
from controlbox.shared.application.cqrs import QueryHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


def _site_response(site) -> WordPressSiteResponse:
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


class ListWordPressSitesHandler(QueryHandler[ListWordPressSitesQuery, list[WordPressSiteResponse]]):
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, query: ListWordPressSitesQuery) -> list[WordPressSiteResponse]:
        sites = await self._uow.wordpress_sites.list_by_tenant(query.tenant_id, query.limit, query.offset)
        if self._settings:
            provisioner = WordPressProvisioner(self._settings)
            for site in sites:
                site.disk_used_mb = provisioner.measure_disk_mb(site)
        return [_site_response(s) for s in sites]


class GetWordPressSiteHandler(QueryHandler[GetWordPressSiteQuery, WordPressSiteResponse]):
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, query: GetWordPressSiteQuery) -> WordPressSiteResponse:
        site = await self._uow.wordpress_sites.get_by_id_and_tenant(query.site_id, query.tenant_id)
        if site is None:
            raise NotFoundError("WordPress site not found")
        if self._settings:
            provisioner = WordPressProvisioner(self._settings)
            site.disk_used_mb = provisioner.measure_disk_mb(site)
        return _site_response(site)


class ListWordPressBackupsHandler(QueryHandler[ListWordPressBackupsQuery, list[WordPressBackupResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListWordPressBackupsQuery) -> list[WordPressBackupResponse]:
        backups = await self._uow.wordpress_backups.list_by_site(query.site_id, query.tenant_id)
        return [
            WordPressBackupResponse(
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


class GetWordPressOptionsHandler(QueryHandler[None, WordPressOptionsResponse]):
    def __init__(self, settings: Settings) -> None:
        self._runtimes = RuntimeCatalogManager(settings)

    async def handle(self, query: None = None) -> WordPressOptionsResponse:
        php_versions = self._runtimes.get_php_versions()
        return WordPressOptionsResponse(
            php_versions=php_versions or ["8.2", "8.3"],
            wordpress_version=WORDPRESS_VERSION,
        )
