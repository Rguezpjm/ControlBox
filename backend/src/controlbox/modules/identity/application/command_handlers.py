from controlbox.modules.identity.application.commands import (
    AssignRoleCommand,
    CreateRoleCommand,
    CreateUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
    RegisterTenantCommand,
    RevokeAllSessionsCommand,
)
from controlbox.modules.identity.application.queries import (
    AuditLogResponse,
    PermissionResponse,
    RoleResponse,
    SessionResponse,
    TenantResponse,
    TokenResponse,
    UserResponse,
)
from controlbox.modules.identity.domain.entities import AuditLog, Permission, Role, Tenant, TenantStatus, User
from controlbox.modules.identity.domain.services import PasswordService, SessionService, TokenService
from controlbox.modules.identity.domain.tenant_service import TenantDomainService, UserDomainService
from controlbox.shared.application.cqrs import CommandHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ConflictError, ForbiddenError, NotFoundError, TenantSlug, ValidationError, utc_now
from controlbox.config.settings import Settings
from controlbox.modules.security.application.command_handlers import _upsert_trusted_device, create_mfa_challenge_if_needed
from controlbox.modules.security.application.queries import MfaChallengeResponse
from controlbox.modules.security.application.security_events import SecurityEventRecorder
from controlbox.modules.team_members.application.auth_resolver import resolve_effective_auth
from controlbox.modules.team_members.domain.entities import TeamMember, TeamMemberStatus
from controlbox.modules.security.domain.services import MfaChallengeStore, MfaService
from controlbox.shared.infrastructure.security.audit import record_audit
from controlbox.shared.infrastructure.redis.client import SessionCache
from controlbox.shared.infrastructure.security.protection import IpReputation

import logging

_auth_logger = logging.getLogger("controlbox.auth")


DEFAULT_PERMISSIONS = [
    ("tenants.read", "Read Tenants", "tenants"),
    ("tenants.manage", "Manage Tenants", "tenants"),
    ("users.read", "Read Users", "users"),
    ("users.manage", "Manage Users", "users"),
    ("roles.read", "Read Roles", "roles"),
    ("roles.manage", "Manage Roles", "roles"),
    ("sessions.read", "Read Sessions", "sessions"),
    ("sessions.manage", "Manage Sessions", "sessions"),
    ("audit.read", "Read Audit Logs", "audit"),
    ("websites.read", "Read Websites", "websites"),
    ("websites.manage", "Manage Websites", "websites"),
    ("databases.read", "Read Databases", "databases"),
    ("databases.manage", "Manage Databases", "databases"),
    ("supabase.read", "Read Supabase", "supabase"),
    ("supabase.manage", "Manage Supabase", "supabase"),
    ("dns.read", "Read DNS", "dns"),
    ("dns.manage", "Manage DNS", "dns"),
    ("files.read", "Read Files", "files"),
    ("files.manage", "Manage Files", "files"),
    ("ftp.read", "Read FTP", "ftp"),
    ("ftp.manage", "Manage FTP", "ftp"),
    ("mail.read", "Read Mail", "mail"),
    ("mail.manage", "Manage Mail", "mail"),
    ("backups.read", "Read Backups", "backups"),
    ("backups.manage", "Manage Backups", "backups"),
    ("monitoring.read", "Read Monitoring", "monitoring"),
    ("security.read", "Read Security", "security"),
    ("security.manage", "Manage Security", "security"),
    ("wordpress.read", "Read WordPress", "wordpress"),
    ("wordpress.manage", "Manage WordPress", "wordpress"),
    ("team_members.read", "Read Team Members", "team_members"),
    ("team_members.manage", "Manage Team Members", "team_members"),
    ("billing.read", "Read Billing", "billing"),
    ("billing.manage", "Manage Billing", "billing"),
    ("staging.read", "Read Staging", "staging"),
    ("staging.manage", "Manage Staging", "staging"),
    ("platform.read", "Read Platform Settings", "platform"),
    ("platform.manage", "Manage Platform Settings", "platform"),
]


