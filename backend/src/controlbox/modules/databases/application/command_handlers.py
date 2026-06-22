from datetime import datetime
from uuid import UUID

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.databases.application.commands import (
    ChangeDatabaseUserPasswordCommand,
    CreateDatabaseBackupCommand,
    CreateDatabaseCommand,
    CreateDatabaseUserCommand,
    DeleteDatabaseBackupCommand,
    DeleteDatabaseCommand,
    DeleteDatabaseUserCommand,
    RestoreDatabaseBackupCommand,
    SetDatabaseConnectionLimitCommand,
    SetDatabaseUserConnectionLimitCommand,
)
from controlbox.modules.databases.domain.entities import (
    DatabaseBackup,
    DatabaseEngineType,
    DatabaseStatus,
    DatabaseUser,
    ENGINE_DEFAULT_PORTS,
    ManagedDatabase,
)
from controlbox.modules.databases.domain.services import DatabaseDomainService
from controlbox.modules.databases.infrastructure.engine_adapters import generate_password
from controlbox.modules.databases.infrastructure.provisioner import (
    DatabaseProvisioner,
    build_backup,
    build_database_user,
    build_managed_database,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


class CreateDatabaseHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = DatabaseProvisioner(self._settings)

    async def handle(self, command: CreateDatabaseCommand) -> ManagedDatabase:
        domain = DatabaseDomainService(self._uow.managed_databases)
        name = domain.validate_name(command.name)
        engine = domain.validate_engine(command.engine)
        await domain.ensure_name_available(name, command.tenant_id)

        host, port = self._provisioner.resolve_host_port(engine)
        database_name = domain.build_database_name(command.tenant_id, name)
        charset = command.charset if engine != DatabaseEngineType.MSSQL else "UTF8"

        database = build_managed_database(
            tenant_id=command.tenant_id,
            name=name,
            engine=engine,
            host=host,
            port=port,
            database_name=database_name,
            charset=charset,
            max_connections=command.max_connections,
        )

        async with self._uow:
            await self._uow.managed_databases.add(database)
            try:
                await self._provisioner.provision_database(database)
                await self._uow.managed_databases.save(database)
            except Exception as exc:
                database.mark_error(str(exc))
                await self._uow.managed_databases.save(database)
                await self._uow.commit()
                raise RuntimeError(str(exc)) from exc
            await self._uow.commit()

        return database


class DeleteDatabaseHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = DatabaseProvisioner(settings or get_settings())

    async def handle(self, command: DeleteDatabaseCommand) -> None:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            users = await self._uow.database_users.list_by_database(database.id)
            for user in users:
                try:
                    await self._provisioner.drop_user(database, user)
                except Exception:
                    pass
                await self._uow.database_users.delete(user.id)

            try:
                await self._provisioner.deprovision_database(database)
            except Exception:
                pass

            await self._uow.managed_databases.delete(database.id)
            await self._uow.commit()


class CreateDatabaseUserHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = DatabaseProvisioner(self._settings)

    async def handle(self, command: CreateDatabaseUserCommand) -> tuple[DatabaseUser, str]:
        domain = DatabaseDomainService(self._uow.managed_databases)
        username = domain.validate_username(command.username)
        plain_password = command.password or generate_password()

        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")
            if database.status != DatabaseStatus.ACTIVE:
                raise NotFoundError(
                    "Database is not active. It may have failed to provision — check its status or delete and recreate it."
                )

            existing = await self._uow.database_users.get_by_username(database.id, username)
            if existing:
                from controlbox.shared.domain.base import ConflictError
                raise ConflictError(f"User '{username}' already exists")

            full_username = domain.build_username(command.tenant_id, username)
            user, password = build_database_user(
                database_id=database.id,
                tenant_id=command.tenant_id,
                username=full_username,
                plain_password=plain_password,
                host=command.host,
                max_connections=command.max_connections,
                grants=command.grants or ["ALL PRIVILEGES"],
            )

            await self._uow.database_users.add(user)
            try:
                await self._provisioner.provision_user(database, user, password)
            except Exception as exc:
                await self._uow.database_users.delete(user.id)
                await self._uow.commit()
                raise RuntimeError(str(exc)) from exc

            await self._uow.commit()

        return user, password


class ChangeDatabaseUserPasswordHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = DatabaseProvisioner(settings or get_settings())

    async def handle(self, command: ChangeDatabaseUserPasswordCommand) -> tuple[DatabaseUser, str]:
        from controlbox.modules.databases.infrastructure.engine_adapters import hash_password

        plain_password = command.password or generate_password()

        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            user = await self._uow.database_users.get_by_id_and_database(command.user_id, database.id)
            if not user:
                raise NotFoundError("User not found")

            await self._provisioner.change_user_password(database, user, plain_password)
            user.password_hash = hash_password(plain_password)
            await self._uow.database_users.save(user)
            await self._uow.commit()

        return user, plain_password


class SetDatabaseUserConnectionLimitHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = DatabaseProvisioner(settings or get_settings())

    async def handle(self, command: SetDatabaseUserConnectionLimitCommand) -> DatabaseUser:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            user = await self._uow.database_users.get_by_id_and_database(command.user_id, database.id)
            if not user:
                raise NotFoundError("User not found")

            user.max_connections = command.max_connections
            await self._provisioner.set_user_connection_limit(database, user)
            await self._uow.database_users.save(user)
            await self._uow.commit()

        return user


class DeleteDatabaseUserHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = DatabaseProvisioner(settings or get_settings())

    async def handle(self, command: DeleteDatabaseUserCommand) -> None:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            user = await self._uow.database_users.get_by_id_and_database(command.user_id, database.id)
            if not user:
                raise NotFoundError("User not found")

            try:
                await self._provisioner.drop_user(database, user)
            except Exception:
                pass

            await self._uow.database_users.delete(user.id)
            await self._uow.commit()


class SetDatabaseConnectionLimitHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: SetDatabaseConnectionLimitCommand) -> ManagedDatabase:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            database.max_connections = command.max_connections
            await self._uow.managed_databases.save(database)
            await self._uow.commit()

        return database


class CreateDatabaseBackupHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = DatabaseProvisioner(settings or get_settings())

    async def handle(self, command: CreateDatabaseBackupCommand) -> DatabaseBackup:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            name = command.name or f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            backup = build_backup(database.id, command.tenant_id, name, command.retention_days)
            backup.file_path = str(
                self._provisioner.backup_path(command.tenant_id, database.id, backup.id, database.engine)
            )

            await self._uow.database_backups.add(backup)
            try:
                await self._provisioner.run_backup(database, backup)
                await self._uow.database_backups.save(backup)
            except Exception as exc:
                backup.mark_failed(str(exc))
                await self._uow.database_backups.save(backup)

            await self._uow.commit()

        return backup


class RestoreDatabaseBackupHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = DatabaseProvisioner(settings or get_settings())

    async def handle(self, command: RestoreDatabaseBackupCommand) -> DatabaseBackup:
        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            backup = await self._uow.database_backups.get_by_id_and_database(command.backup_id, database.id)
            if not backup:
                raise NotFoundError("Backup not found")

            try:
                await self._provisioner.run_restore(database, backup)
                from controlbox.modules.databases.domain.entities import BackupStatus
                backup.status = BackupStatus.COMPLETED
                await self._uow.database_backups.save(backup)
            except Exception as exc:
                backup.mark_failed(str(exc))
                await self._uow.database_backups.save(backup)
                await self._uow.commit()
                raise RuntimeError(str(exc)) from exc

            await self._uow.commit()

        return backup


class DeleteDatabaseBackupHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: DeleteDatabaseBackupCommand) -> None:
        from pathlib import Path

        async with self._uow:
            database = await self._uow.managed_databases.get_by_id_and_tenant(
                command.database_id, command.tenant_id
            )
            if not database:
                raise NotFoundError("Database not found")

            backup = await self._uow.database_backups.get_by_id_and_database(command.backup_id, database.id)
            if not backup:
                raise NotFoundError("Backup not found")

            if backup.file_path:
                path = Path(backup.file_path)
                if path.exists():
                    path.unlink()

            await self._uow.database_backups.delete(backup.id)
            await self._uow.commit()
