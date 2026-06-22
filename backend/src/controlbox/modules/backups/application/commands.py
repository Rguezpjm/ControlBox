from dataclasses import dataclass
from uuid import UUID


@dataclass
class CreateBackupDestinationCommand:
    tenant_id: UUID
    name: str
    destination_type: str
    bucket: str
    endpoint: str
    region: str
    prefix: str
    local_path: str
    access_key: str
    secret_key: str
    is_default: bool


@dataclass
class UpdateBackupDestinationCommand:
    tenant_id: UUID
    destination_id: UUID
    name: str | None
    bucket: str | None
    endpoint: str | None
    region: str | None
    prefix: str | None
    local_path: str | None
    access_key: str | None
    secret_key: str | None
    is_default: bool | None
    is_active: bool | None


@dataclass
class DeleteBackupDestinationCommand:
    tenant_id: UUID
    destination_id: UUID


@dataclass
class CreateBackupScheduleCommand:
    tenant_id: UUID
    name: str
    source_type: str
    resource_id: UUID | None
    destination_id: UUID
    cron_expression: str
    max_versions: int
    retention_days: int


@dataclass
class UpdateBackupScheduleCommand:
    tenant_id: UUID
    schedule_id: UUID
    name: str | None
    source_type: str | None
    resource_id: UUID | None
    destination_id: UUID | None
    cron_expression: str | None
    max_versions: int | None
    retention_days: int | None


@dataclass
class DeleteBackupScheduleCommand:
    tenant_id: UUID
    schedule_id: UUID


@dataclass
class PauseBackupScheduleCommand:
    tenant_id: UUID
    schedule_id: UUID


@dataclass
class ResumeBackupScheduleCommand:
    tenant_id: UUID
    schedule_id: UUID


@dataclass
class RunBackupScheduleCommand:
    tenant_id: UUID
    schedule_id: UUID


@dataclass
class CreateBackupJobCommand:
    tenant_id: UUID
    name: str
    source_type: str
    resource_id: UUID | None
    destination_id: UUID
    max_versions: int
    retention_days: int


@dataclass
class RestoreBackupJobCommand:
    tenant_id: UUID
    job_id: UUID


@dataclass
class DeleteBackupJobCommand:
    tenant_id: UUID
    job_id: UUID