class RegisterTenantHandler(CommandHandler[RegisterTenantCommand, tuple[TenantResponse, UserResponse, TokenResponse]]):
    def __init__(
        self,
        uow: UnitOfWork,
        password_service: PasswordService,
        token_service: TokenService,
        session_service: SessionService,
        session_cache: SessionCache,
    ) -> None:
        self._uow = uow
        self._passwords = password_service
        self._tokens = token_service
        self._sessions = session_service
        self._session_cache = session_cache

    async def handle(self, command: RegisterTenantCommand) -> tuple[TenantResponse, UserResponse, TokenResponse]:
        slug = TenantSlug(command.slug).value
        tenant_service = TenantDomainService(self._uow.tenants)
        user_service = UserDomainService(self._uow.users, self._passwords)

        await tenant_service.ensure_slug_available(slug)
        user_service.validate_password_strength(command.admin_password)

        tenant = Tenant(
            name=command.name,
            slug=slug,
            status=TenantStatus.ACTIVE,
        )
        await self._uow.tenants.add(tenant)
        await self._uow.flush()

        for code, name, module in DEFAULT_PERMISSIONS:
            existing = await self._uow.permissions.get_by_code(code)
            if existing is None:
                await self._uow.permissions.add(Permission(code=code, name=name, module=module))

        all_permissions = await self._uow.permissions.list_all()
        admin_role = Role(
            tenant_id=tenant.id,
            name="admin",
            description="Tenant administrator",
            is_system=True,
        )
        await self._uow.roles.add(admin_role)
        await self._uow.flush()

        for permission in all_permissions:
            await self._uow.roles.assign_permission(admin_role.id, permission.id)

        member_role = Role(
            tenant_id=tenant.id,
            name="member",
            description="Tenant member",
            is_system=True,
        )
        await self._uow.roles.add(member_role)
        await self._uow.flush()

        read_permissions = [permission for permission in all_permissions if permission.code.endswith(".read")]
        for permission in read_permissions:
            await self._uow.roles.assign_permission(member_role.id, permission.id)

        admin_user = User(
            tenant_id=tenant.id,
            email=command.admin_email.lower(),
            password_hash=self._passwords.hash(command.admin_password),
            full_name=command.admin_full_name,
            is_active=True,
            is_platform_admin=True,
        )
        await self._uow.users.add(admin_user)
        await self._uow.flush()
        await self._uow.users.assign_role(admin_user.id, admin_role.id)

        owner_role = await self._uow.team_roles.get_by_slug("owner")
        if owner_role is None:
            raise NotFoundError("Team role 'owner' not found; run database migrations")
        await self._uow.team_members.add(
            TeamMember(
                tenant_id=tenant.id,
                user_id=admin_user.id,
                team_role_id=owner_role.id,
                status=TeamMemberStatus.ACTIVE,
                joined_at=utc_now(),
            )
        )

        session, refresh_token = self._sessions.create_session(
            user=admin_user,
            user_agent=None,
            ip_address=None,
            device_fingerprint=None,
        )
        await self._uow.sessions.add(session)
        await self._uow.flush()

        role_names, permission_codes = await resolve_effective_auth(self._uow, admin_user.id, tenant.id)

        access_token, access_expires = self._tokens.create_access_token(
            user=admin_user,
            session_id=session.id,
            roles=role_names,
            permissions=permission_codes,
        )

        await self._session_cache.store_session(
            session_id=session.id,
            user_id=admin_user.id,
            tenant_id=tenant.id,
            ttl_seconds=self._session_cache.refresh_ttl_seconds(),
        )

        await self._uow.flush()

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=tenant.id,
                user_id=admin_user.id,
                action="tenant.registered",
                resource_type="tenant",
                resource_id=str(tenant.id),
                metadata={"slug": tenant.slug},
            )
        )

        await self._uow.commit()

        return (
            TenantResponse(
                id=tenant.id,
                name=tenant.name,
                slug=tenant.slug,
                status=tenant.status.value,
                settings=tenant.settings,
            ),
            UserResponse(
                id=admin_user.id,
                tenant_id=admin_user.tenant_id,
                email=admin_user.email,
                full_name=admin_user.full_name,
                is_active=admin_user.is_active,
                is_platform_admin=admin_user.is_platform_admin,
                roles=role_names,
                permissions=permission_codes,
            ),
            TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                access_token_expires_at=access_expires,
                refresh_token_expires_at=session.expires_at,
                session_id=session.id,
            ),
        )


