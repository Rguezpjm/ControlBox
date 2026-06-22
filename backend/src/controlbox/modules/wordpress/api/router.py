from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import (
    AppState,
    RequestContext,
    get_app_state,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.wordpress.api.schemas import (
    ChangePhpVersionRequest,
    CloneWordPressSiteRequest,
    CreateWordPressBackupRequest,
    CreateWordPressSiteRequest,
    ToggleMaintenanceRequest,
    WordPressBackupResponseSchema,
    WordPressOptionsSchema,
    WordPressSiteResponseSchema,
)
from controlbox.shared.api.site_modification_schemas import (
    AddSiteDomainRequest,
    SiteModificationSchema,
    UpdateSiteModificationRequest,
)
from controlbox.shared.infrastructure.site_modification import SiteModificationService
from controlbox.modules.wordpress.application.command_handlers import (
    ChangePhpVersionHandler,
    CloneWordPressSiteHandler,
    CreateStagingHandler,
    CreateWordPressBackupHandler,
    CreateWordPressSiteHandler,
    DeleteWordPressSiteHandler,
    RestoreWordPressBackupHandler,
    RestartWordPressSiteHandler,
    ToggleMaintenanceHandler,
)
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
from controlbox.modules.wordpress.application.query_handlers import (
    GetWordPressOptionsHandler,
    GetWordPressSiteHandler,
    ListWordPressBackupsHandler,
    ListWordPressSitesHandler,
)
from controlbox.modules.wordpress.application.queries import (
    GetWordPressSiteQuery,
    ListWordPressBackupsQuery,
    ListWordPressSitesQuery,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError
from controlbox.shared.infrastructure.site_stats import get_site_traffic_stats, get_ssl_days_remaining


router = APIRouter(prefix="/wordpress", tags=["wordpress"])


async def _wordpress_schema(container: AppState, tenant_id: UUID, site) -> WordPressSiteResponseSchema:
    requests, sparkline = await get_site_traffic_stats(container.redis_client, tenant_id, site.id)
    return WordPressSiteResponseSchema(
        **site.__dict__,
        ssl_days_remaining=get_ssl_days_remaining(
            container.settings, site.domain, site.ssl_enabled, site.ssl_status
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
    )


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


@router.get("/options", response_model=WordPressOptionsSchema)
async def get_options(
    context: Annotated[RequestContext, Depends(require_permission("wordpress.read"))],
) -> WordPressOptionsSchema:
    handler = GetWordPressOptionsHandler()
    options = await handler.handle()
    return WordPressOptionsSchema(**options.__dict__)


@router.get("", response_model=list[WordPressSiteResponseSchema])
async def list_sites(
    context: Annotated[RequestContext, Depends(require_permission("wordpress.read"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[WordPressSiteResponseSchema]:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        sites = await ListWordPressSitesHandler(uow=uow, settings=settings).handle(
            ListWordPressSitesQuery(tenant_id=tenant_id, limit=min(limit, 100), offset=offset)
        )
        return [await _wordpress_schema(container, tenant_id, s) for s in sites]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("", response_model=WordPressSiteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_site(
    payload: CreateWordPressSiteRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await CreateWordPressSiteHandler(uow=uow, settings=settings).handle(
            CreateWordPressSiteCommand(
                tenant_id=tenant_id,
                user_id=context.user_id,
                name=payload.name,
                domain=payload.domain,
                admin_user=payload.admin_user,
                admin_password=payload.admin_password,
                admin_email=str(payload.admin_email),
                php_version=payload.php_version,
                ssl_enabled=payload.ssl_enabled,
            )
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{site_id}", response_model=WordPressSiteResponseSchema)
async def get_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await GetWordPressSiteHandler(uow=uow, settings=settings).handle(
            GetWordPressSiteQuery(site_id=site_id, tenant_id=tenant_id)
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{site_id}/modification", response_model=SiteModificationSchema)
async def get_site_modification(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.wordpress_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("WordPress site not found"))
    view = await SiteModificationService(settings).get_wordpress(site_entity)
    return _modification_schema(view)


@router.patch("/{site_id}/modification", response_model=SiteModificationSchema)
async def update_site_modification(
    site_id: UUID,
    payload: UpdateSiteModificationRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.wordpress_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("WordPress site not found"))
    try:
        service = SiteModificationService(settings)
        view = await service.update_wordpress(
            site_entity,
            settings_patch=payload.settings,
            vhost_config=payload.vhost_config,
            nginx_config=payload.nginx_config,
            ssl_enabled=payload.ssl_enabled,
            php_version=payload.php_version,
        )
        await uow.wordpress_sites.save(site_entity)
        await uow.commit()
        return _modification_schema(view)
    except RuntimeError as exc:
        raise map_domain_exception(ForbiddenError(str(exc))) from exc


@router.post("/{site_id}/domains", response_model=SiteModificationSchema)
async def add_wordpress_domain(
    site_id: UUID,
    payload: AddSiteDomainRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.wordpress_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("WordPress site not found"))
    service = SiteModificationService(settings)
    updated = service.add_domain(site_entity.settings or {}, payload.domain, payload.port)
    view = await service.update_wordpress(site_entity, settings_patch=updated)
    await uow.wordpress_sites.save(site_entity)
    await uow.commit()
    return _modification_schema(view)


@router.delete("/{site_id}/domains/{domain}", response_model=SiteModificationSchema)
async def remove_wordpress_domain(
    site_id: UUID,
    domain: str,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.wordpress_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("WordPress site not found"))
    service = SiteModificationService(settings)
    updated = service.remove_domain(site_entity.settings or {}, domain)
    view = await service.update_wordpress(site_entity, settings_patch=updated)
    await uow.wordpress_sites.save(site_entity)
    await uow.commit()
    return _modification_schema(view)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        await DeleteWordPressSiteHandler(uow=uow, settings=settings).handle(
            DeleteWordPressSiteCommand(site_id=site_id, tenant_id=tenant_id, user_id=context.user_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/restart", response_model=WordPressSiteResponseSchema)
async def restart_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await RestartWordPressSiteHandler(uow=uow, settings=settings).handle(
            RestartWordPressSiteCommand(site_id=site_id, tenant_id=tenant_id, user_id=context.user_id)
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/php-version", response_model=WordPressSiteResponseSchema)
async def change_php_version(
    site_id: UUID,
    payload: ChangePhpVersionRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await ChangePhpVersionHandler(uow=uow, settings=settings).handle(
            ChangePhpVersionCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                php_version=payload.php_version,
            )
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/maintenance", response_model=WordPressSiteResponseSchema)
async def toggle_maintenance(
    site_id: UUID,
    payload: ToggleMaintenanceRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await ToggleMaintenanceHandler(uow=uow, settings=settings).handle(
            ToggleMaintenanceCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                enabled=payload.enabled,
            )
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/clone", response_model=WordPressSiteResponseSchema)
async def clone_site(
    site_id: UUID,
    payload: CloneWordPressSiteRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await CloneWordPressSiteHandler(uow=uow, settings=settings).handle(
            CloneWordPressSiteCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                new_domain=payload.new_domain,
                new_name=payload.new_name,
            )
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/staging", response_model=WordPressSiteResponseSchema)
async def create_staging(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WordPressSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await CreateStagingHandler(uow=uow, settings=settings).handle(
            CreateStagingCommand(site_id=site_id, tenant_id=tenant_id, user_id=context.user_id)
        )
        return WordPressSiteResponseSchema(**site.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{site_id}/backups", response_model=list[WordPressBackupResponseSchema])
async def list_backups(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[WordPressBackupResponseSchema]:
    tenant_id = _require_tenant(context)
    try:
        backups = await ListWordPressBackupsHandler(uow=uow).handle(
            ListWordPressBackupsQuery(site_id=site_id, tenant_id=tenant_id)
        )
        return [WordPressBackupResponseSchema(**b.__dict__) for b in backups]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/backups", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def create_backup(
    site_id: UUID,
    payload: CreateWordPressBackupRequest,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    tenant_id = _require_tenant(context)
    try:
        backup_id = await CreateWordPressBackupHandler(uow=uow).handle(
            CreateWordPressBackupCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                name=payload.name,
            )
        )
        return {"backup_id": str(backup_id), "status": "queued"}
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/backups/{backup_id}/restore", status_code=status.HTTP_202_ACCEPTED)
async def restore_backup(
    site_id: UUID,
    backup_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("wordpress.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    tenant_id = _require_tenant(context)
    try:
        await RestoreWordPressBackupHandler(uow=uow).handle(
            RestoreWordPressBackupCommand(
                site_id=site_id,
                backup_id=backup_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
            )
        )
        return {"status": "queued"}
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
