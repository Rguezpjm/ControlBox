from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CreateWordPressSiteCommand:
    tenant_id: UUID
    user_id: UUID
    name: str
    domain: str
    admin_user: str
    admin_password: str
    admin_email: str
    php_version: str = "8.3"
    ssl_enabled: bool = True
    create_ftp_account: bool = False
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None


@dataclass(frozen=True)
class DeleteWordPressSiteCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class RestartWordPressSiteCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class ChangePhpVersionCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID
    php_version: str


@dataclass(frozen=True)
class ToggleMaintenanceCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID
    enabled: bool


@dataclass(frozen=True)
class ChangeWordPressAdminPasswordCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID
    new_password: str


@dataclass(frozen=True)
class CloneWordPressSiteCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID
    new_domain: str
    new_name: str


@dataclass(frozen=True)
class CreateStagingCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class CreateWordPressBackupCommand:
    site_id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str | None = None


@dataclass(frozen=True)
class RestoreWordPressBackupCommand:
    site_id: UUID
    backup_id: UUID
    tenant_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class ProvisionWordPressSiteCommand:
    site_id: UUID
    admin_password: str
