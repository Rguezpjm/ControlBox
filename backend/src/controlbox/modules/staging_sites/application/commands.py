from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateStagingSiteCommand:
    tenant_id: UUID
    user_id: UUID
    source_type: str
    source_id: UUID
    domain_mode: str = "subdomain"
    name: str = ""


@dataclass(frozen=True)
class SyncStagingCommand:
    staging_id: UUID
    tenant_id: UUID
    user_id: UUID
    sync_type: str
    direction: str


@dataclass(frozen=True)
class DeleteStagingSiteCommand:
    staging_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class RestartStagingSiteCommand:
    staging_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class BlockStagingAccessCommand:
    staging_id: UUID
    tenant_id: UUID
    user_id: UUID
    blocked: bool


@dataclass(frozen=True)
class UpdateStagingSecurityCommand:
    staging_id: UUID
    tenant_id: UUID
    user_id: UUID
    password_protection_enabled: bool = False
    password_protection_username: str = "staging"
    password_protection_password: str = ""
    ip_restriction_enabled: bool = False
    allowed_ips: list[str] | None = None
    temp_access_enabled: bool = False
    temp_access_hours: int = 24


@dataclass(frozen=True)
class ProvisionStagingSiteCommand:
    staging_id: UUID


@dataclass(frozen=True)
class RunStagingSyncCommand:
    staging_id: UUID
    sync_type: str
    direction: str
