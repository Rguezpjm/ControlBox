from controlbox.modules.databases.domain.entities import (
    BackupStatus,
    BackupType,
    DatabaseBackup,
    DatabaseEngineType,
    DatabaseStatus,
    DatabaseUser,
    ManagedDatabase,
)
from controlbox.modules.databases.infrastructure.models import (
    DatabaseBackupModel,
    DatabaseUserModel,
    ManagedDatabaseModel,
)


def to_managed_database(model: ManagedDatabaseModel) -> ManagedDatabase:
    return ManagedDatabase(
        id=model.id,
        tenant_id=model.tenant_id,
        owner_user_id=model.owner_user_id,
        name=model.name,
        engine=DatabaseEngineType(model.engine),
        status=DatabaseStatus(model.status),
        host=model.host,
        port=model.port,
        database_name=model.database_name,
        charset=model.charset,
        collation=model.db_collation,
        max_connections=model.max_connections,
        size_mb=model.size_mb,
        settings=model.settings or {},
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_database_user(model: DatabaseUserModel) -> DatabaseUser:
    return DatabaseUser(
        id=model.id,
        database_id=model.database_id,
        tenant_id=model.tenant_id,
        username=model.username,
        password_hash=model.password_hash,
        host=model.host,
        max_connections=model.max_connections,
        is_active=model.is_active,
        grants=model.grants or [],
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_database_backup(model: DatabaseBackupModel) -> DatabaseBackup:
    return DatabaseBackup(
        id=model.id,
        database_id=model.database_id,
        tenant_id=model.tenant_id,
        name=model.name,
        backup_type=BackupType(model.backup_type),
        status=BackupStatus(model.status),
        file_path=model.file_path,
        size_mb=model.size_mb,
        checksum=model.checksum,
        retention_days=model.retention_days,
        error_message=model.error_message,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
