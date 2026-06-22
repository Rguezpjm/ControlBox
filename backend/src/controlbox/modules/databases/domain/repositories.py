from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.databases.domain.entities import DatabaseBackup, DatabaseUser, ManagedDatabase


class ManagedDatabaseRepository(ABC):
    @abstractmethod
    async def add(self, database: ManagedDatabase) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, database: ManagedDatabase) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, database_id: UUID) -> ManagedDatabase | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, database_id: UUID, tenant_id: UUID) -> ManagedDatabase | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_name(self, name: str, tenant_id: UUID) -> ManagedDatabase | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, engine: str | None = None, limit: int = 50, offset: int = 0) -> list[ManagedDatabase]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, database_id: UUID) -> None:
        raise NotImplementedError


class DatabaseUserRepository(ABC):
    @abstractmethod
    async def add(self, user: DatabaseUser) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, user: DatabaseUser) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> DatabaseUser | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_database(self, user_id: UUID, database_id: UUID) -> DatabaseUser | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_username(self, database_id: UUID, username: str) -> DatabaseUser | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_database(self, database_id: UUID) -> list[DatabaseUser]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, user_id: UUID) -> None:
        raise NotImplementedError


class DatabaseBackupRepository(ABC):
    @abstractmethod
    async def add(self, backup: DatabaseBackup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, backup: DatabaseBackup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, backup_id: UUID) -> DatabaseBackup | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_database(self, backup_id: UUID, database_id: UUID) -> DatabaseBackup | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_database(self, database_id: UUID, limit: int = 20) -> list[DatabaseBackup]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, backup_id: UUID) -> None:
        raise NotImplementedError
