from controlbox.modules.websites.application.queries import (
    DatabaseOptionResponse,
    GetRuntimeOptionsQuery,
    GetWebsiteQuery,
    ListWebsitesQuery,
    RuntimeOptionResponse,
    WebsiteOptionsResponse,
    WebsiteResponse,
)
from controlbox.modules.websites.domain.entities import (
    DEFAULT_RUNTIME_VERSIONS,
    RUNTIME_VERSIONS,
    DatabaseEngine,
    WebsiteRuntime,
)
from controlbox.shared.application.cqrs import QueryHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


RUNTIME_LABELS = {
    WebsiteRuntime.HTML: "HTML Static",
    WebsiteRuntime.PHP: "PHP",
    WebsiteRuntime.NODEJS: "Node.js",
    WebsiteRuntime.PYTHON: "Python",
    WebsiteRuntime.FLUTTER: "Flutter Web",
}

DATABASE_LABELS = {
    DatabaseEngine.NONE: "None",
    DatabaseEngine.MYSQL: "MySQL",
    DatabaseEngine.SUPABASE: "Supabase (PostgreSQL)",
    DatabaseEngine.MSSQL: "Microsoft SQL Server",
}


def _to_response(website) -> WebsiteResponse:
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
        database_config={k: v for k, v in website.database_config.items() if k != "password"},
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


class ListWebsitesHandler(QueryHandler[ListWebsitesQuery, list[WebsiteResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListWebsitesQuery) -> list[WebsiteResponse]:
        websites = await self._uow.websites.list_by_tenant(query.tenant_id, query.limit, query.offset)
        return [_to_response(w) for w in websites]


class GetWebsiteHandler(QueryHandler[GetWebsiteQuery, WebsiteResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetWebsiteQuery) -> WebsiteResponse:
        website = await self._uow.websites.get_by_id_and_tenant(query.website_id, query.tenant_id)
        if website is None:
            raise NotFoundError("Website not found")
        return _to_response(website)


class GetWebsiteOptionsHandler(QueryHandler[GetRuntimeOptionsQuery, WebsiteOptionsResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetRuntimeOptionsQuery) -> WebsiteOptionsResponse:
        runtimes = [
            RuntimeOptionResponse(
                runtime=runtime.value,
                label=RUNTIME_LABELS[runtime],
                versions=RUNTIME_VERSIONS.get(runtime, []),
                default_version=DEFAULT_RUNTIME_VERSIONS.get(runtime, ""),
            )
            for runtime in WebsiteRuntime
        ]
        databases = [
            DatabaseOptionResponse(engine=engine.value, label=DATABASE_LABELS[engine])
            for engine in [DatabaseEngine.NONE, DatabaseEngine.MYSQL, DatabaseEngine.SUPABASE, DatabaseEngine.MSSQL]
        ]
        return WebsiteOptionsResponse(runtimes=runtimes, databases=databases)
