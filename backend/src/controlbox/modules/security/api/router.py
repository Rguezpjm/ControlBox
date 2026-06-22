from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from controlbox.config.settings import Settings
from controlbox.modules.identity.api.dependencies import (
    AppState,
    get_app_state,
    get_client_ip,
    get_current_context,
    get_unit_of_work,
    get_user_agent,
    map_domain_exception,
    require_permission,
    RequestContext,
)
from controlbox.modules.identity.api.schemas import TokenResponseSchema
from controlbox.modules.identity.domain.services import SessionService
from controlbox.modules.security.api.schemas import (
    BlockedIpSchema,
    CsrfTokenResponseSchema,
    DisableMfaRequest,
    EnableMfaRequest,
    MfaSetupResponseSchema,
    MfaVerifyRequest,
    PasskeySchema,
    SecurityEventSchema,
    SecurityOverviewSchema,
    SecuritySettingsSchema,
    TrustedDeviceSchema,
    UpdateSecuritySettingsRequest,
    WebAuthnLoginBeginRequest,
    WebAuthnLoginVerifyRequest,
    WebAuthnRegisterRequest,
)
from controlbox.modules.security.application.command_handlers import (
    DisableMfaHandler,
    EnableMfaHandler,
    RevokeTrustedDeviceHandler,
    SetupMfaHandler,
    UnblockIpHandler,
    UpdateSecuritySettingsHandler,
    VerifyMfaLoginHandler,
)
from controlbox.modules.security.application.commands import (
    DisableMfaCommand,
    EnableMfaCommand,
    RevokeTrustedDeviceCommand,
    SetupMfaCommand,
    UnblockIpCommand,
    UpdateSecuritySettingsCommand,
    VerifyMfaLoginCommand,
)
from controlbox.modules.security.application.query_handlers import (
    GetSecurityOverviewHandler,
    GetSecuritySettingsHandler,
    ListPasskeysHandler,
    ListSecurityEventsHandler,
    ListTrustedDevicesHandler,
)
from controlbox.modules.security.application.queries import (
    GetSecurityOverviewQuery,
    GetSecuritySettingsQuery,
    ListPasskeysQuery,
    ListSecurityEventsQuery,
    ListTrustedDevicesQuery,
)
from controlbox.modules.security.application.security_events import SecurityEventRecorder
from controlbox.modules.security.domain.services import MfaChallengeStore, MfaService, WebAuthnChallengeStore
from controlbox.modules.security.domain.webauthn_service import WebAuthnService
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, NotFoundError
from controlbox.shared.infrastructure.security.cookies import set_access_cookie, set_csrf_cookie, set_refresh_cookie
from controlbox.shared.infrastructure.security.protection import CsrfProtection, IpReputation

router = APIRouter(prefix="/security", tags=["security"])


def _mfa_service(container: AppState) -> MfaService:
    return MfaService(container.settings)


def _challenge_store(container: AppState) -> MfaChallengeStore:
    return MfaChallengeStore(container.redis_client)


def _webauthn_service(container: AppState) -> WebAuthnService:
    return WebAuthnService(container.settings, WebAuthnChallengeStore(container.redis_client))


def _ip_reputation(container: AppState) -> IpReputation:
    return IpReputation(container.redis_client)


def _csrf(container: AppState) -> CsrfProtection:
    return CsrfProtection(container.redis_client)


