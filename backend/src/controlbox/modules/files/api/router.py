import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from controlbox.config.settings import get_settings
from controlbox.modules.files.api.schemas import (
    BrowseResponseSchema,
    CompressRequest,
    ExtractRequest,
    FileEntrySchema,
    MkdirRequest,
    PermissionsRequest,
    PermissionsResponse,
    ReadContentResponse,
    RenameRequest,
    WriteContentRequest,
)
from controlbox.modules.files.infrastructure.filesystem_service import FileSystemService
from controlbox.modules.files.infrastructure.site_folder_labels import (
    build_folder_display_names,
    build_path_labels,
    list_site_folders,
)
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError, NotFoundError


router = APIRouter(prefix="/files", tags=["files"])


def _resolve_scope_tenant(context: RequestContext) -> UUID | None:
    if context.is_platform_admin:
        return None
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _service() -> FileSystemService:
    return FileSystemService(get_settings())


def _to_entry_schema(entry, display_name: str | None = None) -> FileEntrySchema:
    return FileEntrySchema(
        name=entry.name,
        path=entry.path,
        display_name=display_name,
        is_dir=entry.is_dir,
        size=entry.size,
        permissions=entry.permissions,
        modified_at=entry.modified_at,
        extension=entry.extension,
        editable=entry.editable,
    )


async def _browse_entries(
    context: RequestContext,
    uow: UnitOfWork,
    tenant_id: UUID | None,
    path: str,
) -> BrowseResponseSchema:
    service = _service()
    path_labels = await build_path_labels(uow, context, tenant_id) if tenant_id else {}

    if tenant_id is not None and path == "":
        fs_result = await asyncio.to_thread(service.browse, tenant_id, "")
        site_folders = await list_site_folders(uow, context, tenant_id)
        site_paths = {folder.path for folder in site_folders}
        entries: list[FileEntrySchema] = []

        for folder in site_folders:
            try:
                entry = await asyncio.to_thread(service.get_entry, tenant_id, folder.path)
            except NotFoundError:
                continue
            if not entry.is_dir:
                continue
            entries.append(_to_entry_schema(entry, display_name=folder.domain))

        for entry in fs_result.entries:
            if entry.is_dir and (
                entry.path in site_paths
                or entry.path == "wordpress"
                or entry.path.startswith("wordpress/")
            ):
                continue
            entries.append(_to_entry_schema(entry))

        return BrowseResponseSchema(
            path=fs_result.path,
            parent=fs_result.parent,
            entries=entries,
            path_labels=path_labels,
        )

    result = await asyncio.to_thread(service.browse, tenant_id, path)
    name_labels = await build_folder_display_names(uow, context, tenant_id, path)
    return BrowseResponseSchema(
        path=result.path,
        parent=result.parent,
        entries=[
            _to_entry_schema(
                entry,
                display_name=(
                    path_labels.get(entry.path)
                    or name_labels.get(entry.name)
                    if entry.is_dir
                    else None
                ),
            )
            for entry in result.entries
        ],
        path_labels=path_labels,
    )


