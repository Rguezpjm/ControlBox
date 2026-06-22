from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateBackupDestinationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=63)
    destination_type: str
    bucket: str = ""
    endpoint: str = ""
    region: str = "us-east-1"
    prefix: str = ""
    local_path: str = ""
    access_key: str = ""
    secret_key: str = ""
    is_default: bool = False


class UpdateBackupDestinationRequest(BaseModel):
    name: str | None = None
    bucket: str | None = None
    endpoint: str | None = None
    region: str | None = None
    prefix: str | None = None
    local_path: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class CreateBackupScheduleRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    source_type: str
    resource_id: UUID | None = None
    destination_id: UUID
    cron_expression: str = "0 3 * * *"
    max_versions: int = Field(default=10, ge=1, le=100)
    retention_days: int = Field(default=30, ge=1, le=365)


class UpdateBackupScheduleRequest(BaseModel):
    name: str | None = None
    source_type: str | None = None
    resource_id: UUID | None = None
    destination_id: UUID | None = None
    cron_expression: str | None = None
    max_versions: int | None = Field(default=None, ge=1, le=100)
    retention_days: int | None = Field(default=None, ge=1, le=365)


class CreateBackupJobRequest(BaseModel):
    name: str = Field(default="", max_length=128)
    source_type: str
    resource_id: UUID | None = None
    destination_id: UUID
    max_versions: int = Field(default=10, ge=1, le=100)
    retention_days: int = Field(default=30, ge=1, le=365)


class BackupDestinationSchema(BaseModel):
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


class BackupScheduleSchema(BaseModel):
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


class BackupJobSchema(BaseModel):
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


class BackupStatsSchema(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_size_bytes: int
    active_schedules: int
    next_scheduled_at: datetime | None


class BackupDownloadSchema(BaseModel):
    download_url: str | None
    storage_path: str


class BackupTestResultSchema(BaseModel):
    success: bool