class LoginHandler(CommandHandler[LoginCommand, TokenResponse | MfaChallengeResponse]):
    def __init__(
        self,
        uow: UnitOfWork,
        password_service: PasswordService,
        token_service: TokenService,
        session_service: SessionService,
        session_cache: SessionCache,
        settings: Settings,
        ip_reputation: IpReputation | None = None,
        mfa_service: MfaService | None = None,
        challenge_store: MfaChallengeStore | None = None,
        events: SecurityEventRecorder | None = None,
    ) -> None:
        self._uow = uow
        self._passwords = password_service
        self._tokens = token_service
        self._sessions = session_service
        self._session_cache = session_cache
        self._settings = settings
        self._ip = ip_reputation
        self._mfa = mfa_service
        self._challenges = challenge_store
        self._events = events or SecurityEventRecorder()

    async def handle(self, command: LoginCommand) -> TokenResponse | MfaChallengeResponse:
        if command.ip_address and self._ip and await self._ip.is_blocked(command.ip_address):
            raise NotFoundError("Invalid credentials")

        tenant_id = None
        tenant = None
        if command.tenant_slug:
            tenant = await self._uow.tenants.get_by_slug(command.tenant_slug)
            if tenant is None:
                raise NotFoundError("Tenant not found")
            TenantDomainService(self._uow.tenants).ensure_tenant_active(tenant)
            tenant_id = tenant.id

        user_service = UserDomainService(self._uow.users, self._passwords)
        try:
            user = await user_service.authenticate(command.email, command.password, tenant_id)
        except NotFoundError:
            if command.ip_address and self._ip and self._settings.security_brute_force_enabled:
                count = await self._ip.record_failed_login(command.ip_address, command.email)
                if count >= self._settings.security_brute_force_max_attempts:
                    await self._ip.block(
                        command.ip_address,
                        "brute_force",
                        self._settings.security_brute_force_block_seconds,
                    )
                    await self._events.record(
                        self._uow,
                        tenant_id=tenant_id,
                        user_id=None,
                        event_type="ip_blocked",
                        severity="high",
                        message=f"IP blocked after {count} failed login attempts",
                        ip_address=command.ip_address,
                        user_agent=command.user_agent,
                    )
            await record_audit(
                self._uow,
                tenant_id=tenant_id,
                user_id=None,
                action="auth.login_failed",
                resource_type="user",
                resource_id=command.email,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
            _auth_logger.warning(
                "Login failed",
                extra={"action": "auth.login_failed", "ip": command.ip_address, "email": command.email},
            )
            await self._uow.commit()
            raise

        if tenant and user.tenant_id != tenant.id:
            raise NotFoundError("Invalid credentials")

        if command.ip_address and self._ip:
            await self._ip.clear_failed_logins(command.ip_address)

        if self._mfa and self._challenges:
            challenge = await create_mfa_challenge_if_needed(
                self._uow,
                user.id,
                self._mfa,
                self._challenges,
                {
                    "user_agent": command.user_agent,
                    "ip_address": command.ip_address,
                    "device_fingerprint": command.device_fingerprint,
                },
            )
            if challenge:
                await self._uow.commit()
                return challenge

        session, refresh_token = self._sessions.create_session(
            user=user,
            user_agent=command.user_agent,
            ip_address=command.ip_address,
            device_fingerprint=command.device_fingerprint,
        )
        await self._uow.sessions.add(session)

        if command.device_fingerprint:
            await _upsert_trusted_device(
                self._uow,
                user.id,
                command.device_fingerprint,
                command.user_agent,
                command.ip_address,
            )

        role_names, permission_codes = await resolve_effective_auth(self._uow, user.id, user.tenant_id)

        access_token, access_expires = self._tokens.create_access_token(
            user=user,
            session_id=session.id,
            roles=role_names,
            permissions=permission_codes,
        )

        await self._session_cache.store_session(
            session_id=session.id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            ttl_seconds=self._session_cache.refresh_ttl_seconds(),
        )

        await record_audit(
            self._uow,
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.login",
            resource_type="session",
            resource_id=str(session.id),
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        await self._events.record(
            self._uow,
            tenant_id=user.tenant_id,
            user_id=user.id,
            event_type="login_success",
            severity="low",
            message="Successful login",
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )

        await self._uow.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            access_token_expires_at=access_expires,
            refresh_token_expires_at=session.expires_at,
            session_id=session.id,
        )


class RefreshTokenHandler(CommandHandler[RefreshTokenCommand, TokenResponse]):
    def __init__(
        self,
        uow: UnitOfWork,
        token_service: TokenService,
        session_service: SessionService,
        session_cache: SessionCache,
    ) -> None:
        self._uow = uow
        self._tokens = token_service
        self._sessions = session_service
        self._session_cache = session_cache

    async def handle(self, command: RefreshTokenCommand) -> TokenResponse:
        token_hash = self._tokens.hash_token(command.refresh_token)
        session = await self._uow.sessions.get_by_refresh_token_hash(token_hash)
        if session is None:
            raise NotFoundError("Invalid refresh token")

        user = await self._uow.users.get_by_id(session.user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User not found")

        old_session, new_session, new_refresh_token = self._sessions.rotate_session(
            session=session,
            user=user,
            raw_refresh_token=command.refresh_token,
            user_agent=command.user_agent,
            ip_address=command.ip_address,
            device_fingerprint=command.device_fingerprint,
        )
        old_session.mark_used(utc_now())
        new_session.mark_used(utc_now())

        await self._uow.sessions.save(old_session)
        await self._uow.sessions.add(new_session)

        role_names, permission_codes = await resolve_effective_auth(self._uow, user.id, user.tenant_id)

        access_token, access_expires = self._tokens.create_access_token(
            user=user,
            session_id=new_session.id,
            roles=role_names,
            permissions=permission_codes,
        )

        await self._session_cache.revoke_session(old_session.id)
        await self._session_cache.store_session(
            session_id=new_session.id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            ttl_seconds=self._session_cache.refresh_ttl_seconds(),
        )

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="auth.refresh",
                resource_type="session",
                resource_id=str(new_session.id),
                metadata={"rotated_from": str(old_session.id)},
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )

        await self._uow.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            access_token_expires_at=access_expires,
            refresh_token_expires_at=new_session.expires_at,
            session_id=new_session.id,
        )


