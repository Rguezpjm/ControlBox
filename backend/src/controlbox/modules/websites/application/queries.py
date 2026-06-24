from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ListWebsitesQuery:
    tenant_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetWebsiteQuery:
    website_id: UUID
    tenant_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False


@dataclass(frozen=True)
class GetRuntimeOptionsQuery:
    pass


@dataclass(frozen=True)
class WebsiteResponse:
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
    created_at: datetime
    updated_at: datetime
    ftp_username: str | None = None
    ftp_password: str | None = None
    ftp_home: str | None = None


@dataclass(frozen=True)
class RuntimeOptionResponse:
    runtime: str
    label: str
    versions: list[str]
    default_version: str


@dataclass(frozen=True)
class DatabaseOptionResponse:
    engine: str
    label: str


@dataclass(frozen=True)
class WebsiteOptionsResponse:
    runtimes: list[RuntimeOptionResponse]
    databases: list[DatabaseOptionResponse]
