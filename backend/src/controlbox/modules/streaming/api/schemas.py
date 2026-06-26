from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class CreateStreamingSourceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field("m3u", pattern="^(m3u|xtream)$")
    url: str = Field(..., min_length=10, max_length=512)
    username: str | None = None
    password: str | None = None


class StreamingSourceResponse(BaseModel):
    id: UUID
    name: str
    type: str
    url: str
    username: str | None = None
    status: str
    last_sync_at: datetime | None = None
    created_at: datetime


class StreamingCategoryResponse(BaseModel):
    id: UUID
    name: str


class StreamingChannelResponse(BaseModel):
    id: UUID
    source_id: UUID
    category_id: UUID | None = None
    name: str
    stream_url: str
    logo_url: str | None = None
    epg_id: str | None = None
    is_active: bool
    status: str


class CreateStreamingClientRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)
    max_connections: int = Field(1, ge=1)
    is_active: bool = True
    expires_at: datetime | None = None
    allowed_categories: list[str] = Field(default_factory=list)


class StreamingClientResponse(BaseModel):
    id: UUID
    username: str
    password: str
    max_connections: int
    is_active: bool
    expires_at: datetime | None = None
    allowed_categories: list[str]
    created_at: datetime


class ImportChannelItem(BaseModel):
    name: str
    stream_url: str
    logo_url: str | None = None
    epg_id: str | None = None
    category_name: str = "Uncategorized"
    stream_id: int | None = None


class ImportChannelsRequest(BaseModel):
    source_id: UUID
    channels: list[ImportChannelItem]


class ActiveConnectionResponse(BaseModel):
    id: UUID
    client_username: str
    channel_name: str
    ip_address: str
    user_agent: str | None = None
    bytes_transferred: int
    connected_at: datetime


class EpgProgramResponse(BaseModel):
    id: UUID
    channel_epg_id: str
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime


class StreamingStatsResponse(BaseModel):
    connected_users: int
    bandwidth_mbps: float
    active_streams: int
    total_channels: int
