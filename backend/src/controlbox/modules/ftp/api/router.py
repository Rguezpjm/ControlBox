from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from controlbox.config.settings import get_settings
from controlbox.modules.ftp.api.schemas import (
    ChangeFtpPasswordRequest,
    CreateFtpAccountRequest,
    FtpAccountCreatedSchema,
    FtpAccountSchema,
    FtpLogSchema,
    FtpPasswordChangedSchema,
    FtpServiceActionResponse,
    FtpServiceStatusSchema,
    SetFtpDirectoryRequest,
    SetFtpQuotaRequest,
    SetFtpStatusRequest,
    UpdateFtpAccountRequest,
    UpdateFtpServiceRequest,
)
from controlbox.modules.ftp.application.command_handlers import (
    ChangeFtpPasswordHandler,
    CreateFtpAccountHandler,
    DeleteFtpAccountHandler,
    SetFtpDirectoryHandler,
    SetFtpQuotaHandler,
    SetFtpStatusHandler,
    UpdateFtpAccountHandler,
)
from controlbox.modules.ftp.application.commands import (
    ChangeFtpPasswordCommand,
    CreateFtpAccountCommand,
    DeleteFtpAccountCommand,
    SetFtpDirectoryCommand,
    SetFtpQuotaCommand,
    SetFtpStatusCommand,
    UpdateFtpAccountCommand,
)
from controlbox.modules.ftp.application.queries import FtpAccountResponse
from controlbox.modules.ftp.application.query_handlers import (
    GetFtpAccountHandler,
    GetFtpServiceStatusHandler,
    ListFtpAccountsHandler,
    ListFtpLogsHandler,
    to_account_response,
)
from controlbox.modules.ftp.application.queries import (
    GetFtpAccountQuery,
    ListFtpAccountsQuery,
    ListFtpLogsQuery,
)
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_current_context,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ForbiddenError
from controlbox.modules.ftp.domain.entities import FtpAccount
from controlbox.modules.ftp.infrastructure.service_manager import FtpServiceManager
from controlbox.shared.infrastructure.resource_isolation import can_manage_all_resources


router = APIRouter(prefix="/ftp", tags=["ftp"])


def _ftp_db_error_message(exc: Exception) -> str:
    text = str(exc).lower()
    if "owner_user_id" in text or "does not exist" in text or "undefinedcolumn" in text:
        return (
            "La base de datos necesita migraciones pendientes. "
            "En el VPS ejecute: controlbox repair"
        )
    return f"Error de base de datos: {exc}"


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _assert_account_access(context: RequestContext, account) -> None:
    if can_manage_all_resources(context):
        return
    if account.owner_user_id is None or account.owner_user_id != context.user_id:
        raise map_domain_exception(ForbiddenError("FTP account not found"))


