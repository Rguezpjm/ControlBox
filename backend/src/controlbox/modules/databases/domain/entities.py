from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class DatabaseEngineType(StrEnum):
    MYSQL = "mysql"
    MARIADB = "mariadb"
    POSTGRESQL = "postgresql"
    MSSQL = "mssql"


class DatabaseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    STOPPED = "stopped"
    ERROR = "error"
    DELETING = "deleting"


class BackupStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORING = "restoring"


class BackupType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


ENGINE_DEFAULT_PORTS: dict[DatabaseEngineType, int] = {
    DatabaseEngineType.MYSQL: 3306,
    DatabaseEngineType.MARIADB: 3306,
    DatabaseEngineType.POSTGRESQL: 5432,
    DatabaseEngineType.MSSQL: 1433,
}


@dataclass
class ManagedDatabase(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    engine: DatabaseEngineType = DatabaseEngineType.MYSQL
    status: DatabaseStatus = DatabaseStatus.PENDING
    host: str = ""
    port: int = 3306
    database_name: str = ""
    charset: str = "utf8mb4"
    collation: str = ""
    max_connections: int = 50
    size_mb: int = 0
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def mark_active(self) -> None:
        self.status = DatabaseStatus.ACTIVE
        self.error_message = None
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = DatabaseStatus.ERROR
        self.error_message = message
        self.touch()


@dataclass
class DatabaseUser(Entity):
    database_id: UUID | None = None
    tenant_id: UUID | None = None
    username: str = ""
    password_hash: str = ""
    host: str = "%"
    max_connections: int = 10
    is_active: bool = True
    grants: list[str] = field(default_factory=list)

    def deactivate(self) -> None:
        self.is_active = False
        self.touch()


@dataclass
class DatabaseBackup(Entity):
    database_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    backup_type: BackupType = BackupType.MANUAL
    status: BackupStatus = BackupStatus.PENDING
    file_path: str | None = None
    size_mb: int = 0
    checksum: str | None = None
    retention_days: int = 7
    error_message: str | None = None
    completed_at: datetime | None = None

    def mark_completed(self, file_path: str, size_mb: int, checksum: str) -> None:
        self.status = BackupStatus.COMPLETED
        self.file_path = file_path
        self.size_mb = size_mb
        self.checksum = checksum
        self.completed_at = datetime.now()
        self.touch()

    def mark_failed(self, message: str) -> None:
        self.status = BackupStatus.FAILED
        self.error_message = message
        self.touch()
