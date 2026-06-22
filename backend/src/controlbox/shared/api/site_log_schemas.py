from pydantic import BaseModel, Field


class AccessLogEntrySchema(BaseModel):
    raw: str
    ip: str
    timestamp: str
    method: str
    path: str
    protocol: str
    status: int
    bytes: str
    user_agent: str
    ip_location: str | None = None


class SiteAccessLogsSchema(BaseModel):
    source: str = ""
    entries: list[AccessLogEntrySchema] = Field(default_factory=list)


class SiteErrorLogSchema(BaseModel):
    source: str = ""
    content: str = ""
