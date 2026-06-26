from uuid import UUID
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.streaming.domain.entities import (
    StreamingSource,
    StreamingCategory,
    StreamingChannel,
    StreamingClient,
    StreamingConnection,
    EpgProgram,
)
from controlbox.modules.streaming.domain.repositories import (
    StreamingSourceRepository,
    StreamingCategoryRepository,
    StreamingChannelRepository,
    StreamingClientRepository,
    StreamingConnectionRepository,
    EpgProgramRepository,
)
from controlbox.modules.streaming.infrastructure.mappers import (
    source_to_entity,
    source_to_model,
    category_to_entity,
    category_to_model,
    channel_to_entity,
    channel_to_model,
    client_to_entity,
    client_to_model,
    connection_to_entity,
    connection_to_model,
    epg_to_entity,
    epg_to_model,
)
from controlbox.modules.streaming.infrastructure.models import (
    StreamingSourceModel,
    StreamingCategoryModel,
    StreamingChannelModel,
    StreamingClientModel,
    StreamingConnectionModel,
    EpgProgramModel,
)


class SqlAlchemyStreamingSourceRepository(StreamingSourceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, source: StreamingSource) -> None:
        self._session.add(source_to_model(source))

    async def save(self, source: StreamingSource) -> None:
        await self._session.merge(source_to_model(source))

    async def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> StreamingSource | None:
        result = await self._session.execute(
            select(StreamingSourceModel).where(
                StreamingSourceModel.id == source_id, StreamingSourceModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return source_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[StreamingSource]:
        result = await self._session.execute(
            select(StreamingSourceModel)
            .where(StreamingSourceModel.tenant_id == tenant_id)
            .order_by(StreamingSourceModel.created_at.desc())
        )
        return [source_to_entity(m) for m in result.scalars().all()]

    async def delete(self, source_id: UUID) -> None:
        await self._session.execute(delete(StreamingSourceModel).where(StreamingSourceModel.id == source_id))


class SqlAlchemyStreamingCategoryRepository(StreamingCategoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, category: StreamingCategory) -> None:
        self._session.add(category_to_model(category))

    async def get_by_id_and_tenant(self, category_id: UUID, tenant_id: UUID) -> StreamingCategory | None:
        result = await self._session.execute(
            select(StreamingCategoryModel).where(
                StreamingCategoryModel.id == category_id, StreamingCategoryModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return category_to_entity(model) if model else None

    async def get_by_name_and_tenant(self, name: str, tenant_id: UUID) -> StreamingCategory | None:
        result = await self._session.execute(
            select(StreamingCategoryModel).where(
                StreamingCategoryModel.name == name, StreamingCategoryModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return category_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[StreamingCategory]:
        result = await self._session.execute(
            select(StreamingCategoryModel)
            .where(StreamingCategoryModel.tenant_id == tenant_id)
            .order_by(StreamingCategoryModel.name.asc())
        )
        return [category_to_entity(m) for m in result.scalars().all()]

    async def delete(self, category_id: UUID) -> None:
        await self._session.execute(delete(StreamingCategoryModel).where(StreamingCategoryModel.id == category_id))


class SqlAlchemyStreamingChannelRepository(StreamingChannelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, channel: StreamingChannel) -> None:
        self._session.add(channel_to_model(channel))

    async def save(self, channel: StreamingChannel) -> None:
        await self._session.merge(channel_to_model(channel))

    async def get_by_id_and_tenant(self, channel_id: UUID, tenant_id: UUID) -> StreamingChannel | None:
        result = await self._session.execute(
            select(StreamingChannelModel).where(
                StreamingChannelModel.id == channel_id, StreamingChannelModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return channel_to_entity(model) if model else None

    async def get_by_stream_id_and_source(self, stream_id: int, source_id: UUID, tenant_id: UUID) -> StreamingChannel | None:
        result = await self._session.execute(
            select(StreamingChannelModel).where(
                StreamingChannelModel.stream_id == stream_id,
                StreamingChannelModel.source_id == source_id,
                StreamingChannelModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return channel_to_entity(model) if model else None

    async def get_by_url_and_source(self, stream_url: str, source_id: UUID, tenant_id: UUID) -> StreamingChannel | None:
        result = await self._session.execute(
            select(StreamingChannelModel).where(
                StreamingChannelModel.stream_url == stream_url,
                StreamingChannelModel.source_id == source_id,
                StreamingChannelModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return channel_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 2000, offset: int = 0) -> list[StreamingChannel]:
        result = await self._session.execute(
            select(StreamingChannelModel)
            .where(StreamingChannelModel.tenant_id == tenant_id)
            .order_by(StreamingChannelModel.name.asc())
            .limit(limit)
            .offset(offset)
        )
        return [channel_to_entity(m) for m in result.scalars().all()]

    async def list_by_category(self, category_id: UUID, tenant_id: UUID) -> list[StreamingChannel]:
        result = await self._session.execute(
            select(StreamingChannelModel)
            .where(StreamingChannelModel.category_id == category_id, StreamingChannelModel.tenant_id == tenant_id)
            .order_by(StreamingChannelModel.name.asc())
        )
        return [channel_to_entity(m) for m in result.scalars().all()]

    async def delete(self, channel_id: UUID) -> None:
        await self._session.execute(delete(StreamingChannelModel).where(StreamingChannelModel.id == channel_id))


class SqlAlchemyStreamingClientRepository(StreamingClientRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, client: StreamingClient) -> None:
        self._session.add(client_to_model(client))

    async def save(self, client: StreamingClient) -> None:
        await self._session.merge(client_to_model(client))

    async def get_by_id_and_tenant(self, client_id: UUID, tenant_id: UUID) -> StreamingClient | None:
        result = await self._session.execute(
            select(StreamingClientModel).where(
                StreamingClientModel.id == client_id, StreamingClientModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return client_to_entity(model) if model else None

    async def get_by_username_and_tenant(self, username: str, tenant_id: UUID) -> StreamingClient | None:
        result = await self._session.execute(
            select(StreamingClientModel).where(
                StreamingClientModel.username == username, StreamingClientModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return client_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[StreamingClient]:
        result = await self._session.execute(
            select(StreamingClientModel)
            .where(StreamingClientModel.tenant_id == tenant_id)
            .order_by(StreamingClientModel.username.asc())
        )
        return [client_to_entity(m) for m in result.scalars().all()]

    async def delete(self, client_id: UUID) -> None:
        await self._session.execute(delete(StreamingClientModel).where(StreamingClientModel.id == client_id))


class SqlAlchemyStreamingConnectionRepository(StreamingConnectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, connection: StreamingConnection) -> None:
        self._session.add(connection_to_model(connection))

    async def save(self, connection: StreamingConnection) -> None:
        await self._session.merge(connection_to_model(connection))

    async def get_by_id(self, connection_id: UUID) -> StreamingConnection | None:
        result = await self._session.execute(
            select(StreamingConnectionModel).where(StreamingConnectionModel.id == connection_id)
        )
        model = result.scalar_one_or_none()
        return connection_to_entity(model) if model else None

    async def get_active_by_client(self, client_id: UUID, tenant_id: UUID) -> list[StreamingConnection]:
        result = await self._session.execute(
            select(StreamingConnectionModel).where(
                StreamingConnectionModel.client_id == client_id,
                StreamingConnectionModel.tenant_id == tenant_id
            )
        )
        return [connection_to_entity(m) for m in result.scalars().all()]

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[StreamingConnection]:
        result = await self._session.execute(
            select(StreamingConnectionModel)
            .where(StreamingConnectionModel.tenant_id == tenant_id)
            .order_by(StreamingConnectionModel.connected_at.desc())
        )
        return [connection_to_entity(m) for m in result.scalars().all()]

    async def delete(self, connection_id: UUID) -> None:
        await self._session.execute(delete(StreamingConnectionModel).where(StreamingConnectionModel.id == connection_id))


class SqlAlchemyEpgProgramRepository(EpgProgramRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, program: EpgProgram) -> None:
        self._session.add(epg_to_model(program))

    async def delete_expired(self, before_time: datetime, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(EpgProgramModel).where(
                EpgProgramModel.end_time < before_time,
                EpgProgramModel.tenant_id == tenant_id
            )
        )

    async def list_by_channel_and_time(self, channel_epg_id: str, tenant_id: UUID, start: datetime, end: datetime) -> list[EpgProgram]:
        result = await self._session.execute(
            select(EpgProgramModel).where(
                EpgProgramModel.channel_epg_id == channel_epg_id,
                EpgProgramModel.tenant_id == tenant_id,
                EpgProgramModel.end_time >= start,
                EpgProgramModel.start_time <= end,
            ).order_by(EpgProgramModel.start_time.asc())
        )
        return [epg_to_entity(m) for m in result.scalars().all()]
