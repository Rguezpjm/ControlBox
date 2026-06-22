from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.platform.domain.entities import ResourceAlert, TenantPlatformSettings


class TenantPlatformSettingsRepository(ABC):
    @abstractmethod
    async def get_or_create(self, tenant_id: UUID) -> TenantPlatformSettings:
        raise NotImplementedError

    @abstractmethod
    async def save(self, settings: TenantPlatformSettings) -> None:
        raise NotImplementedError


class ResourceAlertRepository(ABC):
    @abstractmethod
    async def add(self, alert: ResourceAlert) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> ResourceAlert | None:
        raise NotImplementedError

    @abstractmethod
    async def list_active(self, tenant_id: UUID, limit: int = 50) -> list[ResourceAlert]:
        raise NotImplementedError

    @abstractmethod
    async def list_recent(self, tenant_id: UUID, limit: int = 50) -> list[ResourceAlert]:
        raise NotImplementedError

    @abstractmethod
    async def count_active(self, tenant_id: UUID) -> int:
        raise NotImplementedError

    @abstractmethod
    async def save(self, alert: ResourceAlert) -> None:
        raise NotImplementedError

    @abstractmethod
    async def has_recent_alert(self, tenant_id: UUID, metric: str, within_minutes: int) -> bool:
        raise NotImplementedError