@router.get("/overview", response_model=SecurityOverviewSchema)
async def security_overview(
    context: Annotated[RequestContext, Depends(require_permission("security.read"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SecurityOverviewSchema:
    if not context.tenant_id:
        raise map_domain_exception(NotFoundError("Tenant not found"))
    handler = GetSecurityOverviewHandler(uow=uow, ip_reputation=_ip_reputation(container))
    overview = await handler.handle(GetSecurityOverviewQuery(tenant_id=context.tenant_id))
    return SecurityOverviewSchema(**overview.__dict__)


@router.get("/events", response_model=list[SecurityEventSchema])
async def list_security_events(
    context: Annotated[RequestContext, Depends(require_permission("security.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[SecurityEventSchema]:
    if not context.tenant_id:
        raise map_domain_exception(NotFoundError("Tenant not found"))
    handler = ListSecurityEventsHandler(uow=uow)
    events = await handler.handle(
        ListSecurityEventsQuery(tenant_id=context.tenant_id, limit=min(limit, 100), offset=offset)
    )
    return [SecurityEventSchema(**e.__dict__) for e in events]


@router.get("/settings", response_model=SecuritySettingsSchema)
async def get_security_settings(
    context: Annotated[RequestContext, Depends(require_permission("security.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SecuritySettingsSchema:
    if not context.tenant_id:
        raise map_domain_exception(NotFoundError("Tenant not found"))
    handler = GetSecuritySettingsHandler(uow=uow)
    settings = await handler.handle(GetSecuritySettingsQuery(tenant_id=context.tenant_id))
    return SecuritySettingsSchema(**settings)


@router.patch("/settings", response_model=SecuritySettingsSchema)
async def update_security_settings(
    payload: UpdateSecuritySettingsRequest,
    context: Annotated[RequestContext, Depends(require_permission("security.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SecuritySettingsSchema:
    if not context.tenant_id:
        raise map_domain_exception(NotFoundError("Tenant not found"))
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        handler = UpdateSecuritySettingsHandler(uow=uow, events=SecurityEventRecorder())
        settings = await handler.handle(
            UpdateSecuritySettingsCommand(tenant_id=context.tenant_id, settings=updates)
        )
        return SecuritySettingsSchema(**settings)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/blocked-ips", response_model=list[BlockedIpSchema])
async def list_blocked_ips(
    context: Annotated[RequestContext, Depends(require_permission("security.read"))],
    container: Annotated[AppState, Depends(get_app_state)],
) -> list[BlockedIpSchema]:
    blocked = await _ip_reputation(container).list_blocked_ips()
    return [BlockedIpSchema(**item) for item in blocked]


@router.delete("/blocked-ips/{ip}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_ip(
    ip: str,
    context: Annotated[RequestContext, Depends(require_permission("security.manage"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        handler = UnblockIpHandler(
            ip_reputation=_ip_reputation(container),
            uow=uow,
            events=SecurityEventRecorder(),
        )
        await handler.handle(UnblockIpCommand(ip=ip, tenant_id=context.tenant_id))
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/csrf-token", response_model=CsrfTokenResponseSchema)
async def get_csrf_token(
    request: Request,
    response: Response,
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
) -> CsrfTokenResponseSchema:
    csrf = _csrf(container)
    token = await csrf.issue_token(str(context.session_id))
    set_csrf_cookie(response, token, container.settings)
    return CsrfTokenResponseSchema(csrf_token=token)


@router.post("/mfa/setup", response_model=MfaSetupResponseSchema)
async def setup_mfa(
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> MfaSetupResponseSchema:
    user = await uow.users.get_by_id(context.user_id)
    if user is None:
        raise map_domain_exception(NotFoundError("User not found"))
    handler = SetupMfaHandler(uow=uow, mfa_service=_mfa_service(container))
    result = await handler.handle(SetupMfaCommand(user_id=context.user_id, email=user.email))
    return MfaSetupResponseSchema(**result.__dict__)


@router.post("/mfa/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable_mfa(
    payload: EnableMfaRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        handler = EnableMfaHandler(uow=uow, mfa_service=_mfa_service(container), events=SecurityEventRecorder())
        await handler.handle(
            EnableMfaCommand(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                code=payload.code,
                secret=payload.secret,
                backup_codes=payload.backup_codes,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    payload: DisableMfaRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        handler = DisableMfaHandler(uow=uow, mfa_service=_mfa_service(container), events=SecurityEventRecorder())
        await handler.handle(
            DisableMfaCommand(user_id=context.user_id, tenant_id=context.tenant_id, code=payload.code)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/mfa/verify", response_model=TokenResponseSchema)
async def verify_mfa_login(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TokenResponseSchema:
    try:
        handler = VerifyMfaLoginHandler(
            uow=uow,
            mfa_service=_mfa_service(container),
            challenge_store=_challenge_store(container),
            token_service=container.token_service,
            session_service=SessionService(container.token_service),
            session_cache=container.session_cache,
            events=SecurityEventRecorder(),
        )
        tokens = await handler.handle(
            VerifyMfaLoginCommand(
                challenge_token=payload.challenge_token,
                code=payload.code,
                user_agent=get_user_agent(request),
                ip_address=get_client_ip(request),
                device_fingerprint=payload.device_fingerprint,
            )
        )
        set_refresh_cookie(response, tokens.refresh_token, container.settings)
        set_access_cookie(response, tokens.access_token, container.settings)
        return TokenResponseSchema(**tokens.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/devices", response_model=list[TrustedDeviceSchema])
async def list_devices(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[TrustedDeviceSchema]:
    handler = ListTrustedDevicesHandler(uow=uow)
    devices = await handler.handle(ListTrustedDevicesQuery(user_id=context.user_id))
    return [TrustedDeviceSchema(**d.__dict__) for d in devices]


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: UUID,
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        handler = RevokeTrustedDeviceHandler(uow=uow, events=SecurityEventRecorder())
        await handler.handle(
            RevokeTrustedDeviceCommand(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                device_id=device_id,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/passkeys", response_model=list[PasskeySchema])
async def list_passkeys(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[PasskeySchema]:
    handler = ListPasskeysHandler(uow=uow)
    passkeys = await handler.handle(ListPasskeysQuery(user_id=context.user_id))
    return [PasskeySchema(**p.__dict__) for p in passkeys]


@router.get("/webauthn/register/options")
async def webauthn_register_options(
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    user = await uow.users.get_by_id(context.user_id)
    if user is None:
        raise map_domain_exception(NotFoundError("User not found"))
    existing = await uow.webauthn_credentials.list_by_user(context.user_id)
    service = _webauthn_service(container)
    return await service.registration_options(context.user_id, user.email, existing)


@router.post("/webauthn/register/verify", status_code=status.HTTP_201_CREATED)
async def webauthn_register_verify(
    payload: WebAuthnRegisterRequest,
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> PasskeySchema:
    try:
        service = _webauthn_service(container)
        credential = await service.verify_registration(
            context.user_id, payload.credential, payload.nickname
        )
        await uow.webauthn_credentials.add(credential)
        await SecurityEventRecorder().record(
            uow,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            event_type="passkey_registered",
            severity="medium",
            message=f"Passkey '{payload.nickname}' registered",
        )
        await uow.commit()
        return PasskeySchema(
            id=credential.id,
            nickname=credential.nickname,
            transports=credential.transports,
            last_used_at=credential.last_used_at,
            created_at=credential.created_at,
        )
    except (DomainException, ValueError) as exc:
        if isinstance(exc, DomainException):
            raise map_domain_exception(exc) from exc
        raise map_domain_exception(NotFoundError(str(exc))) from exc


@router.post("/webauthn/login/options")
async def webauthn_login_options(
    payload: WebAuthnLoginBeginRequest,
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    tenant_id = None
    if payload.tenant_slug:
        tenant = await uow.tenants.get_by_slug(payload.tenant_slug)
        if tenant:
            tenant_id = tenant.id
    user = await uow.users.get_by_email(payload.email, tenant_id)
    if user is None:
        raise map_domain_exception(NotFoundError("User not found"))
    creds = await uow.webauthn_credentials.list_by_user(user.id)
    if not creds:
        raise map_domain_exception(NotFoundError("No passkeys registered"))
    service = _webauthn_service(container)
    return await service.authentication_options(user.id, creds)


@router.post("/webauthn/login/verify", response_model=TokenResponseSchema)
async def webauthn_login_verify(
    payload: WebAuthnLoginVerifyRequest,
    request: Request,
    response: Response,
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TokenResponseSchema:
    from controlbox.modules.identity.domain.services import SessionService, TokenService
    from controlbox.modules.security.application.command_handlers import _upsert_trusted_device
    from controlbox.modules.team_members.application.auth_resolver import resolve_effective_auth
    from controlbox.shared.infrastructure.security.audit import record_audit

    tenant_id = None
    if payload.tenant_slug:
        tenant = await uow.tenants.get_by_slug(payload.tenant_slug)
        if tenant:
            tenant_id = tenant.id
    user = await uow.users.get_by_email(payload.email, tenant_id)
    if user is None:
        raise map_domain_exception(NotFoundError("User not found"))

    cred_id = payload.credential.get("id", "")
    stored = await uow.webauthn_credentials.get_by_credential_id(cred_id)
    if stored is None or stored.user_id != user.id:
        raise map_domain_exception(NotFoundError("Credential not found"))

    try:
        service = _webauthn_service(container)
        updated = await service.verify_authentication(payload.credential, stored)
        await uow.webauthn_credentials.save(updated)

        session_service = SessionService(container.token_service)
        session, refresh_token = session_service.create_session(
            user=user,
            user_agent=get_user_agent(request),
            ip_address=get_client_ip(request),
            device_fingerprint=payload.device_fingerprint,
        )
        await uow.sessions.add(session)

        if payload.device_fingerprint:
            await _upsert_trusted_device(
                uow, user.id, payload.device_fingerprint, get_user_agent(request), get_client_ip(request)
            )

        role_names, permission_codes = await resolve_effective_auth(uow, user.id, user.tenant_id)
        access_token, access_expires = container.token_service.create_access_token(
            user=user,
            session_id=session.id,
            roles=role_names,
            permissions=permission_codes,
        )
        await container.session_cache.store_session(
            session_id=session.id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            ttl_seconds=container.session_cache.refresh_ttl_seconds(),
        )
        await record_audit(
            uow,
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.login",
            resource_type="session",
            resource_id=str(session.id),
            metadata={"webauthn": True},
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        await SecurityEventRecorder().record(
            uow,
            tenant_id=user.tenant_id,
            user_id=user.id,
            event_type="login_success",
            severity="low",
            message="Successful passkey login",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        await uow.commit()

        set_refresh_cookie(response, refresh_token, container.settings)
        set_access_cookie(response, access_token, container.settings)
        return TokenResponseSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            access_token_expires_at=access_expires,
            refresh_token_expires_at=session.expires_at,
            session_id=session.id,
        )
    except ValueError as exc:
        raise map_domain_exception(NotFoundError(str(exc))) from exc
