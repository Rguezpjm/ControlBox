from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from controlbox.config.settings import get_settings
from controlbox.modules.databases.api.schemas import (
    ChangePasswordRequest,
    CreateBackupRequest,
    CreateDatabaseRequest,
    CreateDatabaseUserRequest,
    DatabaseBackupSchema,
    DatabaseOptionsSchema,
    DatabaseUserCreatedSchema,
    DatabaseUserSchema,
    ManagedDatabaseSchema,
    SetConnectionLimitRequest,
    SetUserConnectionLimitRequest,
)
from controlbox.modules.databases.application.command_handlers import (
    ChangeDatabaseUserPasswordHandler,
    CreateDatabaseBackupHandler,
    CreateDatabaseHandler,
    CreateDatabaseUserHandler,
    DeleteDatabaseBackupHandler,
    DeleteDatabaseHandler,
    DeleteDatabaseUserHandler,
    RestoreDatabaseBackupHandler,
    SetDatabaseConnectionLimitHandler,
    SetDatabaseUserConnectionLimitHandler,
)
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
from controlbox.modules.databases.application.query_handlers import (
    GetDatabaseHandler,
    GetDatabaseOptionsHandler,
    ListDatabaseBackupsHandler,
    ListDatabasesHandler,
    ListDatabaseUsersHandler,
)
from controlbox.modules.databases.application.queries import (
    GetDatabaseOptionsQuery,
    GetDatabaseQuery,
    ListDatabaseBackupsQuery,
    ListDatabasesQuery,
    ListDatabaseUsersQuery,
)
from controlbox.modules.databases.domain.entities import DatabaseBackup, DatabaseUser, ManagedDatabase
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_current_context,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError


router = APIRouter(prefix="/databases", tags=["databases"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _to_database_schema(db: ManagedDatabase) -> ManagedDatabaseSchema:
    return ManagedDatabaseSchema(
        id=db.id,
        tenant_id=db.tenant_id,
        name=db.name,
        engine=db.engine.value,
        status=db.status.value,
        host=db.host,
        port=db.port,
        database_name=db.database_name,
        charset=db.charset,
        max_connections=db.max_connections,
        size_mb=db.size_mb,
        error_message=db.error_message,
        created_at=db.created_at,
        updated_at=db.updated_at,
    )


def _to_user_schema(user: DatabaseUser) -> DatabaseUserSchema:
    return DatabaseUserSchema(
        id=user.id,
        database_id=user.database_id,
        username=user.username,
        host=user.host,
        max_connections=user.max_connections,
        is_active=user.is_active,
        grants=user.grants,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _to_backup_schema(backup: DatabaseBackup) -> DatabaseBackupSchema:
    return DatabaseBackupSchema(
        id=backup.id,
        database_id=backup.database_id,
        name=backup.name,
        backup_type=backup.backup_type.value,
        status=backup.status.value,
        size_mb=backup.size_mb,
        retention_days=backup.retention_days,
        error_message=backup.error_message,
        completed_at=backup.completed_at,
        created_at=backup.created_at,
        updated_at=backup.updated_at,
    )


@router.get("/options", response_model=DatabaseOptionsSchema)
async def get_database_options(
    context: Annotated[RequestContext, Depends(require_permission("databases.read"))],
) -> DatabaseOptionsSchema:
    try:
        handler = GetDatabaseOptionsHandler()
        options = await handler.handle(GetDatabaseOptionsQuery())
        return DatabaseOptionsSchema(
            engines=[
                {
                    "engine": e.engine,
                    "label": e.label,
                    "default_port": e.default_port,
                    "supports_connection_limit": e.supports_connection_limit,
                }
                for e in options.engines
            ]
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("", response_model=list[ManagedDatabaseSchema])
async def list_databases(
    context: Annotated[RequestContext, Depends(require_permission("databases.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    engine: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ManagedDatabaseSchema]:
    tenant_id = _require_tenant(context)
    try:
        handler = ListDatabasesHandler(uow=uow)
        databases = await handler.handle(
            ListDatabasesQuery(tenant_id=tenant_id, engine=engine, limit=limit, offset=offset)
        )
        return [_to_database_schema(db) for db in databases]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("", response_model=ManagedDatabaseSchema, status_code=status.HTTP_201_CREATED)
async def create_database(
    body: CreateDatabaseRequest,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ManagedDatabaseSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = CreateDatabaseHandler(uow=uow, settings=get_settings())
        database = await handler.handle(
            CreateDatabaseCommand(
                tenant_id=tenant_id,
                name=body.name,
                engine=body.engine,
                charset=body.charset,
                max_connections=body.max_connections,
            )
        )
        return _to_database_schema(database)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/{database_id}", response_model=ManagedDatabaseSchema)
async def get_database(
    database_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ManagedDatabaseSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = GetDatabaseHandler(uow=uow)
        database = await handler.handle(GetDatabaseQuery(tenant_id=tenant_id, database_id=database_id))
        return _to_database_schema(database)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database(
    database_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        handler = DeleteDatabaseHandler(uow=uow, settings=get_settings())
        await handler.handle(DeleteDatabaseCommand(tenant_id=tenant_id, database_id=database_id))
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.put("/{database_id}/connection-limit", response_model=ManagedDatabaseSchema)
async def set_database_connection_limit(
    database_id: UUID,
    body: SetConnectionLimitRequest,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ManagedDatabaseSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = SetDatabaseConnectionLimitHandler(uow=uow)
        database = await handler.handle(
            SetDatabaseConnectionLimitCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                max_connections=body.max_connections,
            )
        )
        return _to_database_schema(database)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{database_id}/users", response_model=list[DatabaseUserSchema])
async def list_database_users(
    database_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DatabaseUserSchema]:
    tenant_id = _require_tenant(context)
    try:
        handler = ListDatabaseUsersHandler(uow=uow)
        users = await handler.handle(ListDatabaseUsersQuery(tenant_id=tenant_id, database_id=database_id))
        return [_to_user_schema(u) for u in users]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{database_id}/users", response_model=DatabaseUserCreatedSchema, status_code=status.HTTP_201_CREATED)
async def create_database_user(
    database_id: UUID,
    body: CreateDatabaseUserRequest,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DatabaseUserCreatedSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = CreateDatabaseUserHandler(uow=uow, settings=get_settings())
        user, password = await handler.handle(
            CreateDatabaseUserCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                username=body.username,
                password=body.password,
                host=body.host,
                max_connections=body.max_connections,
                grants=body.grants,
            )
        )
        schema = _to_user_schema(user)
        return DatabaseUserCreatedSchema(**schema.model_dump(), password=password)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.put("/{database_id}/users/{user_id}/password", response_model=DatabaseUserCreatedSchema)
async def change_database_user_password(
    database_id: UUID,
    user_id: UUID,
    body: ChangePasswordRequest,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DatabaseUserCreatedSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = ChangeDatabaseUserPasswordHandler(uow=uow, settings=get_settings())
        user, password = await handler.handle(
            ChangeDatabaseUserPasswordCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                user_id=user_id,
                password=body.password,
            )
        )
        schema = _to_user_schema(user)
        return DatabaseUserCreatedSchema(**schema.model_dump(), password=password)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.put("/{database_id}/users/{user_id}/connection-limit", response_model=DatabaseUserSchema)
async def set_database_user_connection_limit(
    database_id: UUID,
    user_id: UUID,
    body: SetUserConnectionLimitRequest,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DatabaseUserSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = SetDatabaseUserConnectionLimitHandler(uow=uow, settings=get_settings())
        user = await handler.handle(
            SetDatabaseUserConnectionLimitCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                user_id=user_id,
                max_connections=body.max_connections,
            )
        )
        return _to_user_schema(user)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/{database_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database_user(
    database_id: UUID,
    user_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        handler = DeleteDatabaseUserHandler(uow=uow, settings=get_settings())
        await handler.handle(
            DeleteDatabaseUserCommand(tenant_id=tenant_id, database_id=database_id, user_id=user_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/{database_id}/backups", response_model=list[DatabaseBackupSchema])
async def list_database_backups(
    database_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 20,
) -> list[DatabaseBackupSchema]:
    tenant_id = _require_tenant(context)
    try:
        handler = ListDatabaseBackupsHandler(uow=uow)
        backups = await handler.handle(
            ListDatabaseBackupsQuery(tenant_id=tenant_id, database_id=database_id, limit=limit)
        )
        return [_to_backup_schema(b) for b in backups]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{database_id}/backups", response_model=DatabaseBackupSchema, status_code=status.HTTP_201_CREATED)
async def create_database_backup(
    database_id: UUID,
    body: CreateBackupRequest,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DatabaseBackupSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = CreateDatabaseBackupHandler(uow=uow, settings=get_settings())
        backup = await handler.handle(
            CreateDatabaseBackupCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                name=body.name,
                retention_days=body.retention_days,
            )
        )
        return _to_backup_schema(backup)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/{database_id}/backups/{backup_id}/restore", response_model=DatabaseBackupSchema)
async def restore_database_backup(
    database_id: UUID,
    backup_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DatabaseBackupSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = RestoreDatabaseBackupHandler(uow=uow, settings=get_settings())
        backup = await handler.handle(
            RestoreDatabaseBackupCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                backup_id=backup_id,
            )
        )
        return _to_backup_schema(backup)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/{database_id}/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database_backup(
    database_id: UUID,
    backup_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("databases.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        handler = DeleteDatabaseBackupHandler(uow=uow)
        await handler.handle(
            DeleteDatabaseBackupCommand(
                tenant_id=tenant_id,
                database_id=database_id,
                backup_id=backup_id,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
