from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from controlbox.shared.domain.base import Entity


class FtpAccountStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ERROR = "error"


@dataclass
class FtpAccount(Entity):
    tenant_id: UUID | None = None
    owner_user_id: UUID | None = None
    username: str = ""
    system_username: str = ""
    password_hash: str = ""
    home_directory: str = ""
    status: FtpAccountStatus = FtpAccountStatus.PENDING
    quota_mb: int = 0
    max_files: int = 0
    upload_bandwidth_kbps: int = 0
    download_bandwidth_kbps: int = 0
    uid: int = 1000
    gid: int = 1000
    last_login_at: datetime | None = None
    error_message: str | None = None

    def mark_active(self) -> None:
        self.status = FtpAccountStatus.ACTIVE
        self.error_message = None
        self.touch()

    def mark_suspended(self) -> None:
        self.status = FtpAccountStatus.SUSPENDED
        self.error_message = None
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = FtpAccountStatus.ERROR
        self.error_message = message
        self.touch()


@dataclass
class FtpLogEntry:
    timestamp: datetime
    username: str
    action: str
    path: str | None
    bytes_transferred: int
    ip_address: str | None
    status: str
