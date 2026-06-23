from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class ListFtpAccountsQuery:
    tenant_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False


@dataclass
class GetFtpAccountQuery:
    tenant_id: UUID
    account_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False


@dataclass
class ListFtpLogsQuery:
    tenant_id: UUID
    account_id: UUID | None
    limit: int
    requester_user_id: UUID | None = None
    can_manage_all: bool = False


@dataclass
class FtpAccountResponse:
    id: UUID
    tenant_id: UUID
    username: str
    system_username: str
    home_directory: str
    status: str
    quota_mb: int
    max_files: int
    upload_bandwidth_kbps: int
    download_bandwidth_kbps: int
    last_login_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class FtpAccountCreatedResponse:
    account: FtpAccountResponse
    password: str


@dataclass
class FtpLogResponse:
    timestamp: datetime
    username: str
    action: str
    path: str | None
    bytes_transferred: int
    ip_address: str | None
    status: str


@dataclass
class FtpServiceStatusResponse:
    enabled: bool
    status: str
    host: str
    port: int | None
    protocol: str = "ftp"
    passive_port_min: int = 30000
    passive_port_max: int = 30009
    public_host: str = ""
    running: bool = False
    can_manage: bool = False
    message: str = ""