def _to_schema(account: FtpAccountResponse) -> FtpAccountSchema:
    return FtpAccountSchema(
        id=account.id,
        tenant_id=account.tenant_id,
        username=account.username,
        system_username=account.system_username,
        home_directory=account.home_directory,
        status=account.status,
        quota_mb=account.quota_mb,
        max_files=account.max_files,
        upload_bandwidth_kbps=account.upload_bandwidth_kbps,
        download_bandwidth_kbps=account.download_bandwidth_kbps,
        last_login_at=account.last_login_at,
        error_message=account.error_message,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _to_service_schema(status) -> FtpServiceStatusSchema:
    return FtpServiceStatusSchema(
        enabled=status.enabled,
        status=status.status if hasattr(status, "status") else ("running" if getattr(status, "running", False) else "stopped"),
        host=getattr(status, "host", ""),
        port=getattr(status, "port", None),
        protocol=getattr(status, "protocol", "ftp"),
        passive_port_min=getattr(status, "passive_port_min", 30000),
        passive_port_max=getattr(status, "passive_port_max", 30009),
        public_host=getattr(status, "public_host", ""),
        running=getattr(status, "running", False),
        can_manage=getattr(status, "can_manage", False),
        message=getattr(status, "message", ""),
    )


@router.get("/status", response_model=FtpServiceStatusSchema)
async def get_ftp_status(
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
) -> FtpServiceStatusSchema:
    _require_tenant(context)
    status = await GetFtpServiceStatusHandler().handle()
    return _to_service_schema(status)


@router.put("/service", response_model=FtpServiceActionResponse)
async def configure_ftp_service(
    body: UpdateFtpServiceRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpServiceActionResponse:
    _require_tenant(context)
    manager = FtpServiceManager(get_settings())
    active_accounts: list[FtpAccount] = []
    if body.protocol == "sftp":
        try:
            async with uow:
                active_accounts = await uow.ftp_accounts.list_active()
        except SQLAlchemyError as exc:
            return FtpServiceActionResponse(
                success=False,
                message=_ftp_db_error_message(exc),
                service=_to_service_schema(await manager.get_config()),
            )
    ok, message, config = await manager.apply_config(
        enabled=body.enabled,
        protocol=body.protocol,
        port=body.port,
        passive_port_min=body.passive_port_min,
        passive_port_max=body.passive_port_max,
        public_host=body.public_host,
        sftp_accounts=active_accounts if body.protocol == "sftp" else None,
    )
    return FtpServiceActionResponse(success=ok, message=message, service=_to_service_schema(config))


@router.post("/service/start", response_model=FtpServiceActionResponse)
async def start_ftp_service(
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpServiceActionResponse:
    _require_tenant(context)
    manager = FtpServiceManager(get_settings())
    ok, message = await manager.start()
    config = await manager.get_config()
    return FtpServiceActionResponse(success=ok, message=message, service=_to_service_schema(config))


@router.post("/service/stop", response_model=FtpServiceActionResponse)
async def stop_ftp_service(
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpServiceActionResponse:
    _require_tenant(context)
    manager = FtpServiceManager(get_settings())
    ok, message = await manager.stop()
    config = await manager.get_config()
    return FtpServiceActionResponse(success=ok, message=message, service=_to_service_schema(config))


@router.get("/accounts", response_model=list[FtpAccountSchema])
async def list_ftp_accounts(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
) -> list[FtpAccountSchema]:
    tenant_id = _require_tenant(context)
    try:
        accounts = await ListFtpAccountsHandler(uow).handle(
            ListFtpAccountsQuery(
                tenant_id=tenant_id,
                requester_user_id=context.user_id,
                can_manage_all=can_manage_all_resources(context),
            )
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ftp_db_error_message(exc),
        ) from exc
    return [_to_schema(account) for account in accounts]


@router.post("/accounts", response_model=FtpAccountCreatedSchema, status_code=201)
async def create_ftp_account(
    body: CreateFtpAccountRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpAccountCreatedSchema:
    tenant_id = _require_tenant(context)
    account, password = await CreateFtpAccountHandler(uow).handle(
        CreateFtpAccountCommand(
            tenant_id=tenant_id,
            user_id=context.user_id,
            username=body.username,
            password=body.password,
            home_directory=body.home_directory,
            quota_mb=body.quota_mb,
            max_files=body.max_files,
            upload_bandwidth_kbps=body.upload_bandwidth_kbps,
            download_bandwidth_kbps=body.download_bandwidth_kbps,
        )
    )
    response = to_account_response(account)
    return FtpAccountCreatedSchema(**_to_schema(response).model_dump(), password=password)


@router.get("/accounts/{account_id}", response_model=FtpAccountSchema)
async def get_ftp_account(
    account_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
) -> FtpAccountSchema:
    tenant_id = _require_tenant(context)
    account = await GetFtpAccountHandler(uow).handle(
        GetFtpAccountQuery(
            tenant_id=tenant_id,
            account_id=account_id,
            requester_user_id=context.user_id,
            can_manage_all=can_manage_all_resources(context),
        )
    )
    return _to_schema(account)


@router.patch("/accounts/{account_id}", response_model=FtpAccountSchema)
async def update_ftp_account(
    account_id: UUID,
    body: UpdateFtpAccountRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpAccountSchema:
    tenant_id = _require_tenant(context)
    account_entity = await uow.ftp_accounts.get_by_id_and_tenant(account_id, tenant_id)
    if not account_entity:
        raise map_domain_exception(ForbiddenError("FTP account not found"))
    _assert_account_access(context, account_entity)
    account = await UpdateFtpAccountHandler(uow).handle(
        UpdateFtpAccountCommand(
            tenant_id=tenant_id,
            account_id=account_id,
            home_directory=body.home_directory,
            quota_mb=body.quota_mb,
            max_files=body.max_files,
            upload_bandwidth_kbps=body.upload_bandwidth_kbps,
            download_bandwidth_kbps=body.download_bandwidth_kbps,
        )
    )
    return _to_schema(to_account_response(account))


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_ftp_account(
    account_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> None:
    tenant_id = _require_tenant(context)
    account_entity = await uow.ftp_accounts.get_by_id_and_tenant(account_id, tenant_id)
    if not account_entity:
        raise map_domain_exception(ForbiddenError("FTP account not found"))
    _assert_account_access(context, account_entity)
    await DeleteFtpAccountHandler(uow).handle(
        DeleteFtpAccountCommand(tenant_id=tenant_id, account_id=account_id)
    )


@router.put("/accounts/{account_id}/password", response_model=FtpPasswordChangedSchema)
async def change_ftp_password(
    account_id: UUID,
    body: ChangeFtpPasswordRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpPasswordChangedSchema:
    tenant_id = _require_tenant(context)
    account_entity = await uow.ftp_accounts.get_by_id_and_tenant(account_id, tenant_id)
    if not account_entity:
        raise map_domain_exception(ForbiddenError("FTP account not found"))
    _assert_account_access(context, account_entity)
    account, password = await ChangeFtpPasswordHandler(uow).handle(
        ChangeFtpPasswordCommand(
            tenant_id=tenant_id,
            account_id=account_id,
            password=body.password,
        )
    )
    response = to_account_response(account)
    return FtpPasswordChangedSchema(account=_to_schema(response), password=password)


@router.put("/accounts/{account_id}/quota", response_model=FtpAccountSchema)
async def set_ftp_quota(
    account_id: UUID,
    body: SetFtpQuotaRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpAccountSchema:
    tenant_id = _require_tenant(context)
    account_entity = await uow.ftp_accounts.get_by_id_and_tenant(account_id, tenant_id)
    if not account_entity:
        raise map_domain_exception(ForbiddenError("FTP account not found"))
    _assert_account_access(context, account_entity)
    account = await SetFtpQuotaHandler(uow).handle(
        SetFtpQuotaCommand(
            tenant_id=tenant_id,
            account_id=account_id,
            quota_mb=body.quota_mb,
            max_files=body.max_files,
        )
    )
    return _to_schema(to_account_response(account))


@router.put("/accounts/{account_id}/directory", response_model=FtpAccountSchema)
async def set_ftp_directory(
    account_id: UUID,
    body: SetFtpDirectoryRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpAccountSchema:
    tenant_id = _require_tenant(context)
    account_entity = await uow.ftp_accounts.get_by_id_and_tenant(account_id, tenant_id)
    if not account_entity:
        raise map_domain_exception(ForbiddenError("FTP account not found"))
    _assert_account_access(context, account_entity)
    account = await SetFtpDirectoryHandler(uow).handle(
        SetFtpDirectoryCommand(
            tenant_id=tenant_id,
            account_id=account_id,
            home_directory=body.home_directory,
        )
    )
    return _to_schema(to_account_response(account))


@router.put("/accounts/{account_id}/status", response_model=FtpPasswordChangedSchema)
async def set_ftp_status(
    account_id: UUID,
    body: SetFtpStatusRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.manage"))],
) -> FtpPasswordChangedSchema:
    tenant_id = _require_tenant(context)
    account_entity = await uow.ftp_accounts.get_by_id_and_tenant(account_id, tenant_id)
    if not account_entity:
        raise map_domain_exception(ForbiddenError("FTP account not found"))
    _assert_account_access(context, account_entity)
    account, password = await SetFtpStatusHandler(uow).handle(
        SetFtpStatusCommand(
            tenant_id=tenant_id,
            account_id=account_id,
            status=body.status,
        )
    )
    return FtpPasswordChangedSchema(account=_to_schema(to_account_response(account)), password=password)


@router.get("/accounts/{account_id}/logs", response_model=list[FtpLogSchema])
async def get_ftp_account_logs(
    account_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[FtpLogSchema]:
    tenant_id = _require_tenant(context)
    logs = await ListFtpLogsHandler(uow).handle(
        ListFtpLogsQuery(
            tenant_id=tenant_id,
            account_id=account_id,
            limit=limit,
            requester_user_id=context.user_id,
            can_manage_all=can_manage_all_resources(context),
        )
    )
    return [FtpLogSchema(**log.__dict__) for log in logs]


@router.get("/logs", response_model=list[FtpLogSchema])
async def get_ftp_logs(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[FtpLogSchema]:
    tenant_id = _require_tenant(context)
    try:
        logs = await ListFtpLogsHandler(uow).handle(
            ListFtpLogsQuery(
                tenant_id=tenant_id,
                account_id=None,
                limit=limit,
                requester_user_id=context.user_id,
                can_manage_all=can_manage_all_resources(context),
            )
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ftp_db_error_message(exc),
        ) from exc
    return [FtpLogSchema(**log.__dict__) for log in logs]
