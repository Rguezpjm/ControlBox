from uuid import UUID

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.dns.application.commands import (
    CreateDnsApiKeyCommand,
    CreateDnsRecordCommand,
    CreateDnsZoneCommand,
    DeleteDnsRecordCommand,
    DeleteDnsZoneCommand,
    ImportDnsZoneCommand,
    RevokeDnsApiKeyCommand,
    UpdateDnsRecordCommand,
    UpdateDnsZoneCommand,
)
from controlbox.modules.dns.domain.entities import DnsApiKey, DnsRecord, DnsZone, DnsZoneStatus, SUPPORTED_RECORD_TYPES
from controlbox.modules.dns.domain.services import DnsDomainService
from controlbox.modules.dns.infrastructure.api_keys import generate_api_key
from controlbox.modules.dns.infrastructure.powerdns_client import PowerDnsClient
from controlbox.modules.dns.infrastructure.zone_file import export_zone_file, parse_zone_file
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


async def _get_zone(uow: UnitOfWork, zone_id: UUID, tenant_id: UUID) -> DnsZone:
    zone = await uow.dns_zones.get_by_id_and_tenant(zone_id, tenant_id)
    if not zone:
        raise NotFoundError("Zone not found")
    return zone


class CreateDnsZoneHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._pdns = PowerDnsClient(self._settings)

    async def handle(self, command: CreateDnsZoneCommand) -> DnsZone:
        domain = DnsDomainService(self._uow.dns_zones)
        name = domain.normalize_zone_name(command.name)
        await domain.ensure_zone_available(name, command.tenant_id)

        zone = DnsZone(
            tenant_id=command.tenant_id,
            name=name,
            status=DnsZoneStatus.PENDING,
            soa_email=command.soa_email,
            default_ttl=command.default_ttl,
            nameservers=command.nameservers or self._settings.powerdns_nameservers_list,
        )

        async with self._uow:
            await self._uow.dns_zones.add(zone)
            try:
                await self._pdns.create_zone(zone)
                zone.mark_active(0)
                await self._uow.dns_zones.save(zone)
            except Exception as exc:
                zone.mark_error(str(exc))
                await self._uow.dns_zones.save(zone)
            await self._uow.commit()
        return zone


class UpdateDnsZoneHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: UpdateDnsZoneCommand) -> DnsZone:
        async with self._uow:
            zone = await _get_zone(self._uow, command.zone_id, command.tenant_id)
            if command.soa_email:
                zone.soa_email = command.soa_email
            if command.default_ttl:
                zone.default_ttl = command.default_ttl
            if command.nameservers:
                zone.nameservers = command.nameservers
            zone.bump_serial()
            await self._uow.dns_zones.save(zone)
            await self._uow.commit()
        return zone


class DeleteDnsZoneHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._pdns = PowerDnsClient(settings or get_settings())

    async def handle(self, command: DeleteDnsZoneCommand) -> None:
        async with self._uow:
            zone = await _get_zone(self._uow, command.zone_id, command.tenant_id)
            try:
                await self._pdns.delete_zone(zone.name)
            except Exception:
                pass
            await self._uow.dns_zones.delete(zone.id)
            await self._uow.commit()


class ImportDnsZoneHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._pdns = PowerDnsClient(settings or get_settings())

    async def handle(self, command: ImportDnsZoneCommand) -> DnsZone:
        async with self._uow:
            zone = await _get_zone(self._uow, command.zone_id, command.tenant_id)
            parsed = parse_zone_file(command.content, zone.name)
            await self._pdns.import_records(zone.name, parsed.records)
            zone.soa_email = parsed.soa_email or zone.soa_email
            zone.default_ttl = parsed.ttl
            zone.bump_serial()
            records = await self._pdns.list_records(zone.name)
            zone.mark_active(len(records))
            await self._uow.dns_zones.save(zone)
            await self._uow.commit()
        return zone


class CreateDnsRecordHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._pdns = PowerDnsClient(self._settings)

    async def handle(self, command: CreateDnsRecordCommand) -> DnsRecord:
        domain = DnsDomainService(self._uow.dns_zones)
        rtype = domain.validate_record_type(command.record_type)

        async with self._uow:
            zone = await _get_zone(self._uow, command.zone_id, command.tenant_id)
            name = domain.normalize_record_name(command.name, zone.name)
            record = DnsRecord(
                name=name,
                type=rtype,
                content=command.content,
                ttl=command.ttl or zone.default_ttl,
                priority=command.priority,
            )
            await self._pdns.upsert_record(zone.name, record)
            zone.bump_serial()
            records = await self._pdns.list_records(zone.name)
            zone.record_count = len(records)
            await self._uow.dns_zones.save(zone)
            await self._uow.commit()
        return record


class UpdateDnsRecordHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._pdns = PowerDnsClient(settings or get_settings())

    async def handle(self, command: UpdateDnsRecordCommand) -> DnsRecord:
        domain = DnsDomainService(self._uow.dns_zones)
        rtype = domain.validate_record_type(command.record_type)

        async with self._uow:
            zone = await _get_zone(self._uow, command.zone_id, command.tenant_id)
            name = domain.normalize_record_name(command.name, zone.name)
            record = DnsRecord(
                name=name,
                type=rtype,
                content=command.content,
                ttl=command.ttl or zone.default_ttl,
                priority=command.priority,
            )
            await self._pdns.upsert_record(zone.name, record)
            zone.bump_serial()
            await self._uow.dns_zones.save(zone)
            await self._uow.commit()
        return record


class DeleteDnsRecordHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._pdns = PowerDnsClient(settings or get_settings())

    async def handle(self, command: DeleteDnsRecordCommand) -> None:
        domain = DnsDomainService(self._uow.dns_zones)

        async with self._uow:
            zone = await _get_zone(self._uow, command.zone_id, command.tenant_id)
            name = domain.normalize_record_name(command.name, zone.name)
            rtype = domain.validate_record_type(command.record_type)
            await self._pdns.delete_record(zone.name, domain.fqdn(name), rtype.value)
            zone.bump_serial()
            records = await self._pdns.list_records(zone.name)
            zone.record_count = len(records)
            await self._uow.dns_zones.save(zone)
            await self._uow.commit()


class CreateDnsApiKeyHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: CreateDnsApiKeyCommand) -> tuple[DnsApiKey, str]:
        full_key, prefix, key_hash = generate_api_key()
        api_key = DnsApiKey(
            tenant_id=command.tenant_id,
            name=command.name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=command.scopes or ["dns.read", "dns.manage"],
        )
        async with self._uow:
            await self._uow.dns_api_keys.add(api_key)
            await self._uow.commit()
        return api_key, full_key


class RevokeDnsApiKeyHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: RevokeDnsApiKeyCommand) -> None:
        async with self._uow:
            api_key = await self._uow.dns_api_keys.get_by_id_and_tenant(command.key_id, command.tenant_id)
            if not api_key:
                raise NotFoundError("API key not found")
            api_key.deactivate()
            await self._uow.dns_api_keys.save(api_key)
            await self._uow.commit()
