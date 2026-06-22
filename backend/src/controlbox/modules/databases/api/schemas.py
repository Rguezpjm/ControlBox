from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDatabaseRequest(BaseModel):
    name: str = Field(min_length=2, max_length=63)
    engine: str
    charset: str = "utf8mb4"
    max_connections: int = Field(default=50, ge=1, le=1000)


class SetConnectionLimitRequest(BaseModel):
    max_connections: int = Field(ge=1, le=1000)


class CreateDatabaseUserRequest(BaseModel):
    username: str = Field(min_length=2, max_length=31)
    password: str | None = None
    host: str = "%"
    max_connections: int = Field(default=10, ge=1, le=500)
    grants: list[str] | None = None


class ChangePasswordRequest(BaseModel):
    password: str | None = None


class SetUserConnectionLimitRequest(BaseModel):
    max_connections: int = Field(ge=1, le=500)


class CreateBackupRequest(BaseModel):
    name: str | None = None
    retention_days: int = Field(default=7, ge=1, le=90)


class EngineOptionSchema(BaseModel):
    engine: str
    label: str
    default_port: int
    supports_connection_limit: bool


class DatabaseOptionsSchema(BaseModel):
    engines: list[EngineOptionSchema]


class ManagedDatabaseSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    engine: str
    status: str
    host: str
    port: int
    database_name: str
    charset: str
    max_connections: int
    size_mb: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DatabaseUserSchema(BaseModel):
    id: UUID
    database_id: UUID
    username: str
    host: str
    max_connections: int
    is_active: bool
    grants: list[str]
    created_at: datetime
    updated_at: datetime


class DatabaseUserCreatedSchema(DatabaseUserSchema):
    password: str


class DatabaseBackupSchema(BaseModel):
    id: UUID
    database_id: UUID
    name: str
    backup_type: str
    status: str
    size_mb: int
    retention_days: int
    error_message: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
