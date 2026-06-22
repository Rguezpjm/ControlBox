from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateFtpAccountRequest(BaseModel):
    username: str = Field(min_length=2, max_length=31)
    password: str | None = None
    home_directory: str = ""
    quota_mb: int = Field(default=0, ge=0, le=102400)
    max_files: int = Field(default=0, ge=0, le=1_000_000)
    upload_bandwidth_kbps: int = Field(default=0, ge=0)
    download_bandwidth_kbps: int = Field(default=0, ge=0)


class UpdateFtpAccountRequest(BaseModel):
    home_directory: str | None = None
    quota_mb: int | None = Field(default=None, ge=0, le=102400)
    max_files: int | None = Field(default=None, ge=0, le=1_000_000)
    upload_bandwidth_kbps: int | None = Field(default=None, ge=0)
    download_bandwidth_kbps: int | None = Field(default=None, ge=0)


class ChangeFtpPasswordRequest(BaseModel):
    password: str | None = None


class SetFtpQuotaRequest(BaseModel):
    quota_mb: int = Field(ge=0, le=102400)
    max_files: int = Field(default=0, ge=0, le=1_000_000)


class SetFtpDirectoryRequest(BaseModel):
    home_directory: str = Field(max_length=512)


class SetFtpStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")


class FtpAccountSchema(BaseModel):
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


class FtpAccountCreatedSchema(FtpAccountSchema):
    password: str


class FtpPasswordChangedSchema(BaseModel):
    account: FtpAccountSchema
    password: str | None = None


class FtpLogSchema(BaseModel):
    timestamp: datetime
    username: str
    action: str
    path: str | None
    bytes_transferred: int
    ip_address: str | None
    status: str


class FtpServiceStatusSchema(BaseModel):
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


class UpdateFtpServiceRequest(BaseModel):
    enabled: bool
    protocol: str = Field(default="ftp", pattern="^(ftp|ftps|sftp)$")
    port: int = Field(default=21, ge=1, le=65535)
    passive_port_min: int = Field(default=30000, ge=1024, le=65535)
    passive_port_max: int = Field(default=30009, ge=1024, le=65535)
    public_host: str = Field(default="", max_length=255)


class FtpServiceActionResponse(BaseModel):
    success: bool
    message: str
    service: FtpServiceStatusSchema
