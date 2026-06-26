from typing import Annotated
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, status

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.identity.api.dependencies import (
    AppState,
    RequestContext,
    get_app_state,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.joomla.api.schemas import (
    ChangePhpVersionRequest,
    ChangeJoomlaAdminPasswordRequest,
    CloneJoomlaSiteRequest,
    CreateJoomlaBackupRequest,
    CreateJoomlaSiteRequest,
    ToggleMaintenanceRequest,
    JoomlaBackupResponseSchema,
    JoomlaOptionsSchema,
    JoomlaProvisionStatusSchema,
    JoomlaSiteAccessSchema,
    JoomlaSiteResponseSchema,
)
from controlbox.modules.joomla.application.queries import JoomlaSiteResponse
from controlbox.shared.api.site_modification_schemas import (
    AddSiteDomainRequest,
    SiteModificationSchema,
    SiteSslConfigSchema,
    SubdirectoryBindingSchema,
    UpdateSiteModificationRequest,
)
from controlbox.shared.infrastructure.site_modification import SiteModificationService
from controlbox.modules.joomla.application.command_handlers import (
    ChangePhpVersionHandler,
    ChangeJoomlaAdminPasswordHandler,
    CloneJoomlaSiteHandler,
    CreateStagingHandler,
    CreateJoomlaBackupHandler,
    CreateJoomlaSiteHandler,
    DeleteJoomlaSiteHandler,
    RestoreJoomlaBackupHandler,
    RestartJoomlaSiteHandler,
    ToggleMaintenanceHandler,
)
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
from controlbox.modules.joomla.application.query_handlers import (
    GetJoomlaOptionsHandler,
    GetJoomlaSiteHandler,
    ListJoomlaBackupsHandler,
    ListJoomlaSitesHandler,
)
from controlbox.modules.joomla.application.queries import (
    GetJoomlaSiteQuery,
    ListJoomlaBackupsQuery,
    ListJoomlaSitesQuery,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError
from controlbox.shared.api.site_log_schemas import AccessLogEntrySchema, SiteAccessLogsSchema, SiteErrorLogSchema
from controlbox.shared.infrastructure.site_logs import SiteLogReader
from controlbox.modules.joomla.infrastructure.provision_progress import build_provision_status
from controlbox.shared.infrastructure.site_stats import enrich_site_monitoring_fields, get_ssl_days_remaining
from controlbox.shared.infrastructure.resource_isolation import can_manage_all_resources


router = APIRouter(prefix="/joomla", tags=["joomla"])


def _serialize_site_response(site: JoomlaSiteResponse) -> JoomlaSiteResponseSchema:
    payload = {key: value for key, value in site.__dict__.items() if key != "access_info"}
    if site.access_info is not None:
        payload["access_info"] = JoomlaSiteAccessSchema(**site.access_info.__dict__)
    return JoomlaSiteResponseSchema(**payload)


async def _joomla_schema(container: AppState, tenant_id: UUID, site: JoomlaSiteResponse) -> JoomlaSiteResponseSchema:
    monitoring = await enrich_site_monitoring_fields(
        container.redis_client, tenant_id, site.id, "joomla"
    )
    base = _serialize_site_response(site)
    return base.model_copy(
        update={
            "ssl_days_remaining": get_ssl_days_remaining(
                container.settings, site.domain, site.ssl_enabled, site.ssl_status
            ),
            **monitoring,
        }
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
        php_extensions=view.php_extensions,
        php_extensions_available=view.php_extensions_available,
        ssl_enabled=view.ssl_enabled,
        ssl_status=view.ssl_status,
        ssl_config=SiteSslConfigSchema(**view.ssl_config.__dict__) if view.ssl_config else None,
        document_root=view.document_root,
        running_directory=view.running_directory,
        running_directory_options=view.running_directory_options,
        open_basedir_enabled=view.open_basedir_enabled,
        logs_enabled=view.logs_enabled,
        site_files_path=view.site_files_path,
        site_path=view.site_path,
        subdirectory_bindings=[
            SubdirectoryBindingSchema(**item) if isinstance(item, dict) else item
            for item in view.subdirectory_bindings
        ],
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


def _assert_site_access(context: RequestContext, site_entity) -> None:
    if can_manage_all_resources(context):
        return
    if site_entity.owner_user_id is None or site_entity.owner_user_id != context.user_id:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))


@router.get("/options", response_model=JoomlaOptionsSchema)
async def get_options(
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JoomlaOptionsSchema:
    handler = GetJoomlaOptionsHandler(settings=settings)
    options = await handler.handle()
    return JoomlaOptionsSchema(**options.__dict__)


@router.get("", response_model=list[JoomlaSiteResponseSchema])
async def list_sites(
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[JoomlaSiteResponseSchema]:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        sites = await ListJoomlaSitesHandler(uow=uow, settings=settings).handle(
            ListJoomlaSitesQuery(
                tenant_id=tenant_id,
                requester_user_id=context.user_id,
                can_manage_all=can_manage_all_resources(context),
                limit=min(limit, 100),
                offset=offset,
            )
        )
        return [await _joomla_schema(container, tenant_id, s) for s in sites]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("", response_model=JoomlaSiteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_site(
    payload: CreateJoomlaSiteRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await CreateJoomlaSiteHandler(uow=uow, settings=settings).handle(
            CreateJoomlaSiteCommand(
                tenant_id=tenant_id,
                user_id=context.user_id,
                name=payload.name,
                domain=payload.domain,
                admin_user=payload.admin_user,
                admin_password=payload.admin_password,
                admin_email=str(payload.admin_email),
                php_version=payload.php_version,
                ssl_enabled=payload.ssl_enabled,
                create_ftp_account=payload.create_ftp_account,
                db_name=payload.db_name,
                db_user=payload.db_user,
                db_password=payload.db_password,
            )
        )
        return _serialize_site_response(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{site_id}", response_model=JoomlaSiteResponseSchema)
async def get_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await GetJoomlaSiteHandler(uow=uow, settings=settings).handle(
            GetJoomlaSiteQuery(
                site_id=site_id,
                tenant_id=tenant_id,
                requester_user_id=context.user_id,
                can_manage_all=can_manage_all_resources(context),
            )
        )
        return await _joomla_schema(container, tenant_id, site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/admin-password", response_model=JoomlaSiteResponseSchema)
async def change_joomla_admin_password(
    site_id: UUID,
    payload: ChangeJoomlaAdminPasswordRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        site = await ChangeJoomlaAdminPasswordHandler(uow=uow, settings=settings).handle(
            ChangeJoomlaAdminPasswordCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                new_password=payload.new_password,
            )
        )
        return await _joomla_schema(container, tenant_id, site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{site_id}/provision-status", response_model=JoomlaProvisionStatusSchema)
async def get_provision_status(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JoomlaProvisionStatusSchema:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    payload = build_provision_status(site_entity, settings)
    return JoomlaProvisionStatusSchema(**payload)


@router.get("/{site_id}/modification", response_model=SiteModificationSchema)
async def get_site_modification(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    view = await SiteModificationService(settings).get_joomla(site_entity)
    return _modification_schema(view)


@router.get("/{site_id}/access-logs", response_model=SiteAccessLogsSchema)
async def get_joomla_access_logs(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 100,
) -> SiteAccessLogsSchema:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    reader = SiteLogReader(settings)
    site_path = Path(site_entity.site_path)
    cap = 2000 if limit <= 0 else min(max(limit, 1), 2000)
    source, entries = await reader.read_access_logs(
        site_path=site_path,
        container_name=site_entity.nginx_container_name,
        limit=cap,
    )
    return SiteAccessLogsSchema(
        source=source or str(site_path / "logs" / "access.log"),
        entries=[AccessLogEntrySchema.model_validate(e) for e in entries],
    )


@router.get("/{site_id}/error-log", response_model=SiteErrorLogSchema)
async def get_joomla_error_log(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 100,
) -> SiteErrorLogSchema:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    reader = SiteLogReader(settings)
    site_path = Path(site_entity.site_path)
    cap = 2000 if limit <= 0 else min(max(limit, 1), 2000)
    source, content = await reader.read_error_log(
        site_path=site_path,
        container_name=site_entity.nginx_container_name,
        limit=cap,
    )
    return SiteErrorLogSchema(source=source or str(site_path / "logs" / "error.log"), content=content)


@router.patch("/{site_id}/modification", response_model=SiteModificationSchema)
async def update_site_modification(
    site_id: UUID,
    payload: UpdateSiteModificationRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        service = SiteModificationService(settings)
        view = await service.update_joomla(
            site_entity,
            settings_patch=payload.settings,
            document_root=payload.document_root,
            logs_enabled=payload.logs_enabled,
            vhost_config=payload.vhost_config,
            nginx_config=payload.nginx_config,
            ssl_enabled=payload.ssl_enabled,
            php_version=payload.php_version,
            php_extensions=payload.php_extensions,
            ssl_provider=payload.ssl_provider,
            ssl_certificate_pem=payload.ssl_certificate_pem,
            ssl_private_key_pem=payload.ssl_private_key_pem,
            ssl_force_https=payload.ssl_force_https,
        )
        await uow.joomla_sites.save(site_entity)
        await uow.commit()
        return _modification_schema(view)
    except RuntimeError as exc:
        raise map_domain_exception(ForbiddenError(str(exc))) from exc


@router.post("/{site_id}/domains", response_model=SiteModificationSchema)
async def add_joomla_domain(
    site_id: UUID,
    payload: AddSiteDomainRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    service = SiteModificationService(settings)
    updated = service.add_domain(site_entity.settings or {}, payload.domain, payload.port)
    view = await service.update_joomla(site_entity, settings_patch=updated)
    await uow.joomla_sites.save(site_entity)
    await uow.commit()
    return _modification_schema(view)


@router.delete("/{site_id}/domains/{domain}", response_model=SiteModificationSchema)
async def remove_joomla_domain(
    site_id: UUID,
    domain: str,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SiteModificationSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    service = SiteModificationService(settings)
    updated = service.remove_domain(site_entity.settings or {}, domain)
    view = await service.update_joomla(site_entity, settings_patch=updated)
    await uow.joomla_sites.save(site_entity)
    await uow.commit()
    return _modification_schema(view)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        await DeleteJoomlaSiteHandler(uow=uow, settings=settings).handle(
            DeleteJoomlaSiteCommand(site_id=site_id, tenant_id=tenant_id, user_id=context.user_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/restart", response_model=JoomlaSiteResponseSchema)
async def restart_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        site = await RestartJoomlaSiteHandler(uow=uow, settings=settings).handle(
            RestartJoomlaSiteCommand(site_id=site_id, tenant_id=tenant_id, user_id=context.user_id)
        )
        return _serialize_site_response(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/publish")
async def publish_site(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
):
    import logging
    logger = logging.getLogger("controlbox.joomla")
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    logger.info("Joomla site %s published to public tunnel", site_id)
    return {
        "success": True,
        "message": "Sitio publicado correctamente a través del túnel de acceso público.",
        "url": f"https://{site_entity.domain}.tunnel.grodtech.com"
    }


@router.post("/{site_id}/php-version", response_model=JoomlaSiteResponseSchema)
async def change_php_version(
    site_id: UUID,
    payload: ChangePhpVersionRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        site = await ChangePhpVersionHandler(uow=uow, settings=settings).handle(
            ChangePhpVersionCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                php_version=payload.php_version,
            )
        )
        return _serialize_site_response(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/maintenance", response_model=JoomlaSiteResponseSchema)
async def toggle_maintenance(
    site_id: UUID,
    payload: ToggleMaintenanceRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        site = await ToggleMaintenanceHandler(uow=uow, settings=settings).handle(
            ToggleMaintenanceCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                enabled=payload.enabled,
            )
        )
        return _serialize_site_response(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/clone", response_model=JoomlaSiteResponseSchema)
async def clone_site(
    site_id: UUID,
    payload: CloneJoomlaSiteRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        site = await CloneJoomlaSiteHandler(uow=uow, settings=settings).handle(
            CloneJoomlaSiteCommand(
                site_id=site_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                new_domain=payload.new_domain,
                new_name=payload.new_name,
            )
        )
        return _serialize_site_response(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/staging", response_model=JoomlaSiteResponseSchema)
async def create_staging(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> JoomlaSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        site = await CreateStagingHandler(uow=uow, settings=settings).handle(
            CreateStagingCommand(site_id=site_id, tenant_id=tenant_id, user_id=context.user_id)
        )
        return _serialize_site_response(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{site_id}/backups", response_model=list[JoomlaBackupResponseSchema])
async def list_backups(
    site_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("joomla.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[JoomlaBackupResponseSchema]:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        backups = await ListJoomlaBackupsHandler(uow=uow).handle(
            ListJoomlaBackupsQuery(site_id=site_id, tenant_id=tenant_id)
        )
        return [JoomlaBackupResponseSchema(**b.__dict__) for b in backups]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{site_id}/backups", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def create_backup(
    site_id: UUID,
    payload: CreateJoomlaBackupRequest,
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        backup_id = await CreateJoomlaBackupHandler(uow=uow).handle(
            CreateJoomlaBackupCommand(
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
    context: Annotated[RequestContext, Depends(require_permission("joomla.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    tenant_id = _require_tenant(context)
    site_entity = await uow.joomla_sites.get_by_id_and_tenant(site_id, tenant_id)
    if site_entity is None:
        raise map_domain_exception(ForbiddenError("Joomla site not found"))
    _assert_site_access(context, site_entity)
    try:
        await RestoreJoomlaBackupHandler(uow=uow).handle(
            RestoreJoomlaBackupCommand(
                site_id=site_id,
                backup_id=backup_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
            )
        )
        return {"status": "queued"}
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
