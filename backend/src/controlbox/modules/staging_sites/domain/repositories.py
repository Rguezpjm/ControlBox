from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.staging_sites.domain.entities import StagingSite, StagingSourceType


class StagingSiteRepository(ABC):
    @abstractmethod
    async def add(self, staging: StagingSite) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, staging: StagingSite) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, staging_id: UUID) -> StagingSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, staging_id: UUID, tenant_id: UUID) -> StagingSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_domain(self, domain: str, tenant_id: UUID) -> StagingSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_source(
        self, source_type: StagingSourceType, source_id: UUID, tenant_id: UUID
    ) -> StagingSite | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, staging_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[StagingSite]:
        raise NotImplementedError

    @abstractmethod
    async def list_by_source(self, source_type: StagingSourceType, source_id: UUID, tenant_id: UUID) -> list[StagingSite]:
        raise NotImplementedError
