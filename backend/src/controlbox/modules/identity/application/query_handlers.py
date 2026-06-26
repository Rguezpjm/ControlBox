from controlbox.modules.identity.application.queries import (
    AuditLogResponse,
    GetCurrentUserQuery,
    GetTenantBySlugQuery,
    GetTenantQuery,
    ListAuditLogsQuery,
    ListPermissionsQuery,
    ListSessionsQuery,
    ListTenantsQuery,
    ListUsersByTenantQuery,
    LiteUserResponse,
    PermissionResponse,
    SessionResponse,
    TenantResponse,
    UserResponse,
)
from controlbox.modules.team_members.application.auth_resolver import resolve_effective_auth
from controlbox.shared.application.cqrs import QueryHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


class GetCurrentUserHandler(QueryHandler[GetCurrentUserQuery, UserResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetCurrentUserQuery) -> UserResponse:
        user = await self._uow.users.get_by_id(query.user_id)
        if user is None:
            raise NotFoundError("User not found")

        if query.tenant_id and user.tenant_id != query.tenant_id and not user.is_platform_admin:
            raise NotFoundError("User not found in tenant")

        role_names, permission_codes = await resolve_effective_auth(self._uow, user.id, user.tenant_id)

        return UserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_platform_admin=user.is_platform_admin,
            roles=role_names,
            permissions=permission_codes,
        )


class GetTenantHandler(QueryHandler[GetTenantQuery, TenantResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetTenantQuery) -> TenantResponse:
        tenant = await self._uow.tenants.get_by_id(query.tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found")

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status.value,
            settings=tenant.settings,
        )


class GetTenantBySlugHandler(QueryHandler[GetTenantBySlugQuery, TenantResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetTenantBySlugQuery) -> TenantResponse:
        tenant = await self._uow.tenants.get_by_slug(query.slug)
        if tenant is None:
            raise NotFoundError("Tenant not found")

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status.value,
            settings=tenant.settings,
        )


class ListSessionsHandler(QueryHandler[ListSessionsQuery, list[SessionResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSessionsQuery) -> list[SessionResponse]:
        sessions = await self._uow.sessions.list_active_by_user(query.user_id)
        return [
            SessionResponse(
                id=session.id,
                user_agent=session.user_agent,
                ip_address=session.ip_address,
                device_fingerprint=session.device_fingerprint,
                created_at=session.created_at,
                last_used_at=session.last_used_at,
                expires_at=session.expires_at,
            )
            for session in sessions
        ]


class ListAuditLogsHandler(QueryHandler[ListAuditLogsQuery, list[AuditLogResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListAuditLogsQuery) -> list[AuditLogResponse]:
        logs = await self._uow.audit_logs.list_by_tenant(query.tenant_id, query.limit, query.offset)
        return [
            AuditLogResponse(
                id=log.id,
                tenant_id=log.tenant_id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                metadata=log.metadata,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at,
            )
            for log in logs
        ]


class ListPermissionsHandler(QueryHandler[ListPermissionsQuery, list[PermissionResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListPermissionsQuery) -> list[PermissionResponse]:
        permissions = await self._uow.permissions.list_all()
        return [
            PermissionResponse(
                id=permission.id,
                code=permission.code,
                name=permission.name,
                module=permission.module,
            )
            for permission in permissions
        ]


class ListTenantsHandler(QueryHandler[ListTenantsQuery, list[TenantResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListTenantsQuery) -> list[TenantResponse]:
        tenants = await self._uow.tenants.list_all()
        return [
            TenantResponse(
                id=t.id,
                name=t.name,
                slug=t.slug,
                status=t.status.value,
                settings=t.settings,
            )
            for t in tenants
        ]


class ListUsersByTenantHandler(QueryHandler[ListUsersByTenantQuery, list[LiteUserResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListUsersByTenantQuery) -> list[LiteUserResponse]:
        users = await self._uow.users.list_by_tenant(query.tenant_id)
        return [
            LiteUserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
            )
            for u in users
        ]
