from controlbox.modules.dns.domain.entities import DnsApiKey, DnsZone, DnsZoneStatus
from controlbox.modules.dns.infrastructure.models import DnsApiKeyModel, DnsZoneModel


def to_dns_zone(model: DnsZoneModel) -> DnsZone:
    return DnsZone(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        status=DnsZoneStatus(model.status),
        serial=model.serial,
        soa_email=model.soa_email,
        default_ttl=model.default_ttl,
        record_count=model.record_count,
        nameservers=model.nameservers or [],
        settings=model.settings or {},
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_dns_api_key(model: DnsApiKeyModel) -> DnsApiKey:
    return DnsApiKey(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        key_prefix=model.key_prefix,
        key_hash=model.key_hash,
        is_active=model.is_active,
        scopes=model.scopes or [],
        last_used_at=model.last_used_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
