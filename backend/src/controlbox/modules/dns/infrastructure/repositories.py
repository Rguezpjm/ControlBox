from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.dns.domain.entities import DnsApiKey, DnsZone
from controlbox.modules.dns.domain.repositories import DnsApiKeyRepository, DnsZoneRepository
from controlbox.modules.dns.infrastructure.mappers import to_dns_api_key, to_dns_zone
from controlbox.modules.dns.infrastructure.models import DnsApiKeyModel, DnsZoneModel


class SqlAlchemyDnsZoneRepository(DnsZoneRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, zone: DnsZone) -> None:
        self._session.add(DnsZoneModel(
            id=zone.id,
            tenant_id=zone.tenant_id,
            name=zone.name,
            status=zone.status.value,
            serial=zone.serial,
            soa_email=zone.soa_email,
            default_ttl=zone.default_ttl,
            record_count=zone.record_count,
            nameservers=zone.nameservers,
            settings=zone.settings,
            error_message=zone.error_message,
        ))

    async def save(self, zone: DnsZone) -> None:
        result = await self._session.execute(select(DnsZoneModel).where(DnsZoneModel.id == zone.id))
        model = result.scalar_one()
        model.status = zone.status.value
        model.serial = zone.serial
        model.soa_email = zone.soa_email
        model.default_ttl = zone.default_ttl
        model.record_count = zone.record_count
        model.nameservers = zone.nameservers
        model.settings = zone.settings
        model.error_message = zone.error_message

    async def get_by_id(self, zone_id: UUID) -> DnsZone | None:
        result = await self._session.execute(select(DnsZoneModel).where(DnsZoneModel.id == zone_id))
        model = result.scalar_one_or_none()
        return to_dns_zone(model) if model else None

    async def get_by_id_and_tenant(self, zone_id: UUID, tenant_id: UUID) -> DnsZone | None:
        result = await self._session.execute(
            select(DnsZoneModel).where(DnsZoneModel.id == zone_id, DnsZoneModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return to_dns_zone(model) if model else None

    async def get_by_name(self, name: str, tenant_id: UUID) -> DnsZone | None:
        result = await self._session.execute(
            select(DnsZoneModel).where(DnsZoneModel.name == name, DnsZoneModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return to_dns_zone(model) if model else None

    async def get_by_name_global(self, name: str) -> DnsZone | None:
        result = await self._session.execute(select(DnsZoneModel).where(DnsZoneModel.name == name))
        model = result.scalar_one_or_none()
        return to_dns_zone(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[DnsZone]:
        result = await self._session.execute(
            select(DnsZoneModel)
            .where(DnsZoneModel.tenant_id == tenant_id)
            .order_by(DnsZoneModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [to_dns_zone(m) for m in result.scalars().all()]

    async def delete(self, zone_id: UUID) -> None:
        await self._session.execute(delete(DnsZoneModel).where(DnsZoneModel.id == zone_id))


class SqlAlchemyDnsApiKeyRepository(DnsApiKeyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, api_key: DnsApiKey) -> None:
        self._session.add(DnsApiKeyModel(
            id=api_key.id,
            tenant_id=api_key.tenant_id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            key_hash=api_key.key_hash,
            is_active=api_key.is_active,
            scopes=api_key.scopes,
            last_used_at=api_key.last_used_at,
        ))

    async def save(self, api_key: DnsApiKey) -> None:
        result = await self._session.execute(select(DnsApiKeyModel).where(DnsApiKeyModel.id == api_key.id))
        model = result.scalar_one()
        model.is_active = api_key.is_active
        model.last_used_at = api_key.last_used_at

    async def get_by_id(self, key_id: UUID) -> DnsApiKey | None:
        result = await self._session.execute(select(DnsApiKeyModel).where(DnsApiKeyModel.id == key_id))
        model = result.scalar_one_or_none()
        return to_dns_api_key(model) if model else None

    async def get_by_id_and_tenant(self, key_id: UUID, tenant_id: UUID) -> DnsApiKey | None:
        result = await self._session.execute(
            select(DnsApiKeyModel).where(DnsApiKeyModel.id == key_id, DnsApiKeyModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return to_dns_api_key(model) if model else None

    async def get_by_prefix(self, prefix: str) -> DnsApiKey | None:
        result = await self._session.execute(
            select(DnsApiKeyModel).where(DnsApiKeyModel.key_prefix == prefix, DnsApiKeyModel.is_active.is_(True))
        )
        model = result.scalar_one_or_none()
        return to_dns_api_key(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[DnsApiKey]:
        result = await self._session.execute(
            select(DnsApiKeyModel).where(DnsApiKeyModel.tenant_id == tenant_id).order_by(DnsApiKeyModel.created_at.desc())
        )
        return [to_dns_api_key(m) for m in result.scalars().all()]

    async def delete(self, key_id: UUID) -> None:
        await self._session.execute(delete(DnsApiKeyModel).where(DnsApiKeyModel.id == key_id))
