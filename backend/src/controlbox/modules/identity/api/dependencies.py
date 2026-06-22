from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.identity.domain.services import TokenService
from controlbox.modules.identity.infrastructure.unit_of_work import Database
from controlbox.shared.domain.base import DomainException, UnauthorizedError
from controlbox.shared.infrastructure.redis.client import RedisClient, SessionCache
from controlbox.shared.infrastructure.security.cookies import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME


security_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class RequestContext:
    user_id: UUID
    tenant_id: UUID | None
    session_id: UUID
    roles: list[str]
    permissions: list[str]
    jti: str
    token_exp: int
    is_platform_admin: bool = False


class AppState:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        redis_client: RedisClient,
        session_cache: SessionCache,
        token_service: TokenService,
    ) -> None:
        self.settings = settings
        self.database = database
        self.redis_client = redis_client
        self.session_cache = session_cache
        self.token_service = token_service


def get_app_state(request: Request) -> AppState:
    return request.app.state.container


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.container.settings


async def get_unit_of_work(request: Request):
    database: Database = request.app.state.container.database
    async with database.unit_of_work() as uow:
        yield uow


async def get_optional_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> RequestContext | None:
    token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None

    container: AppState = request.app.state.container
    token_service: TokenService = container.token_service
    session_cache: SessionCache = container.session_cache

    try:
        claims = token_service.decode_access_token(token)
    except UnauthorizedError:
        return None

    if await session_cache.is_access_token_blacklisted(claims.jti):
        return None

    session_id = UUID(claims.session_id)
    if not await session_cache.is_session_active(session_id):
        return None

    tenant_id = UUID(claims.tenant_id) if claims.tenant_id else None
    if x_tenant_id:
        header_tenant_id = UUID(x_tenant_id)
        if tenant_id and tenant_id != header_tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    return RequestContext(
        user_id=UUID(claims.sub),
        tenant_id=tenant_id,
        session_id=session_id,
        roles=claims.roles,
        permissions=claims.permissions,
        jti=claims.jti,
        token_exp=claims.exp,
        is_platform_admin=claims.is_platform_admin,
    )


async def get_current_context(
    context: Annotated[RequestContext | None, Depends(get_optional_context)],
) -> RequestContext:
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return context


PLATFORM_ADMIN_ROLES = frozenset({"admin", "owner", "administrator"})


def require_permission(permission: str):
    async def dependency(context: Annotated[RequestContext, Depends(get_current_context)]) -> RequestContext:
        if context.is_platform_admin:
            return context
        if permission in context.permissions:
            return context
        if any(role in PLATFORM_ADMIN_ROLES for role in context.roles):
            return context
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return dependency


async def validate_csrf(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    container: AppState = request.app.state.container
    if not container.settings.security_csrf_enabled:
        return
    path = request.url.path
    if "/auth/login" in path or "/auth/refresh" in path or "/mfa/verify" in path or "/webauthn/login" in path:
        return
    if "/team/invitations/accept" in path or "/team/invitations/preview" in path:
        return
    if not path.startswith(container.settings.app_api_prefix):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def get_client_ip(request: Request) -> str | None:
    settings: Settings = request.app.state.container.settings
    if settings.security_trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def map_domain_exception(exc: DomainException) -> HTTPException:
    status_map = {
        "not_found": status.HTTP_404_NOT_FOUND,
        "conflict": status.HTTP_409_CONFLICT,
        "unauthorized": status.HTTP_401_UNAUTHORIZED,
        "forbidden": status.HTTP_403_FORBIDDEN,
        "validation_error": status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    return HTTPException(
        status_code=status_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )
