from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class JoomlaStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    CLONING = "cloning"
    BACKING_UP = "backing_up"
    RESTORING = "restoring"
    DELETING = "deleting"


class JoomlaSslStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"


class JoomlaBackupStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORING = "restoring"


PHP_VERSIONS = ["8.2", "8.3"]
DEFAULT_PHP_VERSION = "8.3"
JOOMLA_VERSION = "5.1.1"


@dataclass
class JoomlaSite(Entity):
    tenant_id: UUID | None = None
    owner_user_id: UUID | None = None
    name: str = ""
    domain: str = ""
    status: JoomlaStatus = JoomlaStatus.PENDING
    php_version: str = DEFAULT_PHP_VERSION
    joomla_version: str = JOOMLA_VERSION
    url: str = ""
    admin_user: str = ""
    admin_email: str = ""
    managed_database_id: UUID | None = None
    database_user_id: UUID | None = None
    nginx_container_name: str | None = None
    php_container_name: str | None = None
    site_path: str = ""
    ssl_enabled: bool = True
    ssl_status: JoomlaSslStatus = JoomlaSslStatus.PENDING
    maintenance_mode: bool = False
    disk_used_mb: int = 0
    db_size_mb: int = 0
    parent_site_id: UUID | None = None
    is_staging: bool = False
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    task_id: str | None = None

    def mark_provisioning(self, task_id: str | None = None) -> None:
        self.status = JoomlaStatus.PROVISIONING
        self.task_id = task_id
        self.touch()

    def mark_running(self, nginx_name: str, php_name: str) -> None:
        self.status = JoomlaStatus.RUNNING
        self.nginx_container_name = nginx_name
        self.php_container_name = php_name
        self.error_message = None
        if self.ssl_enabled:
            self.ssl_status = JoomlaSslStatus.ACTIVE
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = JoomlaStatus.ERROR
        self.error_message = message
        self.touch()

    def mark_stopped(self) -> None:
        self.status = JoomlaStatus.STOPPED
        self.touch()

    def set_maintenance(self, enabled: bool) -> None:
        self.maintenance_mode = enabled
        self.status = JoomlaStatus.MAINTENANCE if enabled else JoomlaStatus.RUNNING
        self.touch()


@dataclass
class JoomlaBackup(Entity):
    site_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    status: JoomlaBackupStatus = JoomlaBackupStatus.PENDING
    file_path: str | None = None
    size_mb: int = 0
    checksum: str | None = None
    includes_database: bool = True
    includes_files: bool = True
    error_message: str | None = None
    completed_at: datetime | None = None

    def mark_running(self) -> None:
        self.status = JoomlaBackupStatus.RUNNING
        self.touch()

    def mark_completed(self, file_path: str, size_mb: int, checksum: str) -> None:
        self.status = JoomlaBackupStatus.COMPLETED
        self.file_path = file_path
        self.size_mb = size_mb
        self.checksum = checksum
        self.completed_at = datetime.utcnow()
        self.error_message = None
        self.touch()

    def mark_failed(self, message: str) -> None:
        self.status = JoomlaBackupStatus.FAILED
        self.error_message = message
        self.touch()
