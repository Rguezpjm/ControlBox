from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from controlbox.shared.domain.base import Entity


class TenantMailStatus(StrEnum):
    PENDING = "pending"
    CONFIGURING = "configuring"
    ACTIVE = "active"
    ERROR = "error"


class MailAccountStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ERROR = "error"


@dataclass
class TenantMailService(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    mail_domain: str = ""
    status: TenantMailStatus = TenantMailStatus.PENDING
    imap_host: str = ""
    imap_port: int = 993
    imap_use_ssl: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_ssl: bool = False
    smtp_use_tls: bool = True
    admin_username: str = ""
    admin_password_enc: str | None = None
    default_quota_mb: int = 5120
    total_quota_mb: int = 51200
    webmail_url: str | None = None
    connection_verified_at: datetime | None = None
    error_message: str | None = None

    def mark_configuring(self) -> None:
        self.status = TenantMailStatus.CONFIGURING
        self.error_message = None
        self.touch()

    def mark_active(self) -> None:
        self.status = TenantMailStatus.ACTIVE
        self.error_message = None
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = TenantMailStatus.ERROR
        self.error_message = message
        self.touch()


@dataclass
class MailAccount(Entity):
    tenant_id: UUID | None = None
    mail_service_id: UUID | None = None
    local_part: str = ""
    email_address: str = ""
    display_name: str = ""
    password_hash: str = ""
    status: MailAccountStatus = MailAccountStatus.ACTIVE
    quota_mb: int = 5120
    used_mb: int = 0
    forwarding_to: str | None = None
    error_message: str | None = None

    def mark_suspended(self) -> None:
        self.status = MailAccountStatus.SUSPENDED
        self.touch()

    def mark_active(self) -> None:
        self.status = MailAccountStatus.ACTIVE
        self.touch()
