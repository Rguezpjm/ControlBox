from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.cloudflare.api.schemas import (
    CloudflareActionResponse,
    CloudflareDnsRecordSchema,
    CloudflareSettingsSchema,
    CloudflareTunnelStatusSchema,
    CloudflareZoneActionRequest,
    CloudflareZoneSchema,
    CreateCloudflareDnsRecordRequest,
    CreateCloudflareZoneRequest,
    TestCloudflareRequest,
    UpdateCloudflareDnsRecordRequest,
    UpdateCloudflareSettingsRequest,
)
from controlbox.modules.cloudflare.infrastructure.cloudflare_client import CloudflareApiError
from controlbox.modules.cloudflare.infrastructure.settings_service import CloudflareSettingsService
from controlbox.modules.cloudflare.infrastructure.tunnel_manager import CloudflareTunnelManager
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    require_permission,
)
from controlbox.modules.platform.api.router import require_platform_admin
from controlbox.shared.application.unit_of_work import UnitOfWork


router = APIRouter(prefix="/cloudflare", tags=["cloudflare"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required")
    return context.tenant_id


async def _platform_settings(uow: UnitOfWork, tenant_id: UUID):
    return await uow.tenant_platform_settings.get_or_create(tenant_id)


def _zone_schema(raw: dict) -> CloudflareZoneSchema:
    security = str(raw.get("security_level", "medium"))
    return CloudflareZoneSchema(
        id=str(raw["id"]),
        name=str(raw.get("name", "")),
        status=str(raw.get("status", "unknown")),
        paused=bool(raw.get("paused", False)),
        security_level=security,
        name_servers=list(raw.get("name_servers") or []),
    )


def _record_schema(raw: dict) -> CloudflareDnsRecordSchema:
    return CloudflareDnsRecordSchema(
        id=str(raw["id"]),
        type=str(raw.get("type", "")),
        name=str(raw.get("name", "")),
        content=str(raw.get("content", "")),
        ttl=int(raw.get("ttl") or 1),
        proxied=bool(raw.get("proxied", False)),
        priority=raw.get("priority"),
    )


async def _require_cloudflare_client(
    platform,
    settings: Settings,
) -> CloudflareSettingsService:
    service = CloudflareSettingsService(settings)
    if not platform.cloudflare_enabled or not platform.cloudflare_api_token_enc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare is not configured. Add your API token in Settings → Cloudflare.",
        )
    return service


@router.get("/settings", response_model=CloudflareSettingsSchema)
async def get_cloudflare_settings(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareSettingsSchema:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    view = CloudflareSettingsService(settings).build_settings_view(platform)
    tunnel = await CloudflareTunnelManager(settings).status(platform)
    view["tunnel_running"] = tunnel.running
    return CloudflareSettingsSchema(**view)


@router.patch("/settings", response_model=CloudflareSettingsSchema)
async def update_cloudflare_settings(
    payload: UpdateCloudflareSettingsRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareSettingsSchema:
    tenant_id = _require_tenant(context)
    service = CloudflareSettingsService(settings)
    tunnel_mgr = CloudflareTunnelManager(settings)
    platform = await _platform_settings(uow, tenant_id)

    service.apply_settings(
        platform,
        enabled=payload.enabled,
        api_token=payload.api_token,
        account_id=payload.account_id,
        tunnel_hostname=payload.tunnel_hostname,
    )

    if payload.tunnel_enabled is True:
        ok, message = await tunnel_mgr.enable_tunnel(platform)
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    elif payload.tunnel_enabled is False and platform.cloudflare_tunnel_enabled:
        await tunnel_mgr.disable_tunnel(platform)

    await uow.tenant_platform_settings.save(platform)
    await uow.commit()

    view = service.build_settings_view(platform)
    tunnel = await tunnel_mgr.status(platform)
    view["tunnel_running"] = tunnel.running
    return CloudflareSettingsSchema(**view)


@router.post("/settings/test", response_model=CloudflareActionResponse)
async def test_cloudflare_connection(
    payload: TestCloudflareRequest,
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareActionResponse:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    service = CloudflareSettingsService(settings)
    ok, message, account_id = await service.test_connection(
        platform,
        api_token=payload.api_token,
        account_id=payload.account_id,
    )
    if ok and account_id and not platform.cloudflare_account_id:
        platform.cloudflare_account_id = account_id
        await uow.tenant_platform_settings.save(platform)
        await uow.commit()
    return CloudflareActionResponse(success=ok, message=message, account_id=account_id)


@router.get("/tunnel/status", response_model=CloudflareTunnelStatusSchema)
async def cloudflare_tunnel_status(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareTunnelStatusSchema:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    status_view = await CloudflareTunnelManager(settings).status(platform)
    return CloudflareTunnelStatusSchema(
        enabled=status_view.enabled,
        running=status_view.running,
        tunnel_id=status_view.tunnel_id,
        hostname=status_view.hostname,
        message=status_view.message,
    )


@router.post("/tunnel/start", response_model=CloudflareActionResponse)
async def start_cloudflare_tunnel(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareActionResponse:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    await _require_cloudflare_client(platform, settings)
    ok, message = await CloudflareTunnelManager(settings).enable_tunnel(platform)
    await uow.tenant_platform_settings.save(platform)
    await uow.commit()
    return CloudflareActionResponse(success=ok, message=message)


@router.post("/tunnel/stop", response_model=CloudflareActionResponse)
async def stop_cloudflare_tunnel(
    context: Annotated[RequestContext, Depends(require_platform_admin())],
    _: Annotated[None, Depends(require_permission("platform.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareActionResponse:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    ok, message = await CloudflareTunnelManager(settings).disable_tunnel(platform)
    await uow.tenant_platform_settings.save(platform)
    await uow.commit()
    return CloudflareActionResponse(success=ok, message=message)


@router.get("/zones", response_model=list[CloudflareZoneSchema])
async def list_cloudflare_zones(
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CloudflareZoneSchema]:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        zones = await client.list_zones()
        return [_zone_schema(z) for z in zones]
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/zones", response_model=CloudflareZoneSchema, status_code=status.HTTP_201_CREATED)
async def create_cloudflare_zone(
    payload: CreateCloudflareZoneRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareZoneSchema:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        zone = await client.create_zone(payload.name)
        return _zone_schema(zone)
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/zones/{zone_id}", response_model=CloudflareZoneSchema)
async def update_cloudflare_zone(
    zone_id: str,
    payload: CloudflareZoneActionRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareZoneSchema:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        if payload.paused is not None:
            await client.set_zone_paused(zone_id, payload.paused)
        if payload.under_attack is not None:
            level = "under_attack" if payload.under_attack else "medium"
            await client.set_security_level(zone_id, level)
        zone = await client.get_zone(zone_id)
        return _zone_schema(zone)
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloudflare_zone(
    zone_id: str,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        await client.delete_zone(zone_id)
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/zones/{zone_id}/dns-records", response_model=list[CloudflareDnsRecordSchema])
async def list_cloudflare_dns_records(
    zone_id: str,
    context: Annotated[RequestContext, Depends(require_permission("dns.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CloudflareDnsRecordSchema]:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        records = await client.list_dns_records(zone_id)
        return [_record_schema(r) for r in records]
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/zones/{zone_id}/dns-records", response_model=CloudflareDnsRecordSchema, status_code=status.HTTP_201_CREATED)
async def create_cloudflare_dns_record(
    zone_id: str,
    payload: CreateCloudflareDnsRecordRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareDnsRecordSchema:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        record = await client.create_dns_record(
            zone_id,
            record_type=payload.type,
            name=payload.name,
            content=payload.content,
            ttl=payload.ttl,
            proxied=payload.proxied,
            priority=payload.priority,
        )
        return _record_schema(record)
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/zones/{zone_id}/dns-records/{record_id}", response_model=CloudflareDnsRecordSchema)
async def update_cloudflare_dns_record(
    zone_id: str,
    record_id: str,
    payload: UpdateCloudflareDnsRecordRequest,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudflareDnsRecordSchema:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        record = await client.update_dns_record(
            zone_id,
            record_id,
            record_type=payload.type,
            name=payload.name,
            content=payload.content,
            ttl=payload.ttl,
            proxied=payload.proxied,
            priority=payload.priority,
        )
        return _record_schema(record)
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/zones/{zone_id}/dns-records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloudflare_dns_record(
    zone_id: str,
    record_id: str,
    context: Annotated[RequestContext, Depends(require_permission("dns.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    tenant_id = _require_tenant(context)
    platform = await _platform_settings(uow, tenant_id)
    cf_service = await _require_cloudflare_client(platform, settings)
    try:
        client = await cf_service.client_for(platform)
        await client.delete_dns_record(zone_id, record_id)
    except CloudflareApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
