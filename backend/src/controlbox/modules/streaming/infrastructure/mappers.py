from controlbox.modules.streaming.domain.entities import (
    StreamingSource,
    StreamingCategory,
    StreamingChannel,
    StreamingClient,
    StreamingConnection,
    EpgProgram,
    StreamingSourceType,
    ChannelStatus,
)
from controlbox.modules.streaming.infrastructure.models import (
    StreamingSourceModel,
    StreamingCategoryModel,
    StreamingChannelModel,
    StreamingClientModel,
    StreamingConnectionModel,
    EpgProgramModel,
)


def source_to_entity(model: StreamingSourceModel) -> StreamingSource:
    return StreamingSource(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        type=StreamingSourceType(model.type),
        url=model.url,
        username=model.username,
        password=model.password,
        status=model.status,
        last_sync_at=model.last_sync_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def source_to_model(entity: StreamingSource) -> StreamingSourceModel:
    return StreamingSourceModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        type=entity.type.value,
        url=entity.url,
        username=entity.username,
        password=entity.password,
        status=entity.status,
        last_sync_at=entity.last_sync_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def category_to_entity(model: StreamingCategoryModel) -> StreamingCategory:
    return StreamingCategory(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        created_at=model.created_at,
    )


def category_to_model(entity: StreamingCategory) -> StreamingCategoryModel:
    return StreamingCategoryModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        created_at=entity.created_at,
    )


def channel_to_entity(model: StreamingChannelModel) -> StreamingChannel:
    return StreamingChannel(
        id=model.id,
        tenant_id=model.tenant_id,
        source_id=model.source_id,
        category_id=model.category_id,
        name=model.name,
        stream_url=model.stream_url,
        logo_url=model.logo_url,
        epg_id=model.epg_id,
        stream_id=model.stream_id,
        is_active=model.is_active,
        status=ChannelStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def channel_to_model(entity: StreamingChannel) -> StreamingChannelModel:
    return StreamingChannelModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        source_id=entity.source_id,
        category_id=entity.category_id,
        name=entity.name,
        stream_url=entity.stream_url,
        logo_url=entity.logo_url,
        epg_id=entity.epg_id,
        stream_id=entity.stream_id,
        is_active=entity.is_active,
        status=entity.status.value,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def client_to_entity(model: StreamingClientModel) -> StreamingClient:
    return StreamingClient(
        id=model.id,
        tenant_id=model.tenant_id,
        username=model.username,
        password=model.password,
        max_connections=model.max_connections,
        is_active=model.is_active,
        expires_at=model.expires_at,
        allowed_categories=model.allowed_categories,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def client_to_model(entity: StreamingClient) -> StreamingClientModel:
    return StreamingClientModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        username=entity.username,
        password=entity.password,
        max_connections=entity.max_connections,
        is_active=entity.is_active,
        expires_at=entity.expires_at,
        allowed_categories=entity.allowed_categories,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def connection_to_entity(model: StreamingConnectionModel) -> StreamingConnection:
    return StreamingConnection(
        id=model.id,
        tenant_id=model.tenant_id,
        client_id=model.client_id,
        channel_id=model.channel_id,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        bytes_transferred=model.bytes_transferred,
        connected_at=model.connected_at,
        updated_at=model.updated_at,
    )


def connection_to_model(entity: StreamingConnection) -> StreamingConnectionModel:
    return StreamingConnectionModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        client_id=entity.client_id,
        channel_id=entity.channel_id,
        ip_address=entity.ip_address,
        user_agent=entity.user_agent,
        bytes_transferred=entity.bytes_transferred,
        connected_at=entity.connected_at,
        updated_at=entity.updated_at,
    )


def epg_to_entity(model: EpgProgramModel) -> EpgProgram:
    return EpgProgram(
        id=model.id,
        tenant_id=model.tenant_id,
        channel_epg_id=model.channel_epg_id,
        title=model.title,
        description=model.description,
        start_time=model.start_time,
        end_time=model.end_time,
        created_at=model.created_at if hasattr(model, "created_at") else None,
        updated_at=model.updated_at if hasattr(model, "updated_at") else None,
    )


def epg_to_model(entity: EpgProgram) -> EpgProgramModel:
    return EpgProgramModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        channel_epg_id=entity.channel_epg_id,
        title=entity.title,
        description=entity.description,
        start_time=entity.start_time,
        end_time=entity.end_time,
    )
