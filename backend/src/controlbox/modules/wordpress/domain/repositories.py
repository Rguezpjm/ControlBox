from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.wordpress.domain.entities import WordPressBackup, WordPressSite


class WordPressSiteRepository(ABC):
    @abstractmethod
    async def add(self, site: WordPressSite) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, site: WordPressSite) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, site_id: UUID) -> WordPressSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, site_id: UUID, tenant_id: UUID) -> WordPressSite | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_domain(self, domain: str, tenant_id: UUID) -> WordPressSite | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[WordPressSite]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, site_id: UUID) -> None:
        raise NotImplementedError


class WordPressBackupRepository(ABC):
    @abstractmethod
    async def add(self, backup: WordPressBackup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, backup: WordPressBackup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, backup_id: UUID, tenant_id: UUID) -> WordPressBackup | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_site(self, site_id: UUID, tenant_id: UUID) -> list[WordPressBackup]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, backup_id: UUID) -> None:
        raise NotImplementedError