class LogoutHandler(CommandHandler[LogoutCommand, None]):
    def __init__(
        self,
        uow: UnitOfWork,
        session_cache: SessionCache,
    ) -> None:
        self._uow = uow
        self._session_cache = session_cache

    async def handle(self, command: LogoutCommand) -> None:
        session = await self._uow.sessions.get_by_id(command.session_id)
        if session is None or session.user_id != command.user_id:
            raise NotFoundError("Session not found")

        session.revoke()
        await self._uow.sessions.save(session)
        await self._session_cache.revoke_session(session.id)

        if command.access_token_jti and command.access_token_exp:
            ttl = max(command.access_token_exp - int(utc_now().timestamp()), 1)
            await self._session_cache.blacklist_access_token(command.access_token_jti, ttl)

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=session.tenant_id,
                user_id=command.user_id,
                action="auth.logout",
                resource_type="session",
                resource_id=str(session.id),
            )
        )

        await self._uow.commit()


class RevokeAllSessionsHandler(CommandHandler[RevokeAllSessionsCommand, int]):
    def __init__(
        self,
        uow: UnitOfWork,
        session_cache: SessionCache,
    ) -> None:
        self._uow = uow
        self._session_cache = session_cache

    async def handle(self, command: RevokeAllSessionsCommand) -> int:
        sessions = await self._uow.sessions.list_active_by_user(command.user_id)
        count = await self._uow.sessions.revoke_all_for_user(command.user_id)

        for session in sessions:
            await self._session_cache.revoke_session(session.id)

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                action="auth.revoke_all_sessions",
                resource_type="user",
                resource_id=str(command.user_id),
                metadata={"revoked_count": count},
            )
        )

        await self._uow.commit()
        return count


