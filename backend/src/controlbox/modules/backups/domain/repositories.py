from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.backups.domain.entities import BackupDestination, BackupJob, BackupSchedule


class BackupDestinationRepository(ABC):
    @abstractmethod
    async def add(self, destination: BackupDestination) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, destination: BackupDestination) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, destination_id: UUID) -> BackupDestination | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, destination_id: UUID, tenant_id: UUID) -> BackupDestination | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[BackupDestination]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, destination_id: UUID) -> None:
        raise NotImplementedError


class BackupScheduleRepository(ABC):
    @abstractmethod
    async def add(self, schedule: BackupSchedule) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, schedule: BackupSchedule) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, schedule_id: UUID) -> BackupSchedule | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, schedule_id: UUID, tenant_id: UUID) -> BackupSchedule | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[BackupSchedule]:
        raise NotImplementedError

    @abstractmethod
    async def list_due(self, before: "datetime") -> list[BackupSchedule]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, schedule_id: UUID) -> None:
        raise NotImplementedError


class BackupJobRepository(ABC):
    @abstractmethod
    async def add(self, job: BackupJob) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, job: BackupJob) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> BackupJob | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> BackupJob | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, source_type: str | None = None) -> list[BackupJob]:
        raise NotImplementedError

    @abstractmethod
    async def list_versions(self, tenant_id: UUID, resource_key: str) -> list[BackupJob]:
        raise NotImplementedError

    @abstractmethod
    async def get_latest_version(self, tenant_id: UUID, resource_key: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, job_id: UUID) -> None:
        raise NotImplementedError
