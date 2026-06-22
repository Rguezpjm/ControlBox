from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from controlbox.shared.domain.email import TENANT_SLUG_PATTERN, PanelEmail


class RegisterTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=63, pattern=TENANT_SLUG_PATTERN)
    admin_email: PanelEmail
    admin_password: str = Field(min_length=12, max_length=128)
    admin_full_name: str = Field(min_length=1, max_length=255)
    invite_token: str | None = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    email: PanelEmail
    password: str = Field(min_length=1, max_length=128)
    tenant_slug: str | None = Field(default=None, max_length=63, pattern=TENANT_SLUG_PATTERN)
    device_fingerprint: str | None = Field(default=None, max_length=128)

    @field_validator("tenant_slug", mode="before")
    @classmethod
    def normalize_tenant_slug(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip().lower()
            return cleaned or None
        return value  # type: ignore[return-value]


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=512)
    device_fingerprint: str | None = Field(default=None, max_length=128)


class CreateUserRequest(BaseModel):
    email: PanelEmail
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role_name: str = Field(default="member", max_length=128)


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    description: str = Field(default="", max_length=1000)
    permission_codes: list[str] = Field(default_factory=list)


class AssignRoleRequest(BaseModel):
    role_id: UUID


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    session_id: UUID


class UserResponseSchema(BaseModel):
    id: UUID
    tenant_id: UUID | None
    email: str
    full_name: str
    is_active: bool
    is_platform_admin: bool
    roles: list[str]
    permissions: list[str]


class TenantResponseSchema(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    settings: dict


class RegisterTenantResponseSchema(BaseModel):
    tenant: TenantResponseSchema
    user: UserResponseSchema
    tokens: TokenResponseSchema


class SessionResponseSchema(BaseModel):
    id: UUID
    user_agent: str | None
    ip_address: str | None
    device_fingerprint: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class AuditLogResponseSchema(BaseModel):
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


class PermissionResponseSchema(BaseModel):
    id: UUID
    code: str
    name: str
    module: str


class RoleResponseSchema(BaseModel):
    id: UUID
    tenant_id: UUID | None
    name: str
    description: str
    is_system: bool
    permissions: list[str]


class ErrorResponseSchema(BaseModel):
    error: str
    code: str
    detail: str | None = None


class HealthResponseSchema(BaseModel):
    status: str
    app: str
    environment: str
    postgres: str
    redis: str
    version: str = ""
