from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateWebsiteCommand:
    tenant_id: UUID
    user_id: UUID
    name: str
    domain: str
    runtime: str
    runtime_version: str | None
    database_engine: str
    ssl_enabled: bool = True
    disk_limit_mb: int = 5120


@dataclass(frozen=True)
class DeleteWebsiteCommand:
    website_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class StartWebsiteCommand:
    website_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class StopWebsiteCommand:
    website_id: UUID
    tenant_id: UUID
    user_id: UUID
