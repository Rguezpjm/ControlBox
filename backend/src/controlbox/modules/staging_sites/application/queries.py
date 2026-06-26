from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ListStagingSitesQuery:
    tenant_id: UUID
    source_type: str | None = None
    source_id: UUID | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetStagingSiteQuery:
    staging_id: UUID
    tenant_id: UUID


@dataclass(frozen=True)
class StagingSiteResponse:
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
    security: dict
    error_message: str | None
    task_id: str | None
    created_at: datetime
    updated_at: datetime
    cms_version: str | None = None
    migration_progress: int | None = None
    migration_status: str | None = None

