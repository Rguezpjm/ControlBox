from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.joomla.domain.entities import JoomlaBackup, JoomlaSite


class JoomlaSiteRepository(ABC):
    @abstractmethod
    async def add(self, site: JoomlaSite) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, site: JoomlaSite) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, site_id: UUID) -> JoomlaSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, site_id: UUID, tenant_id: UUID) -> JoomlaSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_domain(self, domain: str, tenant_id: UUID) -> JoomlaSite | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[JoomlaSite]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, site_id: UUID) -> None:
        raise NotImplementedError


class JoomlaBackupRepository(ABC):
    @abstractmethod
    async def add(self, backup: JoomlaBackup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, backup: JoomlaBackup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, backup_id: UUID, tenant_id: UUID) -> JoomlaBackup | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_site(self, site_id: UUID, tenant_id: UUID) -> list[JoomlaBackup]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, backup_id: UUID) -> None:
        raise NotImplementedError
