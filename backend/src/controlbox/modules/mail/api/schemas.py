from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTenantMailServiceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mail_domain: str = Field(min_length=3, max_length=255)


class UpdateTenantMailServiceRequest(BaseModel):
    name: str | None = None
    imap_host: str | None = None
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_use_ssl: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_use_ssl: bool | None = None
    smtp_use_tls: bool | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    default_quota_mb: int | None = Field(default=None, ge=100)
    total_quota_mb: int | None = Field(default=None, ge=100)
    webmail_url: str | None = None


class VerifyTenantMailServiceRequest(BaseModel):
    admin_password: str | None = None


class TenantMailServiceSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    mail_domain: str
    status: str
    imap_host: str
    imap_port: int
    imap_use_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_use_ssl: bool
    smtp_use_tls: bool
    admin_username: str
    has_admin_password: bool
    default_quota_mb: int
    total_quota_mb: int
    webmail_url: str | None
    connection_verified_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DnsRecordHintSchema(BaseModel):
    type: str
    name: str
    value: str
    purpose: str


class MailOverviewSchema(BaseModel):
    configured: bool
    accounts_count: int
    total_quota_mb: int
    total_used_mb: int


class CreateMailAccountRequest(BaseModel):
    local_part: str = Field(min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    quota_mb: int | None = Field(default=None, ge=100)


class UpdateMailAccountRequest(BaseModel):
    display_name: str | None = None
    quota_mb: int | None = Field(default=None, ge=100)
    status: str | None = None
    forwarding_to: str | None = None


class MailAccountSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    mail_service_id: UUID
    local_part: str
    email_address: str
    display_name: str
    status: str
    quota_mb: int
    used_mb: int
    forwarding_to: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MailAccountCreatedSchema(MailAccountSchema):
    password: str
