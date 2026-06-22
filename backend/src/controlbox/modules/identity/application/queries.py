from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GetCurrentUserQuery:
    user_id: UUID
    tenant_id: UUID | None


@dataclass(frozen=True)
class GetTenantQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class GetTenantBySlugQuery:
    slug: str


@dataclass(frozen=True)
class ListSessionsQuery:
    user_id: UUID


@dataclass(frozen=True)
class ListAuditLogsQuery:
    tenant_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class ListPermissionsQuery:
    pass


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    session_id: UUID


@dataclass(frozen=True)
class UserResponse:
    id: UUID
    tenant_id: UUID | None
    email: str
    full_name: str
    is_active: bool
    is_platform_admin: bool
    roles: list[str]
    permissions: list[str]


@dataclass(frozen=True)
class TenantResponse:
    id: UUID
    name: str
    slug: str
    status: str
    settings: dict


@dataclass(frozen=True)
class SessionResponse:
    id: UUID
    user_agent: str | None
    ip_address: str | None
    device_fingerprint: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True)
class AuditLogResponse:
    id: UUID
    tenant_id: UUID | None
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


@dataclass(frozen=True)
class PermissionResponse:
    id: UUID
    code: str
    name: str
    module: str


@dataclass(frozen=True)
class RoleResponse:
    id: UUID
    tenant_id: UUID | None
    name: str
    description: str
    is_system: bool
    permissions: list[str]
