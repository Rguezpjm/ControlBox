from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.supabase.domain.entities import (
    SupabaseBucket,
    SupabaseProject,
    SupabaseRealtimeChannel,
    SupabaseRlsPolicy,
    SupabaseSchema,
)


class SupabaseProjectRepository(ABC):
    @abstractmethod
    async def add(self, project: SupabaseProject) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, project: SupabaseProject) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, project_id: UUID) -> SupabaseProject | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, project_id: UUID, tenant_id: UUID) -> SupabaseProject | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_slug(self, slug: str, tenant_id: UUID) -> SupabaseProject | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[SupabaseProject]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, project_id: UUID) -> None:
        raise NotImplementedError


class SupabaseSchemaRepository(ABC):
    @abstractmethod
    async def add(self, schema: SupabaseSchema) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[SupabaseSchema]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_project(self, schema_id: UUID, project_id: UUID) -> SupabaseSchema | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, schema_id: UUID) -> None:
        raise NotImplementedError


class SupabaseBucketRepository(ABC):
    @abstractmethod
    async def add(self, bucket: SupabaseBucket) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, bucket: SupabaseBucket) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[SupabaseBucket]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_project(self, bucket_id: UUID, project_id: UUID) -> SupabaseBucket | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, bucket_id: UUID) -> None:
        raise NotImplementedError


class SupabaseRealtimeChannelRepository(ABC):
    @abstractmethod
    async def add(self, channel: SupabaseRealtimeChannel) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[SupabaseRealtimeChannel]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_project(self, channel_id: UUID, project_id: UUID) -> SupabaseRealtimeChannel | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, channel_id: UUID) -> None:
        raise NotImplementedError


class SupabaseRlsPolicyRepository(ABC):
    @abstractmethod
    async def add(self, policy: SupabaseRlsPolicy) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[SupabaseRlsPolicy]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_project(self, policy_id: UUID, project_id: UUID) -> SupabaseRlsPolicy | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, policy_id: UUID) -> None:
        raise NotImplementedError
