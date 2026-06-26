from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime

from controlbox.modules.streaming.domain.entities import (
    StreamingSource,
    StreamingCategory,
    StreamingChannel,
    StreamingClient,
    StreamingConnection,
    EpgProgram,
)


class StreamingSourceRepository(ABC):
    @abstractmethod
    async def add(self, source: StreamingSource) -> None:
        pass

    @abstractmethod
    async def save(self, source: StreamingSource) -> None:
        pass

    @abstractmethod
    async def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> StreamingSource | None:
        pass

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[StreamingSource]:
        pass

    @abstractmethod
    async def delete(self, source_id: UUID) -> None:
        pass


class StreamingCategoryRepository(ABC):
    @abstractmethod
    async def add(self, category: StreamingCategory) -> None:
        pass

    @abstractmethod
    async def get_by_id_and_tenant(self, category_id: UUID, tenant_id: UUID) -> StreamingCategory | None:
        pass

    @abstractmethod
    async def get_by_name_and_tenant(self, name: str, tenant_id: UUID) -> StreamingCategory | None:
        pass

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[StreamingCategory]:
        pass

    @abstractmethod
    async def delete(self, category_id: UUID) -> None:
        pass


class StreamingChannelRepository(ABC):
    @abstractmethod
    async def add(self, channel: StreamingChannel) -> None:
        pass

    @abstractmethod
    async def save(self, channel: StreamingChannel) -> None:
        pass

    @abstractmethod
    async def get_by_id_and_tenant(self, channel_id: UUID, tenant_id: UUID) -> StreamingChannel | None:
        pass

    @abstractmethod
    async def get_by_stream_id_and_source(self, stream_id: int, source_id: UUID, tenant_id: UUID) -> StreamingChannel | None:
        pass

    @abstractmethod
    async def get_by_url_and_source(self, stream_url: str, source_id: UUID, tenant_id: UUID) -> StreamingChannel | None:
        pass

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID, limit: int = 2000, offset: int = 0) -> list[StreamingChannel]:
        pass

    @abstractmethod
    async def list_by_category(self, category_id: UUID, tenant_id: UUID) -> list[StreamingChannel]:
        pass

    @abstractmethod
    async def delete(self, channel_id: UUID) -> None:
        pass


class StreamingClientRepository(ABC):
    @abstractmethod
    async def add(self, client: StreamingClient) -> None:
        pass

    @abstractmethod
    async def save(self, client: StreamingClient) -> None:
        pass

    @abstractmethod
    async def get_by_id_and_tenant(self, client_id: UUID, tenant_id: UUID) -> StreamingClient | None:
        pass

    @abstractmethod
    async def get_by_username_and_tenant(self, username: str, tenant_id: UUID) -> StreamingClient | None:
        pass

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[StreamingClient]:
        pass

    @abstractmethod
    async def delete(self, client_id: UUID) -> None:
        pass


class StreamingConnectionRepository(ABC):
    @abstractmethod
    async def add(self, connection: StreamingConnection) -> None:
        pass

    @abstractmethod
    async def save(self, connection: StreamingConnection) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, connection_id: UUID) -> StreamingConnection | None:
        pass

    @abstractmethod
    async def get_active_by_client(self, client_id: UUID, tenant_id: UUID) -> list[StreamingConnection]:
        pass

    @abstractmethod
    async def list_active_by_tenant(self, tenant_id: UUID) -> list[StreamingConnection]:
        pass

    @abstractmethod
    async def delete(self, connection_id: UUID) -> None:
        pass


class EpgProgramRepository(ABC):
    @abstractmethod
    async def add(self, program: EpgProgram) -> None:
        pass

    @abstractmethod
    async def delete_expired(self, before_time: datetime, tenant_id: UUID) -> None:
        pass

    @abstractmethod
    async def list_by_channel_and_time(self, channel_epg_id: str, tenant_id: UUID, start: datetime, end: datetime) -> list[EpgProgram]:
        pass
