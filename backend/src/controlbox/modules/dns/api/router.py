from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from controlbox.config.settings import get_settings
from controlbox.modules.dns.api.schemas import (
    CreateDnsApiKeyRequest,
    CreateDnsRecordRequest,
    CreateDnsZoneRequest,
    DnsApiKeyCreatedSchema,
    DnsApiKeySchema,
    DnsRecordSchema,
    DnsZoneSchema,
    ImportZoneRequest,
    RecordTypesSchema,
    UpdateDnsRecordRequest,
    UpdateDnsZoneRequest,
)
from controlbox.modules.dns.application.command_handlers import (
    CreateDnsApiKeyHandler,
    CreateDnsRecordHandler,
    CreateDnsZoneHandler,
    DeleteDnsRecordHandler,
    DeleteDnsZoneHandler,
    ImportDnsZoneHandler,
    RevokeDnsApiKeyHandler,
    UpdateDnsRecordHandler,
    UpdateDnsZoneHandler,
)
from controlbox.modules.dns.application.commands import (
    CreateDnsApiKeyCommand,
    CreateDnsRecordCommand,
    CreateDnsZoneCommand,
    DeleteDnsRecordCommand,
    DeleteDnsZoneCommand,
    ImportDnsZoneCommand,
    RevokeDnsApiKeyCommand,
    UpdateDnsRecordCommand,
    UpdateDnsZoneCommand,
)
from controlbox.modules.dns.application.query_handlers import (
    ExportDnsZoneHandler,
    GetDnsRecordTypesHandler,
    GetDnsZoneHandler,
    ListDnsApiKeysHandler,
    ListDnsRecordsHandler,
    ListDnsZonesHandler,
)
from controlbox.modules.dns.application.queries import (
    ExportDnsZoneQuery,
    GetDnsRecordTypesQuery,
    GetDnsZoneQuery,
    ListDnsApiKeysQuery,
    ListDnsRecordsQuery,
    ListDnsZonesQuery,
)
from controlbox.modules.dns.api.mappers import to_record_schema, to_zone_schema
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError


