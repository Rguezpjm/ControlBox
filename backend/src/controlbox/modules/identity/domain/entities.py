from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import AuditMetadata, Entity


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


@dataclass
class Tenant(Entity):
    name: str = ""
    slug: str = ""
    status: TenantStatus = TenantStatus.PENDING
    settings: dict[str, Any] = field(default_factory=dict)

    def activate(self) -> None:
        self.status = TenantStatus.ACTIVE
        self.touch()

    def suspend(self) -> None:
        self.status = TenantStatus.SUSPENDED
        self.touch()

    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE


@dataclass
class User(Entity):
    tenant_id: UUID | None = None
    email: str = ""
    password_hash: str = ""
    full_name: str = ""
    is_active: bool = True
    is_platform_admin: bool = False

    def deactivate(self) -> None:
        self.is_active = False
        self.touch()

    def activate(self) -> None:
        self.is_active = True
        self.touch()

    def update_profile(self, full_name: str) -> None:
        self.full_name = full_name
        self.touch()


@dataclass
class Permission(Entity):
    code: str = ""
    name: str = ""
    module: str = ""

    def __hash__(self) -> int:
        return hash(self.code)


@dataclass
class Role(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    description: str = ""
    is_system: bool = False
    permissions: list[Permission] = field(default_factory=list)

    def assign_permission(self, permission: Permission) -> None:
        if permission not in self.permissions:
            self.permissions.append(permission)
            self.touch()

    def revoke_permission(self, permission: Permission) -> None:
        if permission in self.permissions:
            self.permissions.remove(permission)
            self.touch()

    def has_permission(self, code: str) -> bool:
        return any(permission.code == code for permission in self.permissions)


@dataclass
class Session(Entity):
    user_id: UUID | None = None
    tenant_id: UUID | None = None
    refresh_token_hash: str = ""
    user_agent: str | None = None
    ip_address: str | None = None
    device_fingerprint: str | None = None
    is_revoked: bool = False
    expires_at: datetime | None = None
    rotated_from_id: UUID | None = None
    last_used_at: datetime | None = None

    def revoke(self) -> None:
        self.is_revoked = True
        self.touch()

    def mark_used(self, used_at: datetime) -> None:
        self.last_used_at = used_at
        self.touch()

    def is_valid(self, now: datetime) -> bool:
        if self.is_revoked:
            return False
        if self.expires_at is None:
            return False
        return self.expires_at > now


@dataclass
class AuditLog(Entity):
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    action: str = ""
    resource_type: str = ""
    resource_id: str | None = None
    metadata: AuditMetadata = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
