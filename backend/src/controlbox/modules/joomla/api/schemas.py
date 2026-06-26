from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from controlbox.modules.websites.api.schemas import UptimeTimelinePointSchema
from controlbox.shared.domain.email import PanelEmail


class CreateJoomlaSiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=3, max_length=255)
    admin_user: str = Field(min_length=3, max_length=60)
    admin_password: str = Field(min_length=8, max_length=128)
    admin_email: PanelEmail
    php_version: str = "8.3"
    ssl_enabled: bool = True
    create_ftp_account: bool = False
    db_name: str | None = Field(default=None, min_length=2, max_length=63)
    db_user: str | None = Field(default=None, min_length=2, max_length=31)
    db_password: str | None = Field(default=None, min_length=8, max_length=128)


class ChangePhpVersionRequest(BaseModel):
    php_version: str


class ToggleMaintenanceRequest(BaseModel):
    enabled: bool


class CloneJoomlaSiteRequest(BaseModel):
    new_domain: str
    new_name: str


class CreateJoomlaBackupRequest(BaseModel):
    name: str | None = None


class ChangeJoomlaAdminPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class JoomlaSiteAccessSchema(BaseModel):
    site_url: str
    login_url: str
    admin_user: str
    admin_email: str
    db_name: str | None = None
    db_user: str | None = None
    db_host: str | None = None
    db_password: str | None = None
    ftp_username: str | None = None
    ftp_password: str | None = None
    ftp_home: str | None = None


class JoomlaSiteResponseSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    domain: str
    status: str
    php_version: str
    joomla_version: str
    url: str
    admin_user: str
    admin_email: str
    ssl_enabled: bool
    ssl_status: str
    maintenance_mode: bool
    disk_used_mb: int
    db_size_mb: int
    is_staging: bool
    parent_site_id: UUID | None
    ssl_days_remaining: int | None = None
    traffic_mbps: float = 0.0
    traffic_sparkline: list[float] = Field(default_factory=list)
    visit_count: int = 0
    visits_sparkline: list[float] = Field(default_factory=list)
    uptime_timeline: list[UptimeTimelinePointSchema] = Field(default_factory=list)
    uptime_percent: float = 100.0
    last_down_reason: str | None = None
    last_down_reason_label: str | None = None
    is_up: bool = True
    error_message: str | None
    task_id: str | None
    access_info: JoomlaSiteAccessSchema | None = None
    created_at: datetime
    updated_at: datetime


class JoomlaBackupResponseSchema(BaseModel):
    id: UUID
    site_id: UUID
    name: str
    status: str
    size_mb: int
    checksum: str | None
    includes_database: bool
    includes_files: bool
    error_message: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JoomlaOptionsSchema(BaseModel):
    php_versions: list[str]
    joomla_version: str


class JoomlaProvisionStepSchema(BaseModel):
    step: str
    message: str
    at: str


class JoomlaDeployCredentialsSchema(BaseModel):
    site_url: str
    login_url: str
    admin_user: str
    db_name: str
    db_user: str
    db_password: str
    db_host: str = ""
    ftp_username: str | None = None
    ftp_password: str | None = None
    ftp_home: str | None = None


class JoomlaProvisionStatusSchema(BaseModel):
    site_id: UUID
    status: str
    error_message: str | None = None
    steps: list[JoomlaProvisionStepSchema] = Field(default_factory=list)
    credentials: JoomlaDeployCredentialsSchema | None = None
