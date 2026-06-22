from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateWebsiteRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    domain: str = Field(min_length=4, max_length=255)
    runtime: str = Field(pattern=r"^(html|php|nodejs|python|flutter)$")
    runtime_version: str | None = Field(default=None, max_length=32)
    database_engine: str = Field(default="none", pattern=r"^(none|mysql|supabase|mssql)$")
    ssl_enabled: bool = True
    disk_limit_mb: int = Field(default=5120, ge=512, le=102400)


class WebsiteResponseSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    domain: str
    runtime: str
    runtime_version: str
    status: str
    container_id: str | None
    container_name: str | None
    document_root: str
    ssl_enabled: bool
    ssl_status: str
    database_engine: str
    database_config: dict[str, Any]
    monitoring_enabled: bool
    logs_enabled: bool
    logs_path: str | None
    port: int
    disk_used_mb: int
    disk_limit_mb: int
    error_message: str | None
    ssl_days_remaining: int | None = None
    requests_count: int = 0
    requests_sparkline: list[float] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RuntimeOptionSchema(BaseModel):
    runtime: str
    label: str
    versions: list[str]
    default_version: str


class DatabaseOptionSchema(BaseModel):
    engine: str
    label: str


class WebsiteOptionsSchema(BaseModel):
    runtimes: list[RuntimeOptionSchema]
    databases: list[DatabaseOptionSchema]
