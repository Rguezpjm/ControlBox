from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import (
    AppState,
    RequestContext,
    get_app_state,
    get_current_context,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.websites.api.schemas import (
    CreateWebsiteRequest,
    WebsiteOptionsSchema,
    WebsiteResponseSchema,
)
from controlbox.shared.api.site_modification_schemas import (
    AddSiteDomainRequest,
    SiteModificationSchema,
    UpdateSiteModificationRequest,
)
from controlbox.shared.infrastructure.site_modification import SiteModificationService
from controlbox.modules.websites.application.command_handlers import (
    CreateWebsiteHandler,
    DeleteWebsiteHandler,
    StartWebsiteHandler,
    StopWebsiteHandler,
)
from controlbox.modules.websites.application.commands import (
    CreateWebsiteCommand,
    DeleteWebsiteCommand,
    StartWebsiteCommand,
    StopWebsiteCommand,
)
from controlbox.modules.websites.application.query_handlers import (
    GetWebsiteHandler,
    GetWebsiteOptionsHandler,
    ListWebsitesHandler,
)
from controlbox.modules.websites.application.queries import (
    GetRuntimeOptionsQuery,
    GetWebsiteQuery,
    ListWebsitesQuery,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError
from controlbox.shared.infrastructure.site_stats import get_site_traffic_stats, get_ssl_days_remaining


router = APIRouter(prefix="/websites", tags=["websites"])


async def _website_schema(
    container: AppState,
    tenant_id: UUID,
    website,
) -> WebsiteResponseSchema:
    requests, sparkline = await get_site_traffic_stats(container.redis_client, tenant_id, website.id)
    return WebsiteResponseSchema(
        **website.__dict__,
        ssl_days_remaining=get_ssl_days_remaining(
            container.settings, website.domain, website.ssl_enabled, website.ssl_status
        ),
        requests_count=requests,
        requests_sparkline=sparkline,
    )


def _modification_schema(view) -> SiteModificationSchema:
    return SiteModificationSchema(
        site_type=view.site_type,
        site_id=view.site_id,
        name=view.name,
        primary_domain=view.primary_domain,
        status=view.status,
        created_at=view.created_at,
        runtime=view.runtime,
        runtime_version=view.runtime_version,
        php_version=view.php_version,
        ssl_enabled=view.ssl_enabled,
        ssl_status=view.ssl_status,
        document_root=view.document_root,
        settings=view.settings,
        vhost_config=view.vhost_config,
        nginx_config=view.nginx_config,
        access_log=view.access_log,
        error_log=view.error_log,
def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


@router.get("/options", response_model=WebsiteOptionsSchema)async def get_website_options(
    context: Annotated[RequestContext, Depends(require_permission("websites.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WebsiteOptionsSchema:
    try:
        handler = GetWebsiteOptionsHandler(uow=uow)
        options = await handler.handle(GetRuntimeOptionsQuery())
        return WebsiteOptionsSchema(
            runtimes=[r.__dict__ for r in options.runtimes],
            databases=[d.__dict__ for d in options.databases],
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("", response_model=list[WebsiteResponseSchema])
async def list_websites(
    context: Annotated[RequestContext, Depends(require_permission("websites.read"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[WebsiteResponseSchema]:
    tenant_id = _require_tenant(context)
    try:
        handler = ListWebsitesHandler(uow=uow)
        websites = await handler.handle(
            ListWebsitesQuery(tenant_id=tenant_id, limit=min(limit, 100), offset=offset)
        )
        return [await _website_schema(container, tenant_id, w) for w in websites]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("", response_model=WebsiteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_website(
    payload: CreateWebsiteRequest,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WebsiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        handler = CreateWebsiteHandler(uow=uow, settings=settings)
        website = await handler.handle(
            CreateWebsiteCommand(
                tenant_id=tenant_id,
                user_id=context.user_id,
                name=payload.name,
                domain=payload.domain,
                runtime=payload.runtime,
                runtime_version=payload.runtime_version,
                database_engine=payload.database_engine,
                ssl_enabled=payload.ssl_enabled,
                disk_limit_mb=payload.disk_limit_mb,
            )
        )
        return WebsiteResponseSchema(**website.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{website_id}", response_model=WebsiteResponseSchema)
async def get_website(
    website_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("websites.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WebsiteResponseSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = GetWebsiteHandler(uow=uow)
        website = await handler.handle(GetWebsiteQuery(website_id=website_id, tenant_id=tenant_id))
        return WebsiteResponseSchema(**website.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{website_id}/modification", response_model=SiteModificationSchema)
async def get_website_modification(
    website_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("websites.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    website_entity = await uow.websites.get_by_id_and_tenant(website_id, tenant_id)
    if website_entity is None:
        raise map_domain_exception(ForbiddenError("Website not found"))
    view = await SiteModificationService(settings).get_website(website_entity)
    return _modification_schema(view)


@router.patch("/{website_id}/modification", response_model=SiteModificationSchema)
async def update_website_modification(
    website_id: UUID,
    payload: UpdateSiteModificationRequest,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    website_entity = await uow.websites.get_by_id_and_tenant(website_id, tenant_id)
    if website_entity is None:
        raise map_domain_exception(ForbiddenError("Website not found"))
    try:
        service = SiteModificationService(settings)
        view = await service.update_website(
            website_entity,
            settings_patch=payload.settings,
            vhost_config=payload.vhost_config,
            ssl_enabled=payload.ssl_enabled,
            runtime_version=payload.runtime_version,
        )
        await uow.websites.save(website_entity)
        await uow.commit()
        return _modification_schema(view)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise map_domain_exception(ForbiddenError(str(exc))) from exc


@router.post("/{website_id}/domains", response_model=SiteModificationSchema)
async def add_website_domain(
    website_id: UUID,
    payload: AddSiteDomainRequest,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    website_entity = await uow.websites.get_by_id_and_tenant(website_id, tenant_id)
    if website_entity is None:
        raise map_domain_exception(ForbiddenError("Website not found"))
    service = SiteModificationService(settings)
    updated = service.add_domain(website_entity.settings or {}, payload.domain, payload.port)
    view = await service.update_website(website_entity, settings_patch=updated)
    await uow.websites.save(website_entity)
    await uow.commit()
    return _modification_schema(view)


@router.delete("/{website_id}/domains/{domain}", response_model=SiteModificationSchema)
async def remove_website_domain(
    website_id: UUID,
    domain: str,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    website_entity = await uow.websites.get_by_id_and_tenant(website_id, tenant_id)
    if website_entity is None:
        raise map_domain_exception(ForbiddenError("Website not found"))
    service = SiteModificationService(settings)
    updated = service.remove_domain(website_entity.settings or {}, domain)
    view = await service.update_website(website_entity, settings_patch=updated)
    await uow.websites.save(website_entity)
    await uow.commit()
    return _modification_schema(view)


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_website(
    website_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        handler = DeleteWebsiteHandler(uow=uow, settings=settings)
        await handler.handle(
            DeleteWebsiteCommand(website_id=website_id, tenant_id=tenant_id, user_id=context.user_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{website_id}/start", response_model=WebsiteResponseSchema)
async def start_website(
    website_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WebsiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        handler = StartWebsiteHandler(uow=uow, settings=settings)
        website = await handler.handle(
            StartWebsiteCommand(website_id=website_id, tenant_id=tenant_id, user_id=context.user_id)
        )
        return WebsiteResponseSchema(**website.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{website_id}/stop", response_model=WebsiteResponseSchema)
async def stop_website(
    website_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("websites.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WebsiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        handler = StopWebsiteHandler(uow=uow, settings=settings)
        website = await handler.handle(
            StopWebsiteCommand(website_id=website_id, tenant_id=tenant_id, user_id=context.user_id)
        )
        return WebsiteResponseSchema(**website.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
