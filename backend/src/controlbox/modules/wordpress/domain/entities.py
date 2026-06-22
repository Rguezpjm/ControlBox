from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class WordPressStatus(StrEnum):
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


class WordPressSslStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"


class WordPressBackupStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORING = "restoring"


PHP_VERSIONS = ["8.2", "8.3"]
DEFAULT_PHP_VERSION = "8.3"
WORDPRESS_VERSION = "latest"


@dataclass
class WordPressSite(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    domain: str = ""
    status: WordPressStatus = WordPressStatus.PENDING
    php_version: str = DEFAULT_PHP_VERSION
    wordpress_version: str = WORDPRESS_VERSION
    url: str = ""
    admin_user: str = ""
    admin_email: str = ""
    managed_database_id: UUID | None = None
    database_user_id: UUID | None = None
    nginx_container_name: str | None = None
    php_container_name: str | None = None
    site_path: str = ""
    ssl_enabled: bool = True
    ssl_status: WordPressSslStatus = WordPressSslStatus.PENDING
    maintenance_mode: bool = False
    disk_used_mb: int = 0
    db_size_mb: int = 0
    parent_site_id: UUID | None = None
    is_staging: bool = False
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    task_id: str | None = None

    def mark_provisioning(self, task_id: str | None = None) -> None:
        self.status = WordPressStatus.PROVISIONING
        self.task_id = task_id
        self.touch()

    def mark_running(self, nginx_name: str, php_name: str) -> None:
        self.status = WordPressStatus.RUNNING
        self.nginx_container_name = nginx_name
        self.php_container_name = php_name
        self.error_message = None
        if self.ssl_enabled:
            self.ssl_status = WordPressSslStatus.ACTIVE
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = WordPressStatus.ERROR
        self.error_message = message
        self.touch()

    def mark_stopped(self) -> None:
        self.status = WordPressStatus.STOPPED
        self.touch()

    def set_maintenance(self, enabled: bool) -> None:
        self.maintenance_mode = enabled
        self.status = WordPressStatus.MAINTENANCE if enabled else WordPressStatus.RUNNING
        self.touch()


@dataclass
class WordPressBackup(Entity):
    site_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    status: WordPressBackupStatus = WordPressBackupStatus.PENDING
    file_path: str | None = None
    size_mb: int = 0
    checksum: str | None = None
    includes_database: bool = True
    includes_files: bool = True
    error_message: str | None = None
    completed_at: datetime | None = None

    def mark_running(self) -> None:
        self.status = WordPressBackupStatus.RUNNING
        self.touch()

    def mark_completed(self, file_path: str, size_mb: int, checksum: str) -> None:
        self.status = WordPressBackupStatus.COMPLETED
        self.file_path = file_path
        self.size_mb = size_mb
        self.checksum = checksum
        self.completed_at = datetime.utcnow()
        self.error_message = None
        self.touch()

    def mark_failed(self, message: str) -> None:
        self.status = WordPressBackupStatus.FAILED
        self.error_message = message
        self.touch()
