from datetime import datetime

from pydantic import BaseModel, Field


class FileEntrySchema(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    permissions: str
    modified_at: datetime
    extension: str | None = None
    editable: bool = False


class BrowseResponseSchema(BaseModel):
    path: str
    parent: str | None
    entries: list[FileEntrySchema]


class WriteContentRequest(BaseModel):
    path: str
    content: str


class ReadContentResponse(BaseModel):
    path: str
    content: str
    extension: str


class MkdirRequest(BaseModel):
    path: str


class RenameRequest(BaseModel):
    path: str
    new_name: str


class DeleteRequest(BaseModel):
    path: str


class CompressRequest(BaseModel):
    paths: list[str] = Field(min_length=1)
    archive_name: str
    dest_dir: str = ""


class ExtractRequest(BaseModel):
    archive_path: str
    dest_dir: str = ""


class PermissionsRequest(BaseModel):
    path: str
    mode: str


class PermissionsResponse(BaseModel):
    path: str
    mode: str
    readable: bool
    writable: bool
    executable: bool
