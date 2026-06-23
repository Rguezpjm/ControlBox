from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateDatabaseCommand:
    tenant_id: UUID
    user_id: UUID
    name: str
    engine: str
    charset: str = "utf8mb4"
    max_connections: int = 50


@dataclass(frozen=True)
class DeleteDatabaseCommand:
    tenant_id: UUID
    database_id: UUID


@dataclass(frozen=True)
class CreateDatabaseUserCommand:
    tenant_id: UUID
    database_id: UUID
    username: str
    password: str | None = None
    host: str = "%"
    max_connections: int = 10
    grants: list[str] | None = None


@dataclass(frozen=True)
class ChangeDatabaseUserPasswordCommand:
    tenant_id: UUID
    database_id: UUID
    user_id: UUID
    password: str | None = None


@dataclass(frozen=True)
class SetDatabaseUserConnectionLimitCommand:
    tenant_id: UUID
    database_id: UUID
    user_id: UUID
    max_connections: int


@dataclass(frozen=True)
class DeleteDatabaseUserCommand:
    tenant_id: UUID
    database_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class SetDatabaseConnectionLimitCommand:
    tenant_id: UUID
    database_id: UUID
    max_connections: int


@dataclass(frozen=True)
class CreateDatabaseBackupCommand:
    tenant_id: UUID
    database_id: UUID
    name: str | None = None
    retention_days: int = 7


@dataclass(frozen=True)
class RestoreDatabaseBackupCommand:
    tenant_id: UUID
    database_id: UUID
    backup_id: UUID


@dataclass(frozen=True)
class DeleteDatabaseBackupCommand:
    tenant_id: UUID
    database_id: UUID
    backup_id: UUID
