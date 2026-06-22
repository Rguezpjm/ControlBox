from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateSupabaseProjectCommand:
    tenant_id: UUID
    name: str


@dataclass(frozen=True)
class SuspendSupabaseProjectCommand:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class ResumeSupabaseProjectCommand:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class DeleteSupabaseProjectCommand:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class RotateSupabaseKeysCommand:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class CreateSupabaseSchemaCommand:
    tenant_id: UUID
    project_id: UUID
    name: str


@dataclass(frozen=True)
class DeleteSupabaseSchemaCommand:
    tenant_id: UUID
    project_id: UUID
    schema_id: UUID


@dataclass(frozen=True)
class CreateSupabaseBucketCommand:
    tenant_id: UUID
    project_id: UUID
    name: str
    public: bool = False
    file_size_limit_mb: int = 50


@dataclass(frozen=True)
class DeleteSupabaseBucketCommand:
    tenant_id: UUID
    project_id: UUID
    bucket_id: UUID


@dataclass(frozen=True)
class CreateSupabaseRealtimeChannelCommand:
    tenant_id: UUID
    project_id: UUID
    name: str
    table_name: str
    schema_name: str = "public"
    events: list[str] | None = None


@dataclass(frozen=True)
class DeleteSupabaseRealtimeChannelCommand:
    tenant_id: UUID
    project_id: UUID
    channel_id: UUID


@dataclass(frozen=True)
class CreateSupabaseRlsPolicyCommand:
    tenant_id: UUID
    project_id: UUID
    name: str
    table_name: str
    schema_name: str = "public"
    action: str = "ALL"
    role_name: str = "authenticated"
    using_expression: str = "true"
    check_expression: str | None = None


@dataclass(frozen=True)
class DeleteSupabaseRlsPolicyCommand:
    tenant_id: UUID
    project_id: UUID
    policy_id: UUID
