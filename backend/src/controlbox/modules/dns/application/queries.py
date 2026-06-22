from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListDnsZonesQuery:
    tenant_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetDnsZoneQuery:
    tenant_id: UUID
    zone_id: UUID


@dataclass(frozen=True)
class ListDnsRecordsQuery:
    tenant_id: UUID
    zone_id: UUID


@dataclass(frozen=True)
class ExportDnsZoneQuery:
    tenant_id: UUID
    zone_id: UUID


@dataclass(frozen=True)
class GetDnsRecordTypesQuery:
    pass


@dataclass(frozen=True)
class ListDnsApiKeysQuery:
    tenant_id: UUID
