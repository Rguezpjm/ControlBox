from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity, utc_now


class BackupDestinationType(StrEnum):
    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"
    R2 = "r2"


class BackupSourceType(StrEnum):
    WEBSITES = "websites"
    DATABASES = "databases"
    DNS = "dns"
    CONFIGURATIONS = "configurations"


class BackupJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORING = "restoring"


class BackupTriggerType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


@dataclass
class BackupDestination(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    destination_type: BackupDestinationType = BackupDestinationType.LOCAL
    bucket: str = ""
    endpoint: str = ""
    region: str = "us-east-1"
    prefix: str = ""
    local_path: str = ""
    access_key_encrypted: str = ""
    secret_key_encrypted: str = ""
    is_default: bool = False
    is_active: bool = True

    def deactivate(self) -> None:
        self.is_active = False
        self.touch()


@dataclass
class BackupSchedule(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    source_type: BackupSourceType = BackupSourceType.WEBSITES
    resource_id: UUID | None = None
    destination_id: UUID | None = None
    cron_expression: str = "0 3 * * *"
    max_versions: int = 10
    retention_days: int = 30
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    def pause(self) -> None:
        self.is_active = False
        self.touch()

    def resume(self, next_run: datetime) -> None:
        self.is_active = True
        self.next_run_at = next_run
        self.touch()

    def mark_run(self, next_run: datetime) -> None:
        self.last_run_at = utc_now()
        self.next_run_at = next_run
        self.touch()


@dataclass
class BackupJob(Entity):
    tenant_id: UUID | None = None
    schedule_id: UUID | None = None
    destination_id: UUID | None = None
    name: str = ""
    source_type: BackupSourceType = BackupSourceType.WEBSITES
    resource_id: UUID | None = None
    resource_name: str = ""
    resource_key: str = ""
    trigger_type: BackupTriggerType = BackupTriggerType.MANUAL
    status: BackupJobStatus = BackupJobStatus.PENDING
    version_number: int = 1
    storage_path: str = ""
    size_bytes: int = 0
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    retention_days: int = 30
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def mark_running(self) -> None:
        self.status = BackupJobStatus.RUNNING
        self.started_at = utc_now()
        self.touch()

    def mark_completed(self, storage_path: str, size_bytes: int, checksum: str) -> None:
        self.status = BackupJobStatus.COMPLETED
        self.storage_path = storage_path
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.completed_at = utc_now()
        self.error_message = None
        self.touch()

    def mark_failed(self, message: str) -> None:
        self.status = BackupJobStatus.FAILED
        self.error_message = message
        self.completed_at = utc_now()
        self.touch()

    def mark_restoring(self) -> None:
        self.status = BackupJobStatus.RESTORING
        self.touch()
