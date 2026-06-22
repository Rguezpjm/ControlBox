from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSupabaseProjectRequest(BaseModel):
    name: str = Field(min_length=2, max_length=49)


class CreateSchemaRequest(BaseModel):
    name: str = Field(min_length=2, max_length=63)


class SupabaseServiceStatusSchema(BaseModel):
    enabled: bool
    profile_enabled: bool
    status: str
    host: str
    port: int
    message: str


class CreateBucketRequest(BaseModel):
    name: str = Field(min_length=2, max_length=48)
    public: bool = False
    file_size_limit_mb: int = Field(default=50, ge=1, le=500)


class CreateRealtimeChannelRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    table_name: str = Field(min_length=1, max_length=128)
    schema_name: str = "public"
    events: list[str] | None = None


class CreateRlsPolicyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    table_name: str = Field(min_length=1, max_length=128)
    schema_name: str = "public"
    action: str = "ALL"
    role_name: str = "authenticated"
    using_expression: str = "true"
    check_expression: str | None = None


class SupabaseProjectSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    status: str
    project_ref: str
    database_name: str
    database_user: str
    api_url: str
    studio_url: str
    storage_used_mb: int
    database_size_mb: int
    requests_count: int
    error_message: str | None
    suspended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SupabaseCredentialsSchema(BaseModel):
    database_name: str
    database_user: str
    database_password: str
    anon_key: str
    service_role_key: str
    api_url: str
    studio_url: str
    connection_url: str


class SupabaseUsageSchema(BaseModel):
    database_size_mb: int
    storage_used_mb: int
    buckets_count: int
    schemas_count: int
    realtime_channels_count: int
    rls_policies_count: int
    requests_count: int


class SupabaseSchemaSchema(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    is_default: bool
    created_at: datetime


class SupabaseBucketSchema(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    public: bool
    file_size_limit_mb: int
    status: str
    objects_count: int
    size_mb: int
    created_at: datetime


class SupabaseRealtimeChannelSchema(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    table_name: str
    schema_name: str
    events: list[str]
    is_active: bool
    created_at: datetime


class SupabaseRlsPolicySchema(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    table_name: str
    schema_name: str
    action: str
    role_name: str
    using_expression: str
    check_expression: str | None
    is_enabled: bool
    created_at: datetime
