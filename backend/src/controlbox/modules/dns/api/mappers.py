from controlbox.modules.dns.api.schemas import DnsRecordSchema, DnsZoneSchema
from controlbox.modules.dns.domain.entities import DnsRecord, DnsZone


def to_zone_schema(zone: DnsZone) -> DnsZoneSchema:
    return DnsZoneSchema(
        id=zone.id,
        tenant_id=zone.tenant_id,
        name=zone.name,
        status=zone.status.value,
        serial=zone.serial,
        soa_email=zone.soa_email,
        default_ttl=zone.default_ttl,
        record_count=zone.record_count,
        nameservers=zone.nameservers,
        error_message=zone.error_message,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


def to_record_schema(record: DnsRecord) -> DnsRecordSchema:
    return DnsRecordSchema(
        id=record.record_id,
        name=record.name,
        record_type=record.type.value,
        content=record.content,
        ttl=record.ttl,
        priority=record.priority,
    )
