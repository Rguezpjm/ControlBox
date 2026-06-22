from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from controlbox.modules.ftp.api.schemas import (
    ChangeFtpPasswordRequest,
    CreateFtpAccountRequest,
    FtpAccountCreatedSchema,
    FtpAccountSchema,
    FtpLogSchema,
    FtpPasswordChangedSchema,
    FtpServiceStatusSchema,
    SetFtpDirectoryRequest,
    SetFtpQuotaRequest,
    SetFtpStatusRequest,
    UpdateFtpAccountRequest,
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


router = APIRouter(prefix="/ftp", tags=["ftp"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


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


@router.get("/status", response_model=FtpServiceStatusSchema)
async def get_ftp_status(
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
) -> FtpServiceStatusSchema:
    _require_tenant(context)
    status = await GetFtpServiceStatusHandler().handle()
    return FtpServiceStatusSchema(
        enabled=status.enabled,
        status=status.status,
        host=status.host,
        port=status.port,
    )


@router.get("/accounts", response_model=list[FtpAccountSchema])
async def list_ftp_accounts(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[None, Depends(require_permission("ftp.read"))],
) -> list[FtpAccountSchema]:
    tenant_id = _require_tenant(context)
    accounts = await ListFtpAccountsHandler(uow).handle(ListFtpAccountsQuery(tenant_id=tenant_id))
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
        GetFtpAccountQuery(tenant_id=tenant_id, account_id=account_id)
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
        ListFtpLogsQuery(tenant_id=tenant_id, account_id=account_id, limit=limit)
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
    logs = await ListFtpLogsHandler(uow).handle(
        ListFtpLogsQuery(tenant_id=tenant_id, account_id=None, limit=limit)
    )
    return [FtpLogSchema(**log.__dict__) for log in logs]