class CreateUserHandler(CommandHandler[CreateUserCommand, UserResponse]):
    def __init__(
        self,
        uow: UnitOfWork,
        password_service: PasswordService,
    ) -> None:
        self._uow = uow
        self._passwords = password_service

    async def handle(self, command: CreateUserCommand) -> UserResponse:
        tenant = await self._uow.tenants.get_by_id(command.tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found")

        TenantDomainService(self._uow.tenants).ensure_tenant_active(tenant)
        user_service = UserDomainService(self._uow.users, self._passwords)
        await user_service.ensure_email_available(command.email, command.tenant_id)
        user_service.validate_password_strength(command.password)

        role = await self._uow.roles.get_by_name(command.role_name, command.tenant_id)
        if role is None:
            raise NotFoundError("Role not found")

        user = User(
            tenant_id=command.tenant_id,
            email=command.email.lower(),
            password_hash=self._passwords.hash(command.password),
            full_name=command.full_name,
        )
        await self._uow.users.add(user)
        await self._uow.users.assign_role(user.id, role.id)

        roles = await self._uow.users.get_roles(user.id)
        permissions = await self._uow.users.get_permissions(user.id)
        role_names = [r.name for r in roles]
        permission_codes = [p.code for p in permissions]

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=user.id,
                action="user.created",
                resource_type="user",
                resource_id=str(user.id),
            )
        )

        await self._uow.commit()

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


class CreateRoleHandler(CommandHandler[CreateRoleCommand, RoleResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: CreateRoleCommand) -> RoleResponse:
        existing = await self._uow.roles.get_by_name(command.name, command.tenant_id)
        if existing:
            raise ConflictError("Role already exists")

        role = Role(
            tenant_id=command.tenant_id,
            name=command.name,
            description=command.description,
        )
        await self._uow.roles.add(role)

        assigned_codes: list[str] = []
        for code in command.permission_codes:
            permission = await self._uow.permissions.get_by_code(code)
            if permission is None:
                raise NotFoundError(f"Permission '{code}' not found")
            await self._uow.roles.assign_permission(role.id, permission.id)
            assigned_codes.append(code)

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=None,
                action="role.created",
                resource_type="role",
                resource_id=str(role.id),
                metadata={"permissions": assigned_codes},
            )
        )

        await self._uow.commit()

        return RoleResponse(
            id=role.id,
            tenant_id=role.tenant_id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permissions=assigned_codes,
        )


class AssignRoleHandler(CommandHandler[AssignRoleCommand, UserResponse]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: AssignRoleCommand) -> UserResponse:
        user = await self._uow.users.get_by_id_and_tenant(command.user_id, command.tenant_id)
        if user is None:
            raise NotFoundError("User not found")

        role = await self._uow.roles.get_by_id(command.role_id)
        if role is None or role.tenant_id != command.tenant_id:
            raise NotFoundError("Role not found")

        await self._uow.users.assign_role(user.id, role.id)

        roles = await self._uow.users.get_roles(user.id)
        permissions = await self._uow.users.get_permissions(user.id)

        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=user.id,
                action="user.role_assigned",
                resource_type="role",
                resource_id=str(role.id),
            )
        )

        await self._uow.commit()

        return UserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_platform_admin=user.is_platform_admin,
            roles=[r.name for r in roles],
            permissions=[p.code for p in permissions],
        )
