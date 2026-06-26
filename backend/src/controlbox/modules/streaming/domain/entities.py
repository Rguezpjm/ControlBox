from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class StreamingSourceType(StrEnum):
    M3U = "m3u"
    XTREAM = "xtream"


class ChannelStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class StreamingSource(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    type: StreamingSourceType = StreamingSourceType.M3U
    url: str = ""
    username: str | None = None
    password: str | None = None
    status: str = "active"
    last_sync_at: datetime | None = None


@dataclass
class StreamingCategory(Entity):
    tenant_id: UUID | None = None
    name: str = ""


@dataclass
class StreamingChannel(Entity):
    tenant_id: UUID | None = None
    source_id: UUID | None = None
    category_id: UUID | None = None
    name: str = ""
    stream_url: str = ""
    logo_url: str | None = None
    epg_id: str | None = None
    stream_id: int | None = None  # Xtream Codes ID
    is_active: bool = True
    status: ChannelStatus = ChannelStatus.UNKNOWN


@dataclass
class StreamingClient(Entity):
    tenant_id: UUID | None = None
    username: str = ""
    password: str = ""
    max_connections: int = 1
    is_active: bool = True
    expires_at: datetime | None = None
    allowed_categories: list[str] = field(default_factory=list)  # list of category UUID strings or empty for all


@dataclass
class StreamingConnection(Entity):
    tenant_id: UUID | None = None
    client_id: UUID | None = None
    channel_id: UUID | None = None
    ip_address: str = ""
    user_agent: str | None = None
    bytes_transferred: int = 0
    connected_at: datetime | None = None


@dataclass
class EpgProgram(Entity):
    tenant_id: UUID | None = None
    channel_epg_id: str = ""
    title: str = ""
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
