from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateDnsZoneCommand:
    tenant_id: UUID
    name: str
    soa_email: str = "hostmaster"
    default_ttl: int = 3600
    nameservers: list[str] | None = None


@dataclass(frozen=True)
class UpdateDnsZoneCommand:
    tenant_id: UUID
    zone_id: UUID
    soa_email: str | None = None
    default_ttl: int | None = None
    nameservers: list[str] | None = None


@dataclass(frozen=True)
class DeleteDnsZoneCommand:
    tenant_id: UUID
    zone_id: UUID


@dataclass(frozen=True)
class ImportDnsZoneCommand:
    tenant_id: UUID
    zone_id: UUID
    content: str


@dataclass(frozen=True)
class CreateDnsRecordCommand:
    tenant_id: UUID
    zone_id: UUID
    name: str
    record_type: str
    content: str
    ttl: int = 3600
    priority: int | None = None


@dataclass(frozen=True)
class UpdateDnsRecordCommand:
    tenant_id: UUID
    zone_id: UUID
    name: str
    record_type: str
    content: str
    ttl: int = 3600
    priority: int | None = None


@dataclass(frozen=True)
class DeleteDnsRecordCommand:
    tenant_id: UUID
    zone_id: UUID
    name: str
    record_type: str


@dataclass(frozen=True)
class CreateDnsApiKeyCommand:
    tenant_id: UUID
    name: str
    scopes: list[str] | None = None


@dataclass(frozen=True)
class RevokeDnsApiKeyCommand:
    tenant_id: UUID
    key_id: UUID
