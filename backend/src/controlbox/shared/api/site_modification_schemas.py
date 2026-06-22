from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SiteDomainSchema(BaseModel):
    domain: str
    port: int = 443
    primary: bool = False


class SiteModificationSchema(BaseModel):
    site_type: str
    site_id: UUID
    name: str
    primary_domain: str
    status: str
    created_at: datetime
    runtime: str | None = None
    runtime_version: str | None = None
    php_version: str | None = None
    ssl_enabled: bool
    ssl_status: str
    document_root: str
    settings: dict[str, Any]
    vhost_config: str
    nginx_config: str | None = None
    access_log: str = ""
    error_log: str = ""


class UpdateSiteModificationRequest(BaseModel):
    settings: dict[str, Any] | None = None
    vhost_config: str | None = None
    nginx_config: str | None = None
    ssl_enabled: bool | None = None
    runtime_version: str | None = None
    php_version: str | None = None


class AddSiteDomainRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=255)
    port: int = Field(default=443, ge=1, le=65535)
