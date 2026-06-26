from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class StagingSourceType(StrEnum):
    WEBSITE = "website"
    WORDPRESS = "wordpress"
    JOOMLA = "joomla"


class StagingStackType(StrEnum):
    HTML = "html"
    PHP = "php"
    NODEJS = "nodejs"
    PYTHON = "python"
    WORDPRESS = "wordpress"
    JOOMLA = "joomla"



class StagingStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    SYNCING = "syncing"
    ERROR = "error"
    DELETING = "deleting"


class StagingDomainMode(StrEnum):
    SUBDOMAIN = "subdomain"
    RANDOM = "random"


class SyncType(StrEnum):
    FILES = "files"
    DATABASE = "database"
    FULL = "full"


class SyncDirection(StrEnum):
    FROM_PRODUCTION = "from_production"
    TO_PRODUCTION = "to_production"


class SslStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"


@dataclass
class StagingSite(Entity):
    tenant_id: UUID | None = None
    source_type: StagingSourceType = StagingSourceType.WEBSITE
    source_id: UUID | None = None
    source_domain: str = ""
    name: str = ""
    domain: str = ""
    domain_mode: StagingDomainMode = StagingDomainMode.SUBDOMAIN
    stack_type: StagingStackType = StagingStackType.PHP
    runtime_version: str = ""
    status: StagingStatus = StagingStatus.PENDING
    ssl_enabled: bool = True
    ssl_status: SslStatus = SslStatus.PENDING
    container_name: str | None = None
    nginx_container_name: str | None = None
    php_container_name: str | None = None
    site_path: str = ""
    traefik_router: str | None = None
    managed_database_id: UUID | None = None
    database_user_id: UUID | None = None
    database_config: dict[str, Any] = field(default_factory=dict)
    public_access_blocked: bool = False
    last_sync_at: datetime | None = None
    last_sync_type: str | None = None
    last_sync_direction: str | None = None
    cpu_usage_percent: float = 0.0
    memory_used_mb: int = 0
    disk_used_mb: int = 0
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    task_id: str | None = None

    def mark_provisioning(self, task_id: str | None = None) -> None:
        self.status = StagingStatus.PROVISIONING
        self.task_id = task_id
        self.error_message = None
        self.touch()

    def mark_running(self) -> None:
        self.status = StagingStatus.RUNNING
        self.error_message = None
        self.touch()

    def mark_syncing(self, direction: SyncDirection, sync_type: SyncType) -> None:
        self.status = StagingStatus.SYNCING
        self.last_sync_direction = direction.value
        self.settings["pending_sync_type"] = sync_type.value
        self.touch()

    def mark_sync_complete(self, sync_type: SyncType, direction: SyncDirection) -> None:
        self.status = StagingStatus.RUNNING
        self.last_sync_at = datetime.utcnow()
        self.last_sync_type = sync_type.value
        self.last_sync_direction = direction.value
        self.settings.pop("pending_sync_type", None)
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = StagingStatus.ERROR
        self.error_message = message
        self.touch()

    def mark_deleting(self) -> None:
        self.status = StagingStatus.DELETING
        self.touch()

    def activate_ssl(self) -> None:
        self.ssl_status = SslStatus.ACTIVE
        self.touch()

    def set_public_blocked(self, blocked: bool) -> None:
        self.public_access_blocked = blocked
        self.touch()

    def update_metrics(self, cpu: float, memory_mb: int, disk_mb: int) -> None:
        self.cpu_usage_percent = cpu
        self.memory_used_mb = memory_mb
        self.disk_used_mb = disk_mb
        self.touch()
