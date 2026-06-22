from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDnsZoneRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    soa_email: str = "hostmaster"
    default_ttl: int = Field(default=3600, ge=60, le=86400)
    nameservers: list[str] | None = None


class UpdateDnsZoneRequest(BaseModel):
    soa_email: str | None = None
    default_ttl: int | None = Field(default=None, ge=60, le=86400)
    nameservers: list[str] | None = None


class ImportZoneRequest(BaseModel):
    content: str = Field(min_length=1)


class CreateDnsRecordRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    record_type: str
    content: str = Field(min_length=1)
    ttl: int = Field(default=3600, ge=60, le=86400)
    priority: int | None = Field(default=None, ge=0, le=65535)


class UpdateDnsRecordRequest(BaseModel):
    content: str = Field(min_length=1)
    ttl: int = Field(default=3600, ge=60, le=86400)
    priority: int | None = Field(default=None, ge=0, le=65535)


class CreateDnsApiKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    scopes: list[str] | None = None


class DnsZoneSchema(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    status: str
    serial: int
    soa_email: str
    default_ttl: int
    record_count: int
    nameservers: list[str]
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DnsRecordSchema(BaseModel):
    id: str
    name: str
    record_type: str
    content: str
    ttl: int
    priority: int | None = None


class DnsApiKeySchema(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    scopes: list[str]
    last_used_at: datetime | None
    created_at: datetime


class DnsApiKeyCreatedSchema(DnsApiKeySchema):
    api_key: str


class RecordTypesSchema(BaseModel):
    types: list[str]
