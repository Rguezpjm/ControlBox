from controlbox.config.settings import Settings, get_settings
from controlbox.modules.dns.application.queries import (
    ExportDnsZoneQuery,
    GetDnsRecordTypesQuery,
    GetDnsZoneQuery,
    ListDnsApiKeysQuery,
    ListDnsRecordsQuery,
    ListDnsZonesQuery,
)
from controlbox.modules.dns.domain.entities import DnsApiKey, DnsRecord, DnsZone, SUPPORTED_RECORD_TYPES
from controlbox.modules.dns.infrastructure.powerdns_client import PowerDnsClient
from controlbox.modules.dns.infrastructure.zone_file import export_zone_file
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


class ListDnsZonesHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListDnsZonesQuery) -> list[DnsZone]:
        async with self._uow:
            return await self._uow.dns_zones.list_by_tenant(query.tenant_id, query.limit, query.offset)


class GetDnsZoneHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetDnsZoneQuery) -> DnsZone:
        async with self._uow:
            zone = await self._uow.dns_zones.get_by_id_and_tenant(query.zone_id, query.tenant_id)
            if not zone:
                raise NotFoundError("Zone not found")
            return zone


class ListDnsRecordsHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._pdns = PowerDnsClient(settings or get_settings())

    async def handle(self, query: ListDnsRecordsQuery) -> list[DnsRecord]:
        async with self._uow:
            zone = await self._uow.dns_zones.get_by_id_and_tenant(query.zone_id, query.tenant_id)
            if not zone:
                raise NotFoundError("Zone not found")
            return await self._pdns.list_records(zone.name)


class ExportDnsZoneHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._pdns = PowerDnsClient(settings or get_settings())

    async def handle(self, query: ExportDnsZoneQuery) -> str:
        async with self._uow:
            zone = await self._uow.dns_zones.get_by_id_and_tenant(query.zone_id, query.tenant_id)
            if not zone:
                raise NotFoundError("Zone not found")
            records = await self._pdns.list_records(zone.name)
            return export_zone_file(
                zone.name, zone.serial, zone.soa_email, zone.nameservers, records, zone.default_ttl
            )


class GetDnsRecordTypesHandler:
    async def handle(self, query: GetDnsRecordTypesQuery) -> list[str]:
        return [t.value for t in SUPPORTED_RECORD_TYPES]


class ListDnsApiKeysHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListDnsApiKeysQuery) -> list[DnsApiKey]:
        async with self._uow:
            return await self._uow.dns_api_keys.list_by_tenant(query.tenant_id)
