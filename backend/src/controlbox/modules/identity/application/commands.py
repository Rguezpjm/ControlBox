from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RegisterTenantCommand:
    name: str
    slug: str
    admin_email: str
    admin_password: str
    admin_full_name: str


@dataclass(frozen=True)
class LoginCommand:
    email: str
    password: str
    tenant_slug: str | None
    user_agent: str | None
    ip_address: str | None
    device_fingerprint: str | None


@dataclass(frozen=True)
class RefreshTokenCommand:
    refresh_token: str
    user_agent: str | None
    ip_address: str | None
    device_fingerprint: str | None


@dataclass(frozen=True)
class LogoutCommand:
    session_id: UUID
    user_id: UUID
    access_token_jti: str | None
    access_token_exp: int | None


@dataclass(frozen=True)
class RevokeAllSessionsCommand:
    user_id: UUID
    tenant_id: UUID | None


@dataclass(frozen=True)
class CreateUserCommand:
    tenant_id: UUID
    email: str
    password: str
    full_name: str
    role_name: str = "member"


@dataclass(frozen=True)
class CreateRoleCommand:
    tenant_id: UUID
    name: str
    description: str
    permission_codes: list[str]


@dataclass(frozen=True)
class AssignRoleCommand:
    user_id: UUID
    role_id: UUID
    tenant_id: UUID
