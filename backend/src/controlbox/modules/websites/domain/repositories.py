from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.websites.domain.entities import Website


class WebsiteRepository(ABC):
    @abstractmethod
    async def add(self, website: Website) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, website: Website) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, website_id: UUID) -> Website | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, website_id: UUID, tenant_id: UUID) -> Website | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_domain(self, domain: str, tenant_id: UUID) -> Website | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[Website]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, website_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def count_by_tenant(self, tenant_id: UUID) -> int:
        raise NotImplementedError
