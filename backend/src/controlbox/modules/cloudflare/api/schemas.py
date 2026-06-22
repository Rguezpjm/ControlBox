from pydantic import BaseModel, Field


class CloudflareSettingsSchema(BaseModel):
    enabled: bool = False
    configured: bool = False
    account_id: str = ""
    tunnel_enabled: bool = False
    tunnel_id: str = ""
    tunnel_hostname: str = ""
    tunnel_running: bool = False


class UpdateCloudflareSettingsRequest(BaseModel):
    enabled: bool | None = None
    api_token: str | None = Field(default=None, min_length=20, max_length=256)
    account_id: str | None = Field(default=None, max_length=64)
    tunnel_enabled: bool | None = None
    tunnel_hostname: str | None = Field(default=None, max_length=255)


class TestCloudflareRequest(BaseModel):
    api_token: str | None = Field(default=None, min_length=20, max_length=256)
    account_id: str | None = Field(default=None, max_length=64)


class CloudflareActionResponse(BaseModel):
    success: bool
    message: str
    account_id: str | None = None


class CloudflareTunnelStatusSchema(BaseModel):
    enabled: bool
    running: bool
    tunnel_id: str = ""
    hostname: str = ""
    message: str = ""


class CloudflareZoneSchema(BaseModel):
    id: str
    name: str
    status: str
    paused: bool = False
    security_level: str = "medium"
    name_servers: list[str] = Field(default_factory=list)


class CreateCloudflareZoneRequest(BaseModel):
    name: str = Field(min_length=3, max_length=253)


class CloudflareZoneActionRequest(BaseModel):
    paused: bool | None = None
    under_attack: bool | None = None


class CloudflareDnsRecordSchema(BaseModel):
    id: str
    type: str
    name: str
    content: str
    ttl: int = 1
    proxied: bool = False
    priority: int | None = None


class CreateCloudflareDnsRecordRequest(BaseModel):
    type: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2048)
    ttl: int = Field(default=1, ge=1, le=86400)
    proxied: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=65535)


class UpdateCloudflareDnsRecordRequest(BaseModel):
    type: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2048)
    ttl: int = Field(default=1, ge=1, le=86400)
    proxied: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=65535)
