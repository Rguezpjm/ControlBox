from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.identity.domain.entities import (
    AuditLog,
    Permission,
    Role,
    Session,
    Tenant,
    User,
)


class TenantRepository(ABC):
    @abstractmethod
    async def add(self, tenant: Tenant) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Tenant | None:
        raise NotImplementedError

    @abstractmethod
    async def exists_by_slug(self, slug: str) -> bool:
        raise NotImplementedError


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str, tenant_id: UUID | None = None) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, user_id: UUID, tenant_id: UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def assign_role(self, user_id: UUID, role_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_roles(self, user_id: UUID) -> list[Role]:
        raise NotImplementedError

    @abstractmethod
    async def get_permissions(self, user_id: UUID) -> list[Permission]:
        raise NotImplementedError


class RoleRepository(ABC):
    @abstractmethod
    async def add(self, role: Role) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, role_id: UUID) -> Role | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_name(self, name: str, tenant_id: UUID | None = None) -> Role | None:
        raise NotImplementedError

    @abstractmethod
    async def assign_permission(self, role_id: UUID, permission_id: UUID) -> None:
        raise NotImplementedError


class PermissionRepository(ABC):
    @abstractmethod
    async def add(self, permission: Permission) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, permission_id: UUID) -> Permission | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_code(self, code: str) -> Permission | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[Permission]:
        raise NotImplementedError


class SessionRepository(ABC):
    @abstractmethod
    async def add(self, session: Session) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, session: Session) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> Session | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_refresh_token_hash(self, token_hash: str) -> Session | None:
        raise NotImplementedError

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID) -> int:
        raise NotImplementedError

    @abstractmethod
    async def list_active_by_user(self, user_id: UUID) -> list[Session]:
        raise NotImplementedError


class AuditLogRepository(ABC):
    @abstractmethod
    async def add(self, audit_log: AuditLog) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[AuditLog]:
        raise NotImplementedError
