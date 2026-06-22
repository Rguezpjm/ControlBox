from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import (
    BackupStatus,
    BackupType,
    DatabaseBackup,
    DatabaseEngineType,
    DatabaseStatus,
    DatabaseUser,
    ENGINE_DEFAULT_PORTS,
    ManagedDatabase,
)
from controlbox.modules.databases.domain.services import DatabaseDomainService
from controlbox.modules.databases.infrastructure.engine_adapters import (
    EngineAdapterFactory,
    compute_checksum,
    generate_password,
    hash_password,
)
from controlbox.modules.databases.infrastructure.engine_config import EngineConfigResolver
class DatabaseProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._config = EngineConfigResolver(settings)
        self._backups_root = Path(settings.database_backups_path)

    def resolve_host_port(self, engine: DatabaseEngineType) -> tuple[str, int]:
        conn = self._config.resolve(engine)
        return conn.host, conn.port

    async def provision_database(self, database: ManagedDatabase) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        charset = database.charset if database.engine != DatabaseEngineType.MSSQL else "UTF8"
        await adapter.create_database(conn, database.database_name, charset)
        database.mark_active()

    async def deprovision_database(self, database: ManagedDatabase) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        await adapter.drop_database(conn, database.database_name)

    async def provision_user(
        self,
        database: ManagedDatabase,
        user: DatabaseUser,
        plain_password: str,
    ) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        await adapter.create_user(
            conn,
            database.database_name,
            user.username,
            plain_password,
            user.host,
            user.grants,
            user.max_connections,
        )

    async def change_user_password(self, database: ManagedDatabase, user: DatabaseUser, plain_password: str) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        await adapter.change_password(conn, user.username, plain_password, user.host)

    async def set_user_connection_limit(self, database: ManagedDatabase, user: DatabaseUser) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        await adapter.set_connection_limit(conn, user.username, user.host, user.max_connections)

    async def drop_user(self, database: ManagedDatabase, user: DatabaseUser) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        await adapter.drop_user(conn, user.username, user.host)

    def backup_path(self, tenant_id: UUID, database_id: UUID, backup_id: UUID, engine: DatabaseEngineType) -> Path:
        ext = "bak" if engine == DatabaseEngineType.MSSQL else "dump" if engine == DatabaseEngineType.POSTGRESQL else "sql"
        directory = self._backups_root / str(tenant_id) / str(database_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{backup_id}.{ext}"

    async def run_backup(self, database: ManagedDatabase, backup: DatabaseBackup) -> None:
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        path = Path(backup.file_path) if backup.file_path else self.backup_path(
            database.tenant_id, database.id, backup.id, database.engine
        )
        backup.status = BackupStatus.RUNNING
        await adapter.backup(conn, database.database_name, path)
        size_mb = max(1, path.stat().st_size // (1024 * 1024))
        backup.mark_completed(str(path), size_mb, compute_checksum(path))

    async def run_restore(self, database: ManagedDatabase, backup: DatabaseBackup) -> None:
        if not backup.file_path:
            raise ValueError("Backup file not found")
        conn = self._config.resolve(database.engine)
        adapter = EngineAdapterFactory.get(database.engine)
        backup.status = BackupStatus.RESTORING
        await adapter.restore(conn, database.database_name, Path(backup.file_path))


def build_managed_database(
    tenant_id: UUID,
    name: str,
    engine: DatabaseEngineType,
    host: str,
    port: int,
    database_name: str,
    charset: str,
    max_connections: int,
) -> ManagedDatabase:
    return ManagedDatabase(
        tenant_id=tenant_id,
        name=name,
        engine=engine,
        status=DatabaseStatus.PENDING,
        host=host,
        port=port,
        database_name=database_name,
        charset=charset,
        max_connections=max_connections,
    )


def build_database_user(
    database_id: UUID,
    tenant_id: UUID,
    username: str,
    plain_password: str,
    host: str,
    max_connections: int,
    grants: list[str],
) -> tuple[DatabaseUser, str]:
    user = DatabaseUser(
        database_id=database_id,
        tenant_id=tenant_id,
        username=username,
        password_hash=hash_password(plain_password),
        host=host,
        max_connections=max_connections,
        grants=grants,
    )
    return user, plain_password


def build_backup(database_id: UUID, tenant_id: UUID, name: str, retention_days: int) -> DatabaseBackup:
    return DatabaseBackup(
        database_id=database_id,
        tenant_id=tenant_id,
        name=name,
        backup_type=BackupType.MANUAL,
        status=BackupStatus.PENDING,
        retention_days=retention_days,
    )
