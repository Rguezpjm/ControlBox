from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from controlbox.modules.identity.domain.entities import (
    AuditLog,
    Permission,
    Role,
    Session,
    Tenant,
    User,
)
from controlbox.modules.identity.domain.repositories import (
    AuditLogRepository,
    PermissionRepository,
    RoleRepository,
    SessionRepository,
    TenantRepository,
    UserRepository,
)
from controlbox.modules.identity.infrastructure.mappers import (
    audit_log_to_entity,
    audit_log_to_model,
    permission_to_entity,
    permission_to_model,
    role_to_entity,
    role_to_model,
    session_to_entity,
    session_to_model,
    tenant_to_entity,
    tenant_to_model,
    user_to_entity,
    user_to_model,
)
from controlbox.modules.identity.infrastructure.models import (
    AuditLogModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    SessionModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from controlbox.shared.domain.base import utc_now


class SqlAlchemyTenantRepository(TenantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant: Tenant) -> None:
        self._session.add(tenant_to_model(tenant))

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        result = await self._session.execute(select(TenantModel).where(TenantModel.id == tenant_id))
        model = result.scalar_one_or_none()
        return tenant_to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self._session.execute(select(TenantModel).where(TenantModel.slug == slug))
        model = result.scalar_one_or_none()
        return tenant_to_entity(model) if model else None

    async def exists_by_slug(self, slug: str) -> bool:
        result = await self._session.execute(select(func.count()).select_from(TenantModel).where(TenantModel.slug == slug))
        return (result.scalar_one() or 0) > 0

    async def save(self, tenant: Tenant) -> None:
        await self._session.merge(tenant_to_model(tenant))

    async def list_active_ids(self) -> list[UUID]:
        result = await self._session.execute(
            select(TenantModel.id).where(TenantModel.status == "active")
        )
        return [row[0] for row in result.all()]

    async def list_all(self) -> list[Tenant]:
        result = await self._session.execute(
            select(TenantModel).order_by(TenantModel.name.asc())
        )
        return [tenant_to_entity(m) for m in result.scalars().all()]


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(user_to_model(user))

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        return user_to_entity(model) if model else None

    async def get_by_email(self, email: str, tenant_id: UUID | None = None) -> User | None:
        query = select(UserModel).where(UserModel.email == email.lower())
        if tenant_id is not None:
            query = query.where(UserModel.tenant_id == tenant_id)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return user_to_entity(model) if model else None

    async def count_by_email(self, email: str) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(UserModel.email == email.lower())
        )
        return result.scalar_one() or 0

    async def get_by_id_and_tenant(self, user_id: UUID, tenant_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return user_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.tenant_id == tenant_id).order_by(UserModel.full_name.asc())
        )
        return [user_to_entity(m) for m in result.scalars().all()]

    async def assign_role(self, user_id: UUID, role_id: UUID) -> None:
        self._session.add(UserRoleModel(user_id=user_id, role_id=role_id))

    async def save(self, user: User) -> None:
        await self._session.merge(user_to_model(user))

    async def get_roles(self, user_id: UUID) -> list[Role]:
        result = await self._session.execute(
            select(RoleModel)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .where(UserRoleModel.user_id == user_id)
            .options(selectinload(RoleModel.permissions))
        )
        models = result.scalars().all()
        return [role_to_entity(model) for model in models]

    async def get_permissions(self, user_id: UUID) -> list[Permission]:
        result = await self._session.execute(
            select(PermissionModel)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .join(RoleModel, RoleModel.id == RolePermissionModel.role_id)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .where(UserRoleModel.user_id == user_id)
            .distinct()
        )
        models = result.scalars().all()
        return [permission_to_entity(model) for model in models]


class SqlAlchemyRoleRepository(RoleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, role: Role) -> None:
        self._session.add(role_to_model(role))

    async def get_by_id(self, role_id: UUID) -> Role | None:
        result = await self._session.execute(
            select(RoleModel).where(RoleModel.id == role_id).options(selectinload(RoleModel.permissions))
        )
        model = result.scalar_one_or_none()
        return role_to_entity(model) if model else None

    async def get_by_name(self, name: str, tenant_id: UUID | None = None) -> Role | None:
        query = select(RoleModel).where(RoleModel.name == name)
        if tenant_id is not None:
            query = query.where(RoleModel.tenant_id == tenant_id)
        result = await self._session.execute(query.options(selectinload(RoleModel.permissions)))
        model = result.scalar_one_or_none()
        return role_to_entity(model) if model else None

    async def assign_permission(self, role_id: UUID, permission_id: UUID) -> None:
        self._session.add(RolePermissionModel(role_id=role_id, permission_id=permission_id))


class SqlAlchemyPermissionRepository(PermissionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, permission: Permission) -> None:
        self._session.add(permission_to_model(permission))

    async def get_by_id(self, permission_id: UUID) -> Permission | None:
        result = await self._session.execute(select(PermissionModel).where(PermissionModel.id == permission_id))
        model = result.scalar_one_or_none()
        return permission_to_entity(model) if model else None

    async def get_by_code(self, code: str) -> Permission | None:
        result = await self._session.execute(select(PermissionModel).where(PermissionModel.code == code))
        model = result.scalar_one_or_none()
        return permission_to_entity(model) if model else None

    async def list_all(self) -> list[Permission]:
        result = await self._session.execute(select(PermissionModel).order_by(PermissionModel.module, PermissionModel.code))
        models = result.scalars().all()
        return [permission_to_entity(model) for model in models]


class SqlAlchemySessionRepository(SessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session_entity: Session) -> None:
        self._session.add(session_to_model(session_entity))

    async def save(self, session_entity: Session) -> None:
        await self._session.merge(session_to_model(session_entity))

    async def get_by_id(self, session_id: UUID) -> Session | None:
        result = await self._session.execute(select(SessionModel).where(SessionModel.id == session_id))
        model = result.scalar_one_or_none()
        return session_to_entity(model) if model else None

    async def get_by_refresh_token_hash(self, token_hash: str) -> Session | None:
        result = await self._session.execute(
            select(SessionModel).where(
                SessionModel.refresh_token_hash == token_hash,
                SessionModel.is_revoked.is_(False),
            )
        )
        model = result.scalar_one_or_none()
        return session_to_entity(model) if model else None

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            update(SessionModel)
            .where(SessionModel.user_id == user_id, SessionModel.is_revoked.is_(False))
            .values(is_revoked=True, updated_at=utc_now())
        )
        return result.rowcount or 0

    async def list_active_by_user(self, user_id: UUID) -> list[Session]:
        now = utc_now()
        result = await self._session.execute(
            select(SessionModel).where(
                SessionModel.user_id == user_id,
                SessionModel.is_revoked.is_(False),
                SessionModel.expires_at > now,
            )
        )
        models = result.scalars().all()
        return [session_to_entity(model) for model in models]

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[Session]:
        now = utc_now()
        result = await self._session.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == tenant_id,
                SessionModel.is_revoked.is_(False),
                SessionModel.expires_at > now,
            )
        )
        models = result.scalars().all()
        return [session_to_entity(model) for model in models]


class SqlAlchemyAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, audit_log: AuditLog) -> None:
        self._session.add(audit_log_to_model(audit_log))

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[AuditLog]:
        result = await self._session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.tenant_id == tenant_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [audit_log_to_entity(model) for model in models]
