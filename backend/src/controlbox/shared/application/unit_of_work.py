from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controlbox.modules.identity.infrastructure.repositories import (
        AuditLogRepository,
        PermissionRepository,
        RoleRepository,
        SessionRepository,
        TenantRepository,
        UserRepository,
    )
    from controlbox.modules.websites.infrastructure.repositories import WebsiteRepository
    from controlbox.modules.databases.infrastructure.repositories import (
        DatabaseBackupRepository,
        DatabaseUserRepository,
        ManagedDatabaseRepository,
    )
    from controlbox.modules.supabase.infrastructure.repositories import (
        SupabaseBucketRepository,
        SupabaseProjectRepository,
        SupabaseRealtimeChannelRepository,
        SupabaseRlsPolicyRepository,
        SupabaseSchemaRepository,
    )
    from controlbox.modules.dns.infrastructure.repositories import DnsApiKeyRepository, DnsZoneRepository
    from controlbox.modules.ftp.infrastructure.repositories import FtpAccountRepository
    from controlbox.modules.backups.infrastructure.repositories import (
        BackupDestinationRepository,
        BackupJobRepository,
        BackupScheduleRepository,
    )
    from controlbox.modules.wordpress.infrastructure.repositories import (
        WordPressBackupRepository,
        WordPressSiteRepository,
    )
    from controlbox.modules.staging_sites.domain.repositories import StagingSiteRepository
    from controlbox.modules.platform.domain.repositories import ResourceAlertRepository, TenantPlatformSettingsRepository
    from controlbox.modules.team_members.domain.repositories import (
        TeamInvitationRepository,
        TeamMemberRepository,
        TeamRoleRepository,
    )


class UnitOfWork(ABC):
    tenants: "TenantRepository"
    users: "UserRepository"
    roles: "RoleRepository"
    permissions: "PermissionRepository"
    sessions: "SessionRepository"
    audit_logs: "AuditLogRepository"
    websites: "WebsiteRepository"
    managed_databases: "ManagedDatabaseRepository"
    database_users: "DatabaseUserRepository"
    database_backups: "DatabaseBackupRepository"
    supabase_projects: "SupabaseProjectRepository"
    supabase_schemas: "SupabaseSchemaRepository"
    supabase_buckets: "SupabaseBucketRepository"
    supabase_realtime_channels: "SupabaseRealtimeChannelRepository"
    supabase_rls_policies: "SupabaseRlsPolicyRepository"
    dns_zones: "DnsZoneRepository"
    dns_api_keys: "DnsApiKeyRepository"
    ftp_accounts: "FtpAccountRepository"
    backup_destinations: "BackupDestinationRepository"
    backup_schedules: "BackupScheduleRepository"
    backup_jobs: "BackupJobRepository"
    wordpress_sites: "WordPressSiteRepository"
    wordpress_backups: "WordPressBackupRepository"
    staging_sites: "StagingSiteRepository"
    tenant_platform_settings: "TenantPlatformSettingsRepository"
    resource_alerts: "ResourceAlertRepository"
    team_roles: "TeamRoleRepository"
    team_members: "TeamMemberRepository"
    team_invitations: "TeamInvitationRepository"
    user_mfa: "SqlAlchemyUserMfaRepository"
    webauthn_credentials: "SqlAlchemyWebAuthnCredentialRepository"
    trusted_devices: "SqlAlchemyTrustedDeviceRepository"
    security_events: "SqlAlchemySecurityEventRepository"

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def flush(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        raise NotImplementedError
