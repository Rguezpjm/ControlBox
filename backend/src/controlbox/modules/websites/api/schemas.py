from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UptimeTimelinePointSchema(BaseModel):
    timestamp: str
    status: str
    reason: str | None = None
    latency_ms: float | None = None
    http_status: int | None = None


class CreateWebsiteRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    domain: str = Field(min_length=4, max_length=255)
    runtime: str = Field(pattern=r"^(html|php|nodejs|python|flutter)$")
    runtime_version: str | None = Field(default=None, max_length=32)
    database_engine: str = Field(default="none", pattern=r"^(none|mysql|supabase|mssql)$")
    ssl_enabled: bool = True
    disk_limit_mb: int = Field(default=5120, ge=512, le=102400)
    create_ftp_account: bool = False


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
    traffic_mbps: float = 0.0
    traffic_sparkline: list[float] = Field(default_factory=list)
    visit_count: int = 0
    visits_sparkline: list[float] = Field(default_factory=list)
    uptime_timeline: list[UptimeTimelinePointSchema] = Field(default_factory=list)
    uptime_percent: float = 100.0
    last_down_reason: str | None = None
    last_down_reason_label: str | None = None
    is_up: bool = True
    created_at: datetime
    updated_at: datetime
    ftp_username: str | None = None
    ftp_password: str | None = None
    ftp_home: str | None = None


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
