from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request, Response, status

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
from controlbox.modules.identity.api.schemas import (
    AssignRoleRequest,
    AuditLogResponseSchema,
    CreateRoleRequest,
    CreateUserRequest,
    LiteUserResponseSchema,
    LoginRequest,
    PermissionResponseSchema,
    RefreshTokenRequest,
    RegisterTenantRequest,
    RegisterTenantResponseSchema,
    RoleResponseSchema,
    SessionResponseSchema,
    TenantResponseSchema,
    TokenResponseSchema,
    UserResponseSchema,
)
from controlbox.modules.security.api.schemas import LoginResponseSchema
from controlbox.modules.security.application.queries import MfaChallengeResponse
from controlbox.modules.security.application.security_events import SecurityEventRecorder
from controlbox.modules.security.domain.services import MfaChallengeStore, MfaService
from controlbox.shared.infrastructure.security.cookies import (
    clear_refresh_cookie,
    get_refresh_token_from_request,
    set_access_cookie,
    set_csrf_cookie,
    set_refresh_cookie,
)
from controlbox.shared.infrastructure.security.protection import CsrfProtection, IpReputation
from controlbox.modules.identity.application.command_handlers import (
    AssignRoleHandler,
    CreateRoleHandler,
    CreateUserHandler,
    LoginHandler,
    LogoutHandler,
    RefreshTokenHandler,
    RegisterTenantHandler,
    RevokeAllSessionsHandler,
)
from controlbox.modules.identity.application.commands import (
    AssignRoleCommand,
    CreateRoleCommand,
    CreateUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
    RegisterTenantCommand,
    RevokeAllSessionsCommand,
)
from controlbox.modules.identity.application.query_handlers import (
    GetCurrentUserHandler,
    GetTenantHandler,
    ListAuditLogsHandler,
    ListPermissionsHandler,
    ListSessionsHandler,
    ListTenantsHandler,
    ListUsersByTenantHandler,
)
from controlbox.modules.identity.application.queries import (
    GetCurrentUserQuery,
    GetTenantQuery,
    ListAuditLogsQuery,
    ListPermissionsQuery,
    ListSessionsQuery,
    ListTenantsQuery,
    ListUsersByTenantQuery,
)
from controlbox.modules.identity.domain.services import PasswordService, SessionService
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError, NotFoundError, utc_now


router = APIRouter(prefix="/identity", tags=["identity"])


def _access_cookie_ttl_seconds(expires_at) -> int:
    return max(60, int((expires_at - utc_now()).total_seconds()))


async def _issue_csrf(response: Response, container: AppState, session_id: str) -> str:
    token = await CsrfProtection(container.redis_client).issue_token(session_id)
    set_csrf_cookie(response, token, container.settings)
    return token


