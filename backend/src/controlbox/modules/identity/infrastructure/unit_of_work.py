from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from controlbox.config.settings import Settings
from controlbox.modules.identity.infrastructure.repositories import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from controlbox.modules.websites.infrastructure.repositories import SqlAlchemyWebsiteRepository
from controlbox.modules.databases.infrastructure.repositories import (
    SqlAlchemyDatabaseBackupRepository,
    SqlAlchemyDatabaseUserRepository,
    SqlAlchemyManagedDatabaseRepository,
)
from controlbox.modules.supabase.infrastructure.repositories import (
    SqlAlchemySupabaseBucketRepository,
    SqlAlchemySupabaseProjectRepository,
    SqlAlchemySupabaseRealtimeChannelRepository,
    SqlAlchemySupabaseRlsPolicyRepository,
    SqlAlchemySupabaseSchemaRepository,
)
from controlbox.modules.dns.infrastructure.repositories import (
    SqlAlchemyDnsApiKeyRepository,
    SqlAlchemyDnsZoneRepository,
)
from controlbox.modules.ftp.infrastructure.repositories import SqlAlchemyFtpAccountRepository
from controlbox.modules.mail.infrastructure.repositories import MailAccountRepository, TenantMailServiceRepository
from controlbox.modules.backups.infrastructure.repositories import (
    SqlAlchemyBackupDestinationRepository,
    SqlAlchemyBackupJobRepository,
    SqlAlchemyBackupScheduleRepository,
)
from controlbox.modules.wordpress.infrastructure.repositories import (
    SqlAlchemyWordPressBackupRepository,
    SqlAlchemyWordPressSiteRepository,
)
from controlbox.modules.staging_sites.infrastructure.repositories import SqlAlchemyStagingSiteRepository
from controlbox.modules.platform.infrastructure.repositories import (
    SqlAlchemyResourceAlertRepository,
    SqlAlchemyTenantPlatformSettingsRepository,
)
from controlbox.modules.team_members.infrastructure.repositories import (
    SqlAlchemyTeamInvitationRepository,
    SqlAlchemyTeamMemberRepository,
    SqlAlchemyTeamRoleRepository,
)
from controlbox.modules.security.infrastructure.repositories import (
    SqlAlchemySecurityEventRepository,
    SqlAlchemyTrustedDeviceRepository,
    SqlAlchemyUserMfaRepository,
    SqlAlchemyWebAuthnCredentialRepository,
)
from controlbox.shared.application.unit_of_work import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.tenants = SqlAlchemyTenantRepository(self._session)
        self.users = SqlAlchemyUserRepository(self._session)
        self.roles = SqlAlchemyRoleRepository(self._session)
        self.permissions = SqlAlchemyPermissionRepository(self._session)
        self.sessions = SqlAlchemySessionRepository(self._session)
        self.audit_logs = SqlAlchemyAuditLogRepository(self._session)
        self.websites = SqlAlchemyWebsiteRepository(self._session)
        self.managed_databases = SqlAlchemyManagedDatabaseRepository(self._session)
        self.database_users = SqlAlchemyDatabaseUserRepository(self._session)
        self.database_backups = SqlAlchemyDatabaseBackupRepository(self._session)
        self.supabase_projects = SqlAlchemySupabaseProjectRepository(self._session)
        self.supabase_schemas = SqlAlchemySupabaseSchemaRepository(self._session)
        self.supabase_buckets = SqlAlchemySupabaseBucketRepository(self._session)
        self.supabase_realtime_channels = SqlAlchemySupabaseRealtimeChannelRepository(self._session)
        self.supabase_rls_policies = SqlAlchemySupabaseRlsPolicyRepository(self._session)
        self.dns_zones = SqlAlchemyDnsZoneRepository(self._session)
        self.dns_api_keys = SqlAlchemyDnsApiKeyRepository(self._session)
        self.ftp_accounts = SqlAlchemyFtpAccountRepository(self._session)
        self.tenant_mail_services = TenantMailServiceRepository(self._session)
        self.mail_accounts = MailAccountRepository(self._session)
        self.backup_destinations = SqlAlchemyBackupDestinationRepository(self._session)
        self.backup_schedules = SqlAlchemyBackupScheduleRepository(self._session)
        self.backup_jobs = SqlAlchemyBackupJobRepository(self._session)
        self.wordpress_sites = SqlAlchemyWordPressSiteRepository(self._session)
        self.wordpress_backups = SqlAlchemyWordPressBackupRepository(self._session)
        self.staging_sites = SqlAlchemyStagingSiteRepository(self._session)
        self.tenant_platform_settings = SqlAlchemyTenantPlatformSettingsRepository(self._session)
        self.resource_alerts = SqlAlchemyResourceAlertRepository(self._session)
        self.team_roles = SqlAlchemyTeamRoleRepository(self._session)
        self.team_members = SqlAlchemyTeamMemberRepository(self._session)
        self.team_invitations = SqlAlchemyTeamInvitationRepository(self._session)
        self.user_mfa = SqlAlchemyUserMfaRepository(self._session)
        self.webauthn_credentials = SqlAlchemyWebAuthnCredentialRepository(self._session)
        self.trusted_devices = SqlAlchemyTrustedDeviceRepository(self._session)
        self.security_events = SqlAlchemySecurityEventRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()
        if self._session:
            await self._session.close()

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def flush(self) -> None:
        if self._session:
            await self._session.flush()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()


class Database:
    def __init__(self, settings: Settings) -> None:
        self._engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.app_debug,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
        )

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def health_check(self) -> bool:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
