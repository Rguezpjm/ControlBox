from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SubdirectoryBindingSchema(BaseModel):
    domain: str
    directory: str = "/"


class SiteDomainSchema(BaseModel):
    domain: str
    port: int = 443
    primary: bool = False


class SiteSslConfigSchema(BaseModel):
    provider: Literal["letsencrypt", "custom", "none"] = "letsencrypt"
    deployed: bool = False
    force_https: bool = True
    cert_type: str = "Let's Encrypt"
    cert_brand: str = ""
    cert_domains: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    days_remaining: int | None = None
    certificate_pem: str = ""


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
    ssl_config: SiteSslConfigSchema | None = None
    document_root: str
    running_directory: str = "/"
    running_directory_options: list[str] = Field(default_factory=list)
    open_basedir_enabled: bool = True
    logs_enabled: bool = True
    site_files_path: str = ""
    site_path: str = ""
    subdirectory_bindings: list[SubdirectoryBindingSchema] = Field(default_factory=list)
    settings: dict[str, Any]
    vhost_config: str
    nginx_config: str | None = None
    access_log: str = ""
    error_log: str = ""


class UpdateSiteModificationRequest(BaseModel):
    settings: dict[str, Any] | None = None
    document_root: str | None = None
    logs_enabled: bool | None = None
    vhost_config: str | None = None
    nginx_config: str | None = None
    ssl_enabled: bool | None = None
    runtime_version: str | None = None
    php_version: str | None = None
    ssl_provider: Literal["letsencrypt", "custom", "none"] | None = None
    ssl_certificate_pem: str | None = None
    ssl_private_key_pem: str | None = None
    ssl_force_https: bool | None = None


class AddSiteDomainRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=255)
    port: int = Field(default=443, ge=1, le=65535)
