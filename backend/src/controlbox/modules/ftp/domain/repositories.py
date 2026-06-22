from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.ftp.domain.entities import FtpAccount


class FtpAccountRepository(ABC):
    @abstractmethod
    async def add(self, account: FtpAccount) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, account: FtpAccount) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, account_id: UUID) -> FtpAccount | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, account_id: UUID, tenant_id: UUID) -> FtpAccount | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_username(self, username: str, tenant_id: UUID) -> FtpAccount | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[FtpAccount]:
        raise NotImplementedError

    @abstractmethod
    async def list_active(self) -> list[FtpAccount]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, account_id: UUID) -> None:
        raise NotImplementedError