router = APIRouter(prefix="/dns", tags=["dns"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


@router.get("/record-types", response_model=RecordTypesSchema)
async def get_record_types(
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
) -> RecordTypesSchema:
    types = await GetDnsRecordTypesHandler().handle(GetDnsRecordTypesQuery())
    return RecordTypesSchema(types=types)


@router.get("/zones", response_model=list[DnsZoneSchema])
async def list_zones(
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[DnsZoneSchema]:
    tenant_id = _require_tenant(context)
    try:
        zones = await ListDnsZonesHandler(uow=uow).handle(
            ListDnsZonesQuery(tenant_id=tenant_id, limit=limit, offset=offset)
        )
        return [to_zone_schema(z) for z in zones]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/zones", response_model=DnsZoneSchema, status_code=status.HTTP_201_CREATED)
async def create_zone(
    body: CreateDnsZoneRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    tenant_id = _require_tenant(context)
    try:
        zone = await CreateDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            CreateDnsZoneCommand(
                tenant_id=tenant_id,
                name=body.name,
                soa_email=body.soa_email,
                default_ttl=body.default_ttl,
                nameservers=body.nameservers,
            )
        )
        return to_zone_schema(zone)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/zones/{zone_id}", response_model=DnsZoneSchema)
async def get_zone(
    zone_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    tenant_id = _require_tenant(context)
    try:
        zone = await GetDnsZoneHandler(uow=uow).handle(GetDnsZoneQuery(tenant_id=tenant_id, zone_id=zone_id))
        return to_zone_schema(zone)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.put("/zones/{zone_id}", response_model=DnsZoneSchema)
async def update_zone(
    zone_id: UUID,
    body: UpdateDnsZoneRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    tenant_id = _require_tenant(context)
    try:
        zone = await UpdateDnsZoneHandler(uow=uow).handle(
            UpdateDnsZoneCommand(
                tenant_id=tenant_id,
                zone_id=zone_id,
                soa_email=body.soa_email,
                default_ttl=body.default_ttl,
                nameservers=body.nameservers,
            )
        )
        return to_zone_schema(zone)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            DeleteDnsZoneCommand(tenant_id=tenant_id, zone_id=zone_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/zones/{zone_id}/import", response_model=DnsZoneSchema)
async def import_zone(
    zone_id: UUID,
    body: ImportZoneRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    tenant_id = _require_tenant(context)
    try:
        zone = await ImportDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            ImportDnsZoneCommand(tenant_id=tenant_id, zone_id=zone_id, content=body.content)
        )
        return to_zone_schema(zone)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/zones/{zone_id}/export")
async def export_zone(
    zone_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> Response:
    tenant_id = _require_tenant(context)
    try:
        content = await ExportDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            ExportDnsZoneQuery(tenant_id=tenant_id, zone_id=zone_id)
        )
        return Response(content=content, media_type="text/plain")
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/zones/{zone_id}/records", response_model=list[DnsRecordSchema])
async def list_records(
    zone_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DnsRecordSchema]:
    tenant_id = _require_tenant(context)
    try:
        records = await ListDnsRecordsHandler(uow=uow, settings=get_settings()).handle(
            ListDnsRecordsQuery(tenant_id=tenant_id, zone_id=zone_id)
        )
        return [to_record_schema(r) for r in records]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/zones/{zone_id}/records", response_model=DnsRecordSchema, status_code=status.HTTP_201_CREATED)
async def create_record(
    zone_id: UUID,
    body: CreateDnsRecordRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsRecordSchema:
    tenant_id = _require_tenant(context)
    try:
        record = await CreateDnsRecordHandler(uow=uow, settings=get_settings()).handle(
            CreateDnsRecordCommand(
                tenant_id=tenant_id,
                zone_id=zone_id,
                name=body.name,
                record_type=body.record_type,
                content=body.content,
                ttl=body.ttl,
                priority=body.priority,
            )
        )
        return to_record_schema(record)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.put("/zones/{zone_id}/records/{record_name}/{record_type}", response_model=DnsRecordSchema)
async def update_record(
    zone_id: UUID,
    record_name: str,
    record_type: str,
    body: UpdateDnsRecordRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsRecordSchema:
    tenant_id = _require_tenant(context)
    try:
        record = await UpdateDnsRecordHandler(uow=uow, settings=get_settings()).handle(
            UpdateDnsRecordCommand(
                tenant_id=tenant_id,
                zone_id=zone_id,
                name=record_name,
                record_type=record_type,
                content=body.content,
                ttl=body.ttl,
                priority=body.priority,
            )
        )
        return to_record_schema(record)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/zones/{zone_id}/records/{record_name}/{record_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(
    zone_id: UUID,
    record_name: str,
    record_type: str,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteDnsRecordHandler(uow=uow, settings=get_settings()).handle(
            DeleteDnsRecordCommand(
                tenant_id=tenant_id,
                zone_id=zone_id,
                name=record_name,
                record_type=record_type,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/api-keys", response_model=list[DnsApiKeySchema])
async def list_api_keys(
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DnsApiKeySchema]:
    tenant_id = _require_tenant(context)
    try:
        keys = await ListDnsApiKeysHandler(uow=uow).handle(ListDnsApiKeysQuery(tenant_id=tenant_id))
        return [
            DnsApiKeySchema(
                id=k.id, name=k.name, key_prefix=k.key_prefix, is_active=k.is_active,
                scopes=k.scopes, last_used_at=k.last_used_at, created_at=k.created_at,
            )
            for k in keys
        ]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/api-keys", response_model=DnsApiKeyCreatedSchema, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateDnsApiKeyRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsApiKeyCreatedSchema:
    tenant_id = _require_tenant(context)
    try:
        api_key, full_key = await CreateDnsApiKeyHandler(uow=uow).handle(
            CreateDnsApiKeyCommand(tenant_id=tenant_id, name=body.name, scopes=body.scopes)
        )
        schema = DnsApiKeySchema(
            id=api_key.id, name=api_key.name, key_prefix=api_key.key_prefix,
            is_active=api_key.is_active, scopes=api_key.scopes,
            last_used_at=api_key.last_used_at, created_at=api_key.created_at,
        )
        return DnsApiKeyCreatedSchema(**schema.model_dump(), api_key=full_key)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await RevokeDnsApiKeyHandler(uow=uow).handle(
            RevokeDnsApiKeyCommand(tenant_id=tenant_id, key_id=key_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
