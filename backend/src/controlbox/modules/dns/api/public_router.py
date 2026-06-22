from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from controlbox.config.settings import get_settings
from controlbox.modules.dns.api.dependencies import IntegrationContext, require_scope
from controlbox.modules.dns.api.schemas import (
    CreateDnsRecordRequest,
    CreateDnsZoneRequest,
    DnsRecordSchema,
    DnsZoneSchema,
    ImportZoneRequest,
    UpdateDnsRecordRequest,
    UpdateDnsZoneRequest,
)
from controlbox.modules.dns.application.command_handlers import (
    CreateDnsRecordHandler,
    CreateDnsZoneHandler,
    DeleteDnsRecordHandler,
    DeleteDnsZoneHandler,
    ImportDnsZoneHandler,
    UpdateDnsRecordHandler,
    UpdateDnsZoneHandler,
)
from controlbox.modules.dns.application.commands import (
    CreateDnsRecordCommand,
    CreateDnsZoneCommand,
    DeleteDnsRecordCommand,
    DeleteDnsZoneCommand,
    ImportDnsZoneCommand,
    UpdateDnsRecordCommand,
    UpdateDnsZoneCommand,
)
from controlbox.modules.dns.application.query_handlers import (
    ExportDnsZoneHandler,
    GetDnsZoneHandler,
    ListDnsRecordsHandler,
    ListDnsZonesHandler,
)
from controlbox.modules.dns.application.queries import (
    ExportDnsZoneQuery,
    GetDnsZoneQuery,
    ListDnsRecordsQuery,
    ListDnsZonesQuery,
)
from controlbox.modules.dns.api.mappers import to_record_schema, to_zone_schema
from controlbox.modules.identity.api.dependencies import get_unit_of_work
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException


public_router = APIRouter(prefix="/integrations/dns", tags=["dns-integrations"])


@public_router.get("/zones", response_model=list[DnsZoneSchema])
async def public_list_zones(
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DnsZoneSchema]:
    try:
        zones = await ListDnsZonesHandler(uow=uow).handle(ListDnsZonesQuery(tenant_id=ctx.tenant_id))
        return [to_zone_schema(z) for z in zones]
    except DomainException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.post("/zones", response_model=DnsZoneSchema, status_code=status.HTTP_201_CREATED)
async def public_create_zone(
    body: CreateDnsZoneRequest,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    try:
        zone = await CreateDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            CreateDnsZoneCommand(
                tenant_id=ctx.tenant_id,
                name=body.name,
                soa_email=body.soa_email,
                default_ttl=body.default_ttl,
                nameservers=body.nameservers,
            )
        )
        return to_zone_schema(zone)
    except DomainException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.get("/zones/{zone_id}", response_model=DnsZoneSchema)
async def public_get_zone(
    zone_id: UUID,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    try:
        zone = await GetDnsZoneHandler(uow=uow).handle(GetDnsZoneQuery(tenant_id=ctx.tenant_id, zone_id=zone_id))
        return to_zone_schema(zone)
    except DomainException as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@public_router.put("/zones/{zone_id}", response_model=DnsZoneSchema)
async def public_update_zone(
    zone_id: UUID,
    body: UpdateDnsZoneRequest,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    try:
        zone = await UpdateDnsZoneHandler(uow=uow).handle(
            UpdateDnsZoneCommand(
                tenant_id=ctx.tenant_id,
                zone_id=zone_id,
                soa_email=body.soa_email,
                default_ttl=body.default_ttl,
                nameservers=body.nameservers,
            )
        )
        return to_zone_schema(zone)
    except DomainException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def public_delete_zone(
    zone_id: UUID,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        await DeleteDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            DeleteDnsZoneCommand(tenant_id=ctx.tenant_id, zone_id=zone_id)
        )
    except DomainException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.post("/zones/{zone_id}/import", response_model=DnsZoneSchema)
async def public_import_zone(
    zone_id: UUID,
    body: ImportZoneRequest,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsZoneSchema:
    try:
        zone = await ImportDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            ImportDnsZoneCommand(tenant_id=ctx.tenant_id, zone_id=zone_id, content=body.content)
        )
        return to_zone_schema(zone)
    except DomainException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.get("/zones/{zone_id}/export")
async def public_export_zone(
    zone_id: UUID,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> Response:
    try:
        content = await ExportDnsZoneHandler(uow=uow, settings=get_settings()).handle(
            ExportDnsZoneQuery(tenant_id=ctx.tenant_id, zone_id=zone_id)
        )
        return Response(content=content, media_type="text/plain")
    except DomainException as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@public_router.get("/zones/{zone_id}/records", response_model=list[DnsRecordSchema])
async def public_list_records(
    zone_id: UUID,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[DnsRecordSchema]:
    try:
        records = await ListDnsRecordsHandler(uow=uow, settings=get_settings()).handle(
            ListDnsRecordsQuery(tenant_id=ctx.tenant_id, zone_id=zone_id)
        )
        return [to_record_schema(r) for r in records]
    except DomainException as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@public_router.post("/zones/{zone_id}/records", response_model=DnsRecordSchema, status_code=status.HTTP_201_CREATED)
async def public_create_record(
    zone_id: UUID,
    body: CreateDnsRecordRequest,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsRecordSchema:
    try:
        record = await CreateDnsRecordHandler(uow=uow, settings=get_settings()).handle(
            CreateDnsRecordCommand(
                tenant_id=ctx.tenant_id,
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
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.put("/zones/{zone_id}/records/{record_name}/{record_type}", response_model=DnsRecordSchema)
async def public_update_record(
    zone_id: UUID,
    record_name: str,
    record_type: str,
    body: UpdateDnsRecordRequest,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DnsRecordSchema:
    try:
        record = await UpdateDnsRecordHandler(uow=uow, settings=get_settings()).handle(
            UpdateDnsRecordCommand(
                tenant_id=ctx.tenant_id,
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
        raise HTTPException(status_code=400, detail=exc.message) from exc


@public_router.delete("/zones/{zone_id}/records/{record_name}/{record_type}", status_code=status.HTTP_204_NO_CONTENT)
async def public_delete_record(
    zone_id: UUID,
    record_name: str,
    record_type: str,
    ctx: Annotated[IntegrationContext, Depends(require_scope("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    try:
        await DeleteDnsRecordHandler(uow=uow, settings=get_settings()).handle(
            DeleteDnsRecordCommand(
                tenant_id=ctx.tenant_id,
                zone_id=zone_id,
                name=record_name,
                record_type=record_type,
            )
        )
    except DomainException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
