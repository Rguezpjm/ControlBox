from dataclasses import dataclass
from uuid import UUID


@dataclass
class CreateFtpAccountCommand:
    tenant_id: UUID
    username: str
    password: str | None
    home_directory: str
    quota_mb: int
    max_files: int
    upload_bandwidth_kbps: int
    download_bandwidth_kbps: int


@dataclass
class UpdateFtpAccountCommand:
    tenant_id: UUID
    account_id: UUID
    home_directory: str | None
    quota_mb: int | None
    max_files: int | None
    upload_bandwidth_kbps: int | None
    download_bandwidth_kbps: int | None


@dataclass
class ChangeFtpPasswordCommand:
    tenant_id: UUID
    account_id: UUID
    password: str | None


@dataclass
class SetFtpQuotaCommand:
    tenant_id: UUID
    account_id: UUID
    quota_mb: int
    max_files: int


@dataclass
class SetFtpDirectoryCommand:
    tenant_id: UUID
    account_id: UUID
    home_directory: str


@dataclass
class SetFtpStatusCommand:
    tenant_id: UUID
    account_id: UUID
    status: str


@dataclass
class DeleteFtpAccountCommand:
    tenant_id: UUID
    account_id: UUID
