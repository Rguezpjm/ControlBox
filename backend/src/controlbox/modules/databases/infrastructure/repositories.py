from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.databases.domain.entities import DatabaseBackup, DatabaseUser, ManagedDatabase
from controlbox.modules.databases.domain.repositories import (
    DatabaseBackupRepository,
    DatabaseUserRepository,
    ManagedDatabaseRepository,
)
from controlbox.modules.databases.infrastructure.mappers import (
    to_database_backup,
    to_database_user,
    to_managed_database,
)
from controlbox.modules.databases.infrastructure.models import (
    DatabaseBackupModel,
    DatabaseUserModel,
    ManagedDatabaseModel,
)


class SqlAlchemyManagedDatabaseRepository(ManagedDatabaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, database: ManagedDatabase) -> None:
        model = ManagedDatabaseModel(
            id=database.id,
            tenant_id=database.tenant_id,
            name=database.name,
            engine=database.engine.value,
            status=database.status.value,
            host=database.host,
            port=database.port,
            database_name=database.database_name,
            charset=database.charset,
            db_collation=database.collation,
            max_connections=database.max_connections,
            size_mb=database.size_mb,
            settings=database.settings,
            error_message=database.error_message,
        )
        self._session.add(model)

    async def save(self, database: ManagedDatabase) -> None:
        result = await self._session.execute(
            select(ManagedDatabaseModel).where(ManagedDatabaseModel.id == database.id)
        )
        model = result.scalar_one()
        model.status = database.status.value
        model.max_connections = database.max_connections
        model.size_mb = database.size_mb
        model.settings = database.settings
        model.error_message = database.error_message

    async def get_by_id(self, database_id: UUID) -> ManagedDatabase | None:
        result = await self._session.execute(
            select(ManagedDatabaseModel).where(ManagedDatabaseModel.id == database_id)
        )
        model = result.scalar_one_or_none()
        return to_managed_database(model) if model else None

    async def get_by_id_and_tenant(self, database_id: UUID, tenant_id: UUID) -> ManagedDatabase | None:
        result = await self._session.execute(
            select(ManagedDatabaseModel).where(
                ManagedDatabaseModel.id == database_id,
                ManagedDatabaseModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_managed_database(model) if model else None

    async def get_by_name(self, name: str, tenant_id: UUID) -> ManagedDatabase | None:
        result = await self._session.execute(
            select(ManagedDatabaseModel).where(
                ManagedDatabaseModel.name == name,
                ManagedDatabaseModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_managed_database(model) if model else None

    async def list_by_tenant(
        self, tenant_id: UUID, engine: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ManagedDatabase]:
        query = select(ManagedDatabaseModel).where(ManagedDatabaseModel.tenant_id == tenant_id)
        if engine:
            query = query.where(ManagedDatabaseModel.engine == engine)
        query = query.order_by(ManagedDatabaseModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [to_managed_database(m) for m in result.scalars().all()]

    async def delete(self, database_id: UUID) -> None:
        await self._session.execute(delete(ManagedDatabaseModel).where(ManagedDatabaseModel.id == database_id))


class SqlAlchemyDatabaseUserRepository(DatabaseUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: DatabaseUser) -> None:
        model = DatabaseUserModel(
            id=user.id,
            database_id=user.database_id,
            tenant_id=user.tenant_id,
            username=user.username,
            password_hash=user.password_hash,
            host=user.host,
            max_connections=user.max_connections,
            is_active=user.is_active,
            grants=user.grants,
        )
        self._session.add(model)

    async def save(self, user: DatabaseUser) -> None:
        result = await self._session.execute(
            select(DatabaseUserModel).where(DatabaseUserModel.id == user.id)
        )
        model = result.scalar_one()
        model.password_hash = user.password_hash
        model.max_connections = user.max_connections
        model.is_active = user.is_active
        model.grants = user.grants

    async def get_by_id(self, user_id: UUID) -> DatabaseUser | None:
        result = await self._session.execute(
            select(DatabaseUserModel).where(DatabaseUserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return to_database_user(model) if model else None

    async def get_by_id_and_database(self, user_id: UUID, database_id: UUID) -> DatabaseUser | None:
        result = await self._session.execute(
            select(DatabaseUserModel).where(
                DatabaseUserModel.id == user_id,
                DatabaseUserModel.database_id == database_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_database_user(model) if model else None

    async def get_by_username(self, database_id: UUID, username: str) -> DatabaseUser | None:
        result = await self._session.execute(
            select(DatabaseUserModel).where(
                DatabaseUserModel.database_id == database_id,
                DatabaseUserModel.username == username,
            )
        )
        model = result.scalar_one_or_none()
        return to_database_user(model) if model else None

    async def list_by_database(self, database_id: UUID) -> list[DatabaseUser]:
        result = await self._session.execute(
            select(DatabaseUserModel)
            .where(DatabaseUserModel.database_id == database_id)
            .order_by(DatabaseUserModel.created_at.desc())
        )
        return [to_database_user(m) for m in result.scalars().all()]

    async def delete(self, user_id: UUID) -> None:
        await self._session.execute(delete(DatabaseUserModel).where(DatabaseUserModel.id == user_id))


class SqlAlchemyDatabaseBackupRepository(DatabaseBackupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, backup: DatabaseBackup) -> None:
        model = DatabaseBackupModel(
            id=backup.id,
            database_id=backup.database_id,
            tenant_id=backup.tenant_id,
            name=backup.name,
            backup_type=backup.backup_type.value,
            status=backup.status.value,
            file_path=backup.file_path,
            size_mb=backup.size_mb,
            checksum=backup.checksum,
            retention_days=backup.retention_days,
            error_message=backup.error_message,
            completed_at=backup.completed_at,
        )
        self._session.add(model)

    async def save(self, backup: DatabaseBackup) -> None:
        result = await self._session.execute(
            select(DatabaseBackupModel).where(DatabaseBackupModel.id == backup.id)
        )
        model = result.scalar_one()
        model.status = backup.status.value
        model.file_path = backup.file_path
        model.size_mb = backup.size_mb
        model.checksum = backup.checksum
        model.error_message = backup.error_message
        model.completed_at = backup.completed_at

    async def get_by_id(self, backup_id: UUID) -> DatabaseBackup | None:
        result = await self._session.execute(
            select(DatabaseBackupModel).where(DatabaseBackupModel.id == backup_id)
        )
        model = result.scalar_one_or_none()
        return to_database_backup(model) if model else None

    async def get_by_id_and_database(self, backup_id: UUID, database_id: UUID) -> DatabaseBackup | None:
        result = await self._session.execute(
            select(DatabaseBackupModel).where(
                DatabaseBackupModel.id == backup_id,
                DatabaseBackupModel.database_id == database_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_database_backup(model) if model else None

    async def list_by_database(self, database_id: UUID, limit: int = 20) -> list[DatabaseBackup]:
        result = await self._session.execute(
            select(DatabaseBackupModel)
            .where(DatabaseBackupModel.database_id == database_id)
            .order_by(DatabaseBackupModel.created_at.desc())
            .limit(limit)
        )
        return [to_database_backup(m) for m in result.scalars().all()]

    async def delete(self, backup_id: UUID) -> None:
        await self._session.execute(delete(DatabaseBackupModel).where(DatabaseBackupModel.id == backup_id))
