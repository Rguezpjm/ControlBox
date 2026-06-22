from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateStagingSiteRequest(BaseModel):
    source_type: str = Field(pattern="^(website|wordpress)$")
    source_id: UUID
    domain_mode: str = Field(default="subdomain", pattern="^(subdomain|random)$")
    name: str = ""


class SyncStagingRequest(BaseModel):
    sync_type: str = Field(pattern="^(files|database|full)$")
    direction: str = Field(default="from_production", pattern="^(from_production|to_production)$")


class SyncTypeRequest(BaseModel):
    sync_type: str = Field(pattern="^(files|database|full)$")


class BlockStagingAccessRequest(BaseModel):
    blocked: bool


class UpdateStagingSecurityRequest(BaseModel):
    password_protection_enabled: bool = False
    password_protection_username: str = "staging"
    password_protection_password: str = ""
    ip_restriction_enabled: bool = False
    allowed_ips: list[str] = Field(default_factory=list)
    temp_access_enabled: bool = False
    temp_access_hours: int = Field(default=24, ge=1, le=168)


class StagingSecuritySchema(BaseModel):
    password_protection: dict
    ip_restriction: dict
    temp_access: dict


class StagingSiteResponseSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    source_type: str
    source_id: UUID
    source_domain: str
    name: str
    domain: str
    domain_mode: str
    stack_type: str
    runtime_version: str
    status: str
    ssl_enabled: bool
    ssl_status: str
    container_name: str | None
    nginx_container_name: str | None
    php_container_name: str | None
    site_path: str
    traefik_router: str | None
    public_access_blocked: bool
    last_sync_at: datetime | None
    last_sync_type: str | None
    last_sync_direction: str | None
    cpu_usage_percent: float
    memory_used_mb: int
    disk_used_mb: int
    security: StagingSecuritySchema
    error_message: str | None
    task_id: str | None
    created_at: datetime
    updated_at: datetime
