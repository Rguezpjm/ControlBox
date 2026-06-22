from controlbox.modules.identity.domain.entities import (
    AuditLog,
    Permission,
    Role,
    Session,
    Tenant,
    TenantStatus,
    User,
)
from controlbox.modules.identity.infrastructure.models import (
    AuditLogModel,
    PermissionModel,
    RoleModel,
    SessionModel,
    TenantModel,
    UserModel,
)


def tenant_to_entity(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        name=model.name,
        slug=model.slug,
        status=TenantStatus(model.status),
        settings=model.settings or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def tenant_to_model(entity: Tenant) -> TenantModel:
    return TenantModel(
        id=entity.id,
        name=entity.name,
        slug=entity.slug,
        status=entity.status.value,
        settings=entity.settings,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def user_to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        tenant_id=model.tenant_id,
        email=model.email,
        password_hash=model.password_hash,
        full_name=model.full_name,
        is_active=model.is_active,
        is_platform_admin=model.is_platform_admin,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_to_model(entity: User) -> UserModel:
    return UserModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        email=entity.email,
        password_hash=entity.password_hash,
        full_name=entity.full_name,
        is_active=entity.is_active,
        is_platform_admin=entity.is_platform_admin,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def permission_to_entity(model: PermissionModel) -> Permission:
    return Permission(
        id=model.id,
        code=model.code,
        name=model.name,
        module=model.module,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def permission_to_model(entity: Permission) -> PermissionModel:
    return PermissionModel(
        id=entity.id,
        code=entity.code,
        name=entity.name,
        module=entity.module,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def role_to_entity(model: RoleModel) -> Role:
    permissions = [permission_to_entity(permission) for permission in model.permissions]
    return Role(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        description=model.description,
        is_system=model.is_system,
        permissions=permissions,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def role_to_model(entity: Role) -> RoleModel:
    return RoleModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        description=entity.description,
        is_system=entity.is_system,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def session_to_entity(model: SessionModel) -> Session:
    return Session(
        id=model.id,
        user_id=model.user_id,
        tenant_id=model.tenant_id,
        refresh_token_hash=model.refresh_token_hash,
        user_agent=model.user_agent,
        ip_address=model.ip_address,
        device_fingerprint=model.device_fingerprint,
        is_revoked=model.is_revoked,
        expires_at=model.expires_at,
        rotated_from_id=model.rotated_from_id,
        last_used_at=model.last_used_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def session_to_model(entity: Session) -> SessionModel:
    return SessionModel(
        id=entity.id,
        user_id=entity.user_id,
        tenant_id=entity.tenant_id,
        refresh_token_hash=entity.refresh_token_hash,
        user_agent=entity.user_agent,
        ip_address=entity.ip_address,
        device_fingerprint=entity.device_fingerprint,
        is_revoked=entity.is_revoked,
        expires_at=entity.expires_at,
        rotated_from_id=entity.rotated_from_id,
        last_used_at=entity.last_used_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def audit_log_to_entity(model: AuditLogModel) -> AuditLog:
    return AuditLog(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        action=model.action,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        metadata=model.metadata_ or {},
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        created_at=model.created_at,
        updated_at=model.created_at,
    )


def audit_log_to_model(entity: AuditLog) -> AuditLogModel:
    return AuditLogModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        user_id=entity.user_id,
        action=entity.action,
        resource_type=entity.resource_type,
        resource_id=entity.resource_id,
        metadata_=entity.metadata,
        ip_address=entity.ip_address,
        user_agent=entity.user_agent,
        created_at=entity.created_at,
    )
