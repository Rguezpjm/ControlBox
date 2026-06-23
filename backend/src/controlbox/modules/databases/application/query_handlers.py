from dataclasses import dataclass

from controlbox.modules.databases.application.queries import (
    GetDatabaseOptionsQuery,
    GetDatabaseQuery,
    ListDatabaseBackupsQuery,
    ListDatabasesQuery,
    ListDatabaseUsersQuery,
)
from controlbox.modules.databases.domain.entities import (
    DatabaseBackup,
    DatabaseEngineType,
    DatabaseUser,
    ENGINE_DEFAULT_PORTS,
    ManagedDatabase,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


@dataclass
class EngineOption:
    engine: str
    label: str
    default_port: int
    supports_connection_limit: bool


@dataclass
class DatabaseOptions:
    engines: list[EngineOption]


class ListDatabasesHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListDatabasesQuery) -> list[ManagedDatabase]:
        async with self._uow:
            databases = await self._uow.managed_databases.list_by_tenant(
                query.tenant_id, query.engine, query.limit, query.offset
            )
            if query.can_manage_all:
                return databases
            return [
                db for db in databases
                if db.owner_user_id is not None and db.owner_user_id == query.requester_user_id
            ]


class GetDatabaseHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetDatabaseQuery) -> ManagedDatabase:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                query.database_id, query.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")
            if not query.can_manage_all and database.owner_user_id != query.requester_user_id:
                raise NotFoundError("Database not found")
            return database


class GetDatabaseOptionsHandler:
    async def handle(self, query: GetDatabaseOptionsQuery) -> DatabaseOptions:
        engines = [
            EngineOption("mysql", "MySQL", ENGINE_DEFAULT_PORTS[DatabaseEngineType.MYSQL], True),
            EngineOption("mariadb", "MariaDB", ENGINE_DEFAULT_PORTS[DatabaseEngineType.MARIADB], True),
            EngineOption("mssql", "Microsoft SQL Server", ENGINE_DEFAULT_PORTS[DatabaseEngineType.MSSQL], False),
        ]
        return DatabaseOptions(engines=engines)


class ListDatabaseUsersHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListDatabaseUsersQuery) -> list[DatabaseUser]:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                query.database_id, query.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")
            return await self._uow.database_users.list_by_database(database.id)


class ListDatabaseBackupsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListDatabaseBackupsQuery) -> list[DatabaseBackup]:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                query.database_id, query.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")
            return await self._uow.database_backups.list_by_database(database.id, query.limit)
