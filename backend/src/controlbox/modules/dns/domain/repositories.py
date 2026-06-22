from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.dns.domain.entities import DnsApiKey, DnsZone


class DnsZoneRepository(ABC):
    @abstractmethod
    async def add(self, zone: DnsZone) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, zone: DnsZone) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, zone_id: UUID) -> DnsZone | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, zone_id: UUID, tenant_id: UUID) -> DnsZone | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_name(self, name: str, tenant_id: UUID) -> DnsZone | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[DnsZone]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, zone_id: UUID) -> None:
        raise NotImplementedError


class DnsApiKeyRepository(ABC):
    @abstractmethod
    async def add(self, api_key: DnsApiKey) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, api_key: DnsApiKey) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, key_id: UUID) -> DnsApiKey | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, key_id: UUID, tenant_id: UUID) -> DnsApiKey | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_prefix(self, prefix: str) -> DnsApiKey | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[DnsApiKey]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key_id: UUID) -> None:
        raise NotImplementedError
