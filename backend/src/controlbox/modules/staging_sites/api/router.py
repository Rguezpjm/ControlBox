from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.staging_sites.api.schemas import (
    BlockStagingAccessRequest,
    CreateStagingSiteRequest,
    StagingSiteResponseSchema,
    SyncStagingRequest,
    SyncTypeRequest,
    UpdateStagingSecurityRequest,
)
from controlbox.modules.staging_sites.application.command_handlers import (
    BlockStagingAccessHandler,
    CreateStagingSiteHandler,
    DeleteStagingSiteHandler,
    GetStagingSiteHandler,
    ListStagingSitesHandler,
    RestartStagingSiteHandler,
    SyncStagingHandler,
    UpdateStagingSecurityHandler,
)
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
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError


router = APIRouter(prefix="/staging", tags=["staging"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _to_schema(response) -> StagingSiteResponseSchema:
    data = response.__dict__
    return StagingSiteResponseSchema(**data)


@router.get("", response_model=list[StagingSiteResponseSchema])
async def list_staging_sites(
    context: Annotated[RequestContext, Depends(require_permission("staging.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    source_type: str | None = None,
    source_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StagingSiteResponseSchema]:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        sites = await ListStagingSitesHandler(uow, settings).handle(
            ListStagingSitesQuery(
                tenant_id=tenant_id,
                source_type=source_type,
                source_id=source_id,
                limit=min(limit, 100),
                offset=offset,
            )
        )
        return [_to_schema(s) for s in sites]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{staging_id}", response_model=StagingSiteResponseSchema)
async def get_staging_site(
    staging_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("staging.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await GetStagingSiteHandler(uow, settings).handle(
            GetStagingSiteQuery(staging_id=staging_id, tenant_id=tenant_id)
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("", response_model=StagingSiteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_staging_site(
    payload: CreateStagingSiteRequest,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await CreateStagingSiteHandler(uow, settings).handle(
            CreateStagingSiteCommand(
                tenant_id=tenant_id,
                user_id=context.user_id,
                source_type=payload.source_type,
                source_id=payload.source_id,
                domain_mode=payload.domain_mode,
                name=payload.name,
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{staging_id}/sync", response_model=StagingSiteResponseSchema)
async def sync_staging(
    staging_id: UUID,
    payload: SyncStagingRequest,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    try:
        site = await SyncStagingHandler(uow).handle(
            SyncStagingCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                sync_type=payload.sync_type,
                direction=payload.direction,
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{staging_id}/sync-from-production", response_model=StagingSiteResponseSchema)
async def sync_from_production(
    staging_id: UUID,
    payload: SyncTypeRequest,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    try:
        site = await SyncStagingHandler(uow).handle(
            SyncStagingCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                sync_type=payload.sync_type,
                direction="from_production",
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{staging_id}/sync-to-production", response_model=StagingSiteResponseSchema)
async def sync_to_production(
    staging_id: UUID,
    payload: SyncTypeRequest,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    try:
        site = await SyncStagingHandler(uow).handle(
            SyncStagingCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                sync_type=payload.sync_type,
                direction="to_production",
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/{staging_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staging_site(
    staging_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteStagingSiteHandler(uow).handle(
            DeleteStagingSiteCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{staging_id}/restart", response_model=StagingSiteResponseSchema)
async def restart_staging_site(
    staging_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await RestartStagingSiteHandler(uow, settings).handle(
            RestartStagingSiteCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{staging_id}/block-access", response_model=StagingSiteResponseSchema)
async def block_staging_access(
    staging_id: UUID,
    payload: BlockStagingAccessRequest,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await BlockStagingAccessHandler(uow, settings).handle(
            BlockStagingAccessCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                blocked=payload.blocked,
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.patch("/{staging_id}/security", response_model=StagingSiteResponseSchema)
async def update_staging_security(
    staging_id: UUID,
    payload: UpdateStagingSecurityRequest,
    context: Annotated[RequestContext, Depends(require_permission("staging.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StagingSiteResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        site = await UpdateStagingSecurityHandler(uow, settings).handle(
            UpdateStagingSecurityCommand(
                staging_id=staging_id,
                tenant_id=tenant_id,
                user_id=context.user_id,
                password_protection_enabled=payload.password_protection_enabled,
                password_protection_username=payload.password_protection_username,
                password_protection_password=payload.password_protection_password,
                ip_restriction_enabled=payload.ip_restriction_enabled,
                allowed_ips=payload.allowed_ips,
                temp_access_enabled=payload.temp_access_enabled,
                temp_access_hours=payload.temp_access_hours,
            )
        )
        return _to_schema(site)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
