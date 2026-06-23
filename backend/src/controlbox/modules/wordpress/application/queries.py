from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from controlbox.modules.wordpress.infrastructure.site_access import WordPressSiteAccessInfo


@dataclass(frozen=True)
class ListWordPressSitesQuery:
    tenant_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetWordPressSiteQuery:
    site_id: UUID
    tenant_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False


@dataclass(frozen=True)
class ListWordPressBackupsQuery:
    site_id: UUID
    tenant_id: UUID


@dataclass(frozen=True)
class WordPressSiteResponse:
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
    error_message: str | None
    task_id: str | None
    created_at: datetime
    updated_at: datetime
    access_info: "WordPressSiteAccessInfo | None" = None


@dataclass(frozen=True)
class WordPressBackupResponse:
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


@dataclass(frozen=True)
class WordPressOptionsResponse:
    php_versions: list[str]
    wordpress_version: str
