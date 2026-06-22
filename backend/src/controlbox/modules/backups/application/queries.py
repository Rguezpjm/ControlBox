from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class ListBackupDestinationsQuery:
    tenant_id: UUID


@dataclass
class GetBackupDestinationQuery:
    tenant_id: UUID
    destination_id: UUID


@dataclass
class ListBackupSchedulesQuery:
    tenant_id: UUID


@dataclass
class GetBackupScheduleQuery:
    tenant_id: UUID
    schedule_id: UUID


@dataclass
class ListBackupJobsQuery:
    tenant_id: UUID
    source_type: str | None


@dataclass
class GetBackupJobQuery:
    tenant_id: UUID
    job_id: UUID


@dataclass
class ListBackupVersionsQuery:
    tenant_id: UUID
    job_id: UUID


@dataclass
class GetBackupStatsQuery:
    tenant_id: UUID


@dataclass
class BackupDestinationResponse:
    id: UUID
    tenant_id: UUID
    name: str
    destination_type: str
    bucket: str
    endpoint: str
    region: str
    prefix: str
    local_path: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class BackupScheduleResponse:
    id: UUID
    tenant_id: UUID
    name: str
    source_type: str
    resource_id: UUID | None
    destination_id: UUID
    cron_expression: str
    max_versions: int
    retention_days: int
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class BackupJobResponse:
    id: UUID
    tenant_id: UUID
    schedule_id: UUID | None
    destination_id: UUID
    name: str
    source_type: str
    resource_id: UUID | None
    resource_name: str
    resource_key: str
    trigger_type: str
    status: str
    version_number: int
    storage_path: str
    size_bytes: int
    checksum: str
    metadata: dict
    retention_days: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class BackupStatsResponse:
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_size_bytes: int
    active_schedules: int
    next_scheduled_at: datetime | None
