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
from controlbox.modules.mail.api.schemas import (
    CreateMailAccountRequest,
    CreateTenantMailServiceRequest,
    DnsRecordHintSchema,
    MailAccountCreatedSchema,
    MailAccountSchema,
    MailOverviewSchema,
    TenantMailServiceSchema,
    UpdateMailAccountRequest,
    UpdateTenantMailServiceRequest,
    VerifyTenantMailServiceRequest,
)
from controlbox.modules.mail.application.service import MailApplicationService
from controlbox.modules.mail.domain.entities import TenantMailService
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError


router = APIRouter(prefix="/mail", tags=["mail"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _service_schema(service: TenantMailService) -> TenantMailServiceSchema:
    return TenantMailServiceSchema(
        id=service.id,
        tenant_id=service.tenant_id,
        name=service.name,
        mail_domain=service.mail_domain,
        status=service.status.value,
        imap_host=service.imap_host,
        imap_port=service.imap_port,
        imap_use_ssl=service.imap_use_ssl,
        smtp_host=service.smtp_host,
        smtp_port=service.smtp_port,
        smtp_use_ssl=service.smtp_use_ssl,
        smtp_use_tls=service.smtp_use_tls,
        admin_username=service.admin_username,
        has_admin_password=bool(service.admin_password_enc),
        default_quota_mb=service.default_quota_mb,
        total_quota_mb=service.total_quota_mb,
        webmail_url=service.webmail_url,
        connection_verified_at=service.connection_verified_at,
        error_message=service.error_message,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def _account_schema(account) -> MailAccountSchema:
    return MailAccountSchema(
        id=account.id,
        tenant_id=account.tenant_id,
        mail_service_id=account.mail_service_id,
        local_part=account.local_part,
        email_address=account.email_address,
        display_name=account.display_name,
        status=account.status.value,
        quota_mb=account.quota_mb,
        used_mb=account.used_mb,
        forwarding_to=account.forwarding_to,
        error_message=account.error_message,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.get("/overview", response_model=MailOverviewSchema)
async def mail_overview(
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MailOverviewSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            return MailOverviewSchema(configured=False, accounts_count=0, total_quota_mb=0, total_used_mb=0)
        data = await service.get_overview(tenant_id, services[0].id)
        return MailOverviewSchema(**data)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/service", response_model=TenantMailServiceSchema | None)
async def get_mail_service_legacy(
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema | None:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        return _service_schema(services[0]) if services else None
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/service", response_model=TenantMailServiceSchema, status_code=status.HTTP_201_CREATED)
async def create_mail_service_legacy(
    body: CreateTenantMailServiceRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        row = await service.create_service(tenant_id, body.name, body.mail_domain)
        return _service_schema(row)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.patch("/service", response_model=TenantMailServiceSchema)
async def update_mail_service_legacy(
    body: UpdateTenantMailServiceRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            raise NotFoundError("No tenant mail service configured")
        row = await service.update_service(tenant_id, services[0].id, **body.model_dump(exclude_unset=True))
        return _service_schema(row)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/service/verify", response_model=TenantMailServiceSchema)
async def verify_mail_service_legacy(
    body: VerifyTenantMailServiceRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            raise NotFoundError("No tenant mail service configured")
        row = await service.verify_service(tenant_id, services[0].id, body.admin_password, body.force)
        return _service_schema(row)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/service", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mail_service_legacy(
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            raise NotFoundError("No tenant mail service configured")
        await service.delete_service(tenant_id, services[0].id)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/service/dns-hints", response_model=list[DnsRecordHintSchema])
async def mail_dns_hints_legacy(
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DnsRecordHintSchema]:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            return []
        rows = await service.dns_checklist(tenant_id, services[0].id)
        return [DnsRecordHintSchema(**row) for row in rows]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/accounts", response_model=list[MailAccountSchema])
async def list_mail_accounts_legacy(
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[MailAccountSchema]:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            return []
        accounts = await service.list_accounts(tenant_id, services[0].id)
        return [_account_schema(a) for a in accounts]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/accounts", response_model=MailAccountCreatedSchema, status_code=status.HTTP_201_CREATED)
async def create_mail_account_legacy(
    body: CreateMailAccountRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MailAccountCreatedSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            raise NotFoundError("No tenant mail service configured")
        account, password = await service.create_account(
            tenant_id,
            services[0].id,
            local_part=body.local_part,
            display_name=body.display_name,
            password=body.password,
            quota_mb=body.quota_mb,
        )
        return MailAccountCreatedSchema(**_account_schema(account).model_dump(), password=password)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.patch("/accounts/{account_id}", response_model=MailAccountSchema)
async def update_mail_account_legacy(
    account_id: UUID,
    body: UpdateMailAccountRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MailAccountSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            raise NotFoundError("No tenant mail service configured")
        account = await service.update_account(
            tenant_id,
            services[0].id,
            account_id,
            **body.model_dump(exclude_unset=True),
        )
        return _account_schema(account)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mail_account_legacy(
    account_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        services = await service.list_services(tenant_id)
        if not services:
            raise NotFoundError("No tenant mail service configured")
        await service.delete_account(tenant_id, services[0].id, account_id)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


# --- Nuevas rutas Multi-Tenant Email ---

@router.get("/services", response_model=list[TenantMailServiceSchema])
async def list_mail_services(
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[TenantMailServiceSchema]:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        rows = await service.list_services(tenant_id)
        return [_service_schema(r) for r in rows]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/services/{service_id}", response_model=TenantMailServiceSchema | None)
async def get_mail_service(
    service_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema | None:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        row = await service.get_service(tenant_id, service_id)
        return _service_schema(row) if row else None
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/services", response_model=TenantMailServiceSchema, status_code=status.HTTP_201_CREATED)
async def create_mail_service(
    body: CreateTenantMailServiceRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        row = await service.create_service(tenant_id, body.name, body.mail_domain)
        return _service_schema(row)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.patch("/services/{service_id}", response_model=TenantMailServiceSchema)
async def update_mail_service(
    service_id: UUID,
    body: UpdateTenantMailServiceRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        row = await service.update_service(tenant_id, service_id, **body.model_dump(exclude_unset=True))
        return _service_schema(row)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/services/{service_id}/verify", response_model=TenantMailServiceSchema)
async def verify_mail_service(
    service_id: UUID,
    body: VerifyTenantMailServiceRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantMailServiceSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        row = await service.verify_service(tenant_id, service_id, body.admin_password, body.force)
        return _service_schema(row)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mail_service(
    service_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        await service.delete_service(tenant_id, service_id)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/services/{service_id}/dns-hints", response_model=list[DnsRecordHintSchema])
async def mail_dns_hints(
    service_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DnsRecordHintSchema]:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        rows = await service.dns_checklist(tenant_id, service_id)
        return [DnsRecordHintSchema(**row) for row in rows]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/services/{service_id}/overview", response_model=MailOverviewSchema)
async def mail_service_overview(
    service_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MailOverviewSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        data = await service.get_overview(tenant_id, service_id)
        return MailOverviewSchema(**data)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/services/{service_id}/accounts", response_model=list[MailAccountSchema])
async def list_mail_accounts(
    service_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[MailAccountSchema]:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        accounts = await service.list_accounts(tenant_id, service_id)
        return [_account_schema(a) for a in accounts]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/services/{service_id}/accounts", response_model=MailAccountCreatedSchema, status_code=status.HTTP_201_CREATED)
async def create_mail_account(
    service_id: UUID,
    body: CreateMailAccountRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MailAccountCreatedSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        account, password = await service.create_account(
            tenant_id,
            service_id,
            local_part=body.local_part,
            display_name=body.display_name,
            password=body.password,
            quota_mb=body.quota_mb,
        )
        return MailAccountCreatedSchema(**_account_schema(account).model_dump(), password=password)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.patch("/services/{service_id}/accounts/{account_id}", response_model=MailAccountSchema)
async def update_mail_account(
    service_id: UUID,
    account_id: UUID,
    body: UpdateMailAccountRequest,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MailAccountSchema:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        account = await service.update_account(
            tenant_id,
            service_id,
            account_id,
            **body.model_dump(exclude_unset=True),
        )
        return _account_schema(account)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/services/{service_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mail_account(
    service_id: UUID,
    account_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("mail.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    service = MailApplicationService(uow, get_settings())
    try:
        await service.delete_account(tenant_id, service_id, account_id)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
