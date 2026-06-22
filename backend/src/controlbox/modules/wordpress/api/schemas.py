from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from controlbox.shared.domain.email import PanelEmail


class CreateWordPressSiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=3, max_length=255)
    admin_user: str = Field(min_length=3, max_length=60)
    admin_password: str = Field(min_length=8, max_length=128)
    admin_email: PanelEmail
    php_version: str = "8.3"
    ssl_enabled: bool = True


class ChangePhpVersionRequest(BaseModel):
    php_version: str


class ToggleMaintenanceRequest(BaseModel):
    enabled: bool


class CloneWordPressSiteRequest(BaseModel):
    new_domain: str
    new_name: str


class CreateWordPressBackupRequest(BaseModel):
    name: str | None = None


class WordPressSiteResponseSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    domain: str
    status: str
    php_version: str
    wordpress_version: str
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
    requests_count: int = 0
    requests_sparkline: list[float] = Field(default_factory=list)
    error_message: str | None
    task_id: str | None
    created_at: datetime
    updated_at: datetime


class WordPressBackupResponseSchema(BaseModel):
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


class WordPressOptionsSchema(BaseModel):
    php_versions: list[str]
    wordpress_version: str