@router.get("/browse", response_model=BrowseResponseSchema)
async def browse(
    context: Annotated[RequestContext, Depends(require_permission("files.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    path: str = "",
) -> BrowseResponseSchema:
    tenant_id = _resolve_scope_tenant(context)
    try:
        return await _browse_entries(context, uow, tenant_id, path)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except OSError as exc:
        raise map_domain_exception(ForbiddenError(f"Filesystem error: {exc}")) from exc


@router.get("/content", response_model=ReadContentResponse)
async def read_content(
    context: Annotated[RequestContext, Depends(require_permission("files.read"))],
    path: str = Query(...),
) -> ReadContentResponse:
    tenant_id = _resolve_scope_tenant(context)
    try:
        content, ext = await asyncio.to_thread(_service().read_content, tenant_id, path)
        return ReadContentResponse(path=path, content=content, extension=ext)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.put("/content", response_model=FileEntrySchema)
async def write_content(
    body: WriteContentRequest,
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
) -> FileEntrySchema:
    tenant_id = _resolve_scope_tenant(context)
    try:
        entry = await asyncio.to_thread(_service().write_content, tenant_id, body.path, body.content)
        return _to_entry_schema(entry)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/download")
async def download_file(
    context: Annotated[RequestContext, Depends(require_permission("files.read"))],
    path: str = Query(...),
):
    tenant_id = _resolve_scope_tenant(context)
    try:
        file_path = await asyncio.to_thread(_service().resolve_download, tenant_id, path)
        return FileResponse(path=file_path, filename=file_path.name)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/upload", response_model=FileEntrySchema, status_code=status.HTTP_201_CREATED)
async def upload_file(
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
    file: UploadFile = File(...),
    directory: str = "",
) -> FileEntrySchema:
    tenant_id = _resolve_scope_tenant(context)
    data = await file.read()
    try:
        entry = await asyncio.to_thread(
            _service().upload, tenant_id, directory, file.filename or "upload.bin", data
        )
        return _to_entry_schema(entry)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/mkdir", response_model=FileEntrySchema, status_code=status.HTTP_201_CREATED)
async def create_directory(
    body: MkdirRequest,
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
) -> FileEntrySchema:
    tenant_id = _resolve_scope_tenant(context)
    try:
        entry = await asyncio.to_thread(_service().mkdir, tenant_id, body.path)
        return _to_entry_schema(entry)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/rename", response_model=FileEntrySchema)
async def rename_path(
    body: RenameRequest,
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
) -> FileEntrySchema:
    tenant_id = _resolve_scope_tenant(context)
    try:
        entry = await asyncio.to_thread(_service().rename, tenant_id, body.path, body.new_name)
        return _to_entry_schema(entry)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_path(
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
    path: str = Query(...),
) -> None:
    tenant_id = _resolve_scope_tenant(context)
    try:
        await asyncio.to_thread(_service().delete, tenant_id, path)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/compress", response_model=FileEntrySchema, status_code=status.HTTP_201_CREATED)
async def compress_paths(
    body: CompressRequest,
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
) -> FileEntrySchema:
    tenant_id = _resolve_scope_tenant(context)
    try:
        entry = await asyncio.to_thread(
            _service().compress, tenant_id, body.paths, body.archive_name, body.dest_dir
        )
        return _to_entry_schema(entry)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/extract", response_model=BrowseResponseSchema)
async def extract_archive(
    body: ExtractRequest,
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> BrowseResponseSchema:
    tenant_id = _resolve_scope_tenant(context)
    try:
        result = await asyncio.to_thread(
            _service().extract, tenant_id, body.archive_path, body.dest_dir
        )
        labels = await build_folder_display_names(uow, context, tenant_id, result.path)
        path_labels = await build_path_labels(uow, context, tenant_id) if tenant_id else {}
        return BrowseResponseSchema(
            path=result.path,
            parent=result.parent,
            entries=[
                _to_entry_schema(
                    entry,
                    display_name=(
                        path_labels.get(entry.path)
                        or labels.get(entry.name)
                        if entry.is_dir
                        else None
                    ),
                )
                for entry in result.entries
            ],
            path_labels=path_labels,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/permissions", response_model=PermissionsResponse)
async def get_permissions(
    context: Annotated[RequestContext, Depends(require_permission("files.read"))],
    path: str = Query(...),
) -> PermissionsResponse:
    tenant_id = _resolve_scope_tenant(context)
    try:
        data = await asyncio.to_thread(_service().get_permissions, tenant_id, path)
        return PermissionsResponse(**data)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.put("/permissions", response_model=PermissionsResponse)
async def set_permissions(
    body: PermissionsRequest,
    context: Annotated[RequestContext, Depends(require_permission("files.manage"))],
) -> PermissionsResponse:
    tenant_id = _resolve_scope_tenant(context)
    try:
        data = await asyncio.to_thread(_service().set_permissions, tenant_id, body.path, body.mode)
        return PermissionsResponse(**data)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
