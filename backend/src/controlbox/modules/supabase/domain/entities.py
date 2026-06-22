from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class SupabaseProjectStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ERROR = "error"
    DELETING = "deleting"


class BucketStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class RlsPolicyAction(StrEnum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ALL = "ALL"


@dataclass
class SupabaseProject(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    slug: str = ""
    status: SupabaseProjectStatus = SupabaseProjectStatus.PENDING
    project_ref: str = ""
    database_name: str = ""
    database_user: str = ""
    database_password_encrypted: str = ""
    anon_key: str = ""
    service_role_key: str = ""
    api_url: str = ""
    studio_url: str = ""
    storage_used_mb: int = 0
    database_size_mb: int = 0
    requests_count: int = 0
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    suspended_at: datetime | None = None

    def mark_active(self) -> None:
        self.status = SupabaseProjectStatus.ACTIVE
        self.error_message = None
        self.suspended_at = None
        self.touch()

    def mark_suspended(self) -> None:
        self.status = SupabaseProjectStatus.SUSPENDED
        self.suspended_at = datetime.now()
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = SupabaseProjectStatus.ERROR
        self.error_message = message
        self.touch()


@dataclass
class SupabaseSchema(Entity):
    project_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    is_default: bool = False


@dataclass
class SupabaseBucket(Entity):
    project_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    public: bool = False
    file_size_limit_mb: int = 50
    status: BucketStatus = BucketStatus.ACTIVE
    objects_count: int = 0
    size_mb: int = 0


@dataclass
class SupabaseRealtimeChannel(Entity):
    project_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    table_name: str = ""
    schema_name: str = "public"
    events: list[str] = field(default_factory=lambda: ["INSERT", "UPDATE", "DELETE"])
    is_active: bool = True


@dataclass
class SupabaseRlsPolicy(Entity):
    project_id: UUID | None = None
    tenant_id: UUID | None = None
    name: str = ""
    table_name: str = ""
    schema_name: str = "public"
    action: RlsPolicyAction = RlsPolicyAction.ALL
    role_name: str = "authenticated"
    using_expression: str = "true"
    check_expression: str | None = None
    is_enabled: bool = True