@router.post("/tenants/register", response_model=RegisterTenantResponseSchema, status_code=status.HTTP_201_CREATED)
async def register_tenant(
    payload: RegisterTenantRequest,
    response: Response,
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RegisterTenantResponseSchema:
    settings = container.settings
    if not settings.registration_enabled:
        raise map_domain_exception(ForbiddenError("Registration is disabled"))
    if settings.registration_invite_token and payload.invite_token != settings.registration_invite_token:
        raise map_domain_exception(ForbiddenError("Invalid invite token"))
    try:
        handler = RegisterTenantHandler(
            uow=uow,
            password_service=PasswordService(),
            token_service=container.token_service,
            session_service=SessionService(container.token_service),
            session_cache=container.session_cache,
        )
        tenant, user, tokens = await handler.handle(
            RegisterTenantCommand(
                name=payload.name,
                slug=payload.slug,
                admin_email=str(payload.admin_email),
                admin_password=payload.admin_password,
                admin_full_name=payload.admin_full_name,
            )
        )
        set_refresh_cookie(response, tokens.refresh_token, container.settings)
        set_access_cookie(
            response,
            tokens.access_token,
            container.settings,
            max_age_seconds=_access_cookie_ttl_seconds(tokens.access_token_expires_at),
        )
        return RegisterTenantResponseSchema(
            tenant=TenantResponseSchema(**tenant.__dict__),
            user=UserResponseSchema(**user.__dict__),
            tokens=TokenResponseSchema(**tokens.__dict__),
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/auth/login", response_model=LoginResponseSchema)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LoginResponseSchema:
    try:
        handler = LoginHandler(
            uow=uow,
            password_service=PasswordService(),
            token_service=container.token_service,
            session_service=SessionService(container.token_service),
            session_cache=container.session_cache,
            settings=container.settings,
            ip_reputation=IpReputation(container.redis_client),
            mfa_service=MfaService(container.settings),
            challenge_store=MfaChallengeStore(container.redis_client),
            events=SecurityEventRecorder(),
        )
        result = await handler.handle(
            LoginCommand(
                email=str(payload.email),
                password=payload.password,
                tenant_slug=payload.tenant_slug,
                user_agent=get_user_agent(request),
                ip_address=get_client_ip(request),
                device_fingerprint=payload.device_fingerprint,
            )
        )
        if isinstance(result, MfaChallengeResponse):
            return LoginResponseSchema(
                mfa_required=True,
                challenge_token=result.challenge_token,
                methods=result.methods,
            )
        set_refresh_cookie(response, result.refresh_token, container.settings)
        set_access_cookie(
            response,
            result.access_token,
            container.settings,
            max_age_seconds=_access_cookie_ttl_seconds(result.access_token_expires_at),
        )
        csrf = await _issue_csrf(response, container, str(result.session_id))
        return LoginResponseSchema(
            access_token=result.access_token,
            refresh_token=None,
            token_type=result.token_type,
            access_token_expires_at=result.access_token_expires_at,
            refresh_token_expires_at=result.refresh_token_expires_at,
            session_id=result.session_id,
            csrf_token=csrf,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/auth/refresh", response_model=TokenResponseSchema)
async def refresh_token(
    request: Request,
    response: Response,
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[RefreshTokenRequest | None, Body()] = None,
) -> TokenResponseSchema:
    try:
        refresh_token_value = (payload.refresh_token if payload else None) or get_refresh_token_from_request(request)
        if not refresh_token_value:
            raise map_domain_exception(NotFoundError("Invalid refresh token"))
        handler = RefreshTokenHandler(
            uow=uow,
            token_service=container.token_service,
            session_service=SessionService(container.token_service),
            session_cache=container.session_cache,
        )
        tokens = await handler.handle(
            RefreshTokenCommand(
                refresh_token=refresh_token_value,
                user_agent=get_user_agent(request),
                ip_address=get_client_ip(request),
                device_fingerprint=payload.device_fingerprint if payload else None,
            )
        )
        set_refresh_cookie(response, tokens.refresh_token, container.settings)
        set_access_cookie(
            response,
            tokens.access_token,
            container.settings,
            max_age_seconds=_access_cookie_ttl_seconds(tokens.access_token_expires_at),
        )
        await _issue_csrf(response, container, str(tokens.session_id))
        return TokenResponseSchema(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            access_token_expires_at=tokens.access_token_expires_at,
            refresh_token_expires_at=tokens.refresh_token_expires_at,
            session_id=tokens.session_id,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    context: Annotated[RequestContext, Depends(get_current_context)],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        handler = LogoutHandler(uow=uow, session_cache=container.session_cache)
        await handler.handle(
            LogoutCommand(
                session_id=context.session_id,
                user_id=context.user_id,
                access_token_jti=context.jti,
                access_token_exp=context.token_exp,
            )
        )
        clear_refresh_cookie(response, container.settings)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/auth/sessions/revoke-all", status_code=status.HTTP_200_OK)
async def revoke_all_sessions(
    context: Annotated[RequestContext, Depends(require_permission("sessions.manage"))],
    container: Annotated[AppState, Depends(get_app_state)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict[str, int]:
    try:
        handler = RevokeAllSessionsHandler(uow=uow, session_cache=container.session_cache)
        count = await handler.handle(
            RevokeAllSessionsCommand(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
            )
        )
        return {"revoked_count": count}
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/auth/me", response_model=UserResponseSchema)
async def get_me(
    context: Annotated[RequestContext, Depends(get_current_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UserResponseSchema:
    try:
        handler = GetCurrentUserHandler(uow=uow)
        user = await handler.handle(
            GetCurrentUserQuery(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
            )
        )
        return UserResponseSchema(**user.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/tenants/{tenant_id}", response_model=TenantResponseSchema)
async def get_tenant(
    tenant_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("tenants.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantResponseSchema:
    if context.tenant_id and context.tenant_id != tenant_id and "admin" not in context.roles:
        raise map_domain_exception(ForbiddenError("Forbidden"))
    try:
        handler = GetTenantHandler(uow=uow)
        tenant = await handler.handle(GetTenantQuery(tenant_id=tenant_id))
        return TenantResponseSchema(**tenant.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/tenants", response_model=list[TenantResponseSchema])
async def list_tenants(
    context: Annotated[RequestContext, Depends(require_permission("tenants.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[TenantResponseSchema]:
    try:
        handler = ListTenantsHandler(uow=uow)
        tenants = await handler.handle(ListTenantsQuery())
        return [TenantResponseSchema(**t.__dict__) for t in tenants]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/tenants/{tenant_id}/lite-users", response_model=list[LiteUserResponseSchema])
async def list_tenant_users(
    tenant_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("tenants.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[LiteUserResponseSchema]:
    if context.tenant_id and context.tenant_id != tenant_id and "admin" not in context.roles:
        raise map_domain_exception(ForbiddenError("Forbidden"))
    try:
        handler = ListUsersByTenantHandler(uow=uow)
        users = await handler.handle(ListUsersByTenantQuery(tenant_id=tenant_id))
        return [LiteUserResponseSchema(**u.__dict__) for u in users]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/tenants/{tenant_id}/users", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    tenant_id: UUID,
    payload: CreateUserRequest,
    context: Annotated[RequestContext, Depends(require_permission("users.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UserResponseSchema:
    if context.tenant_id and context.tenant_id != tenant_id:
        raise map_domain_exception(ForbiddenError("Forbidden"))
    try:
        handler = CreateUserHandler(uow=uow, password_service=PasswordService())
        user = await handler.handle(
            CreateUserCommand(
                tenant_id=tenant_id,
                email=str(payload.email),
                password=payload.password,
                full_name=payload.full_name,
                role_name=payload.role_name,
            )
        )
        return UserResponseSchema(**user.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/tenants/{tenant_id}/roles", response_model=RoleResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_role(
    tenant_id: UUID,
    payload: CreateRoleRequest,
    context: Annotated[RequestContext, Depends(require_permission("roles.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RoleResponseSchema:
    if context.tenant_id and context.tenant_id != tenant_id:
        raise map_domain_exception(ForbiddenError("Forbidden"))
    try:
        handler = CreateRoleHandler(uow=uow)
        role = await handler.handle(
            CreateRoleCommand(
                tenant_id=tenant_id,
                name=payload.name,
                description=payload.description,
                permission_codes=payload.permission_codes,
            )
        )
        return RoleResponseSchema(**role.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/tenants/{tenant_id}/users/{user_id}/roles", response_model=UserResponseSchema)
async def assign_role(
    tenant_id: UUID,
    user_id: UUID,
    payload: AssignRoleRequest,
    context: Annotated[RequestContext, Depends(require_permission("users.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UserResponseSchema:
    if context.tenant_id and context.tenant_id != tenant_id:
        raise map_domain_exception(ForbiddenError("Forbidden"))
    try:
        handler = AssignRoleHandler(uow=uow)
        user = await handler.handle(
            AssignRoleCommand(
                user_id=user_id,
                role_id=payload.role_id,
                tenant_id=tenant_id,
            )
        )
        return UserResponseSchema(**user.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/auth/sessions", response_model=list[SessionResponseSchema])
async def list_sessions(
    context: Annotated[RequestContext, Depends(require_permission("sessions.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[SessionResponseSchema]:
    try:
        handler = ListSessionsHandler(uow=uow)
        sessions = await handler.handle(ListSessionsQuery(user_id=context.user_id))
        return [SessionResponseSchema(**session.__dict__) for session in sessions]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/tenants/{tenant_id}/audit-logs", response_model=list[AuditLogResponseSchema])
async def list_audit_logs(
    tenant_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("audit.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLogResponseSchema]:
    if context.tenant_id and context.tenant_id != tenant_id:
        raise map_domain_exception(ForbiddenError("Forbidden"))
    try:
        handler = ListAuditLogsHandler(uow=uow)
        logs = await handler.handle(
            ListAuditLogsQuery(tenant_id=tenant_id, limit=min(limit, 100), offset=offset)
        )
        return [AuditLogResponseSchema(**log.__dict__) for log in logs]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/permissions", response_model=list[PermissionResponseSchema])
async def list_permissions(
    context: Annotated[RequestContext, Depends(require_permission("roles.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[PermissionResponseSchema]:
    try:
        handler = ListPermissionsHandler(uow=uow)
        permissions = await handler.handle(ListPermissionsQuery())
        return [PermissionResponseSchema(**permission.__dict__) for permission in permissions]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
