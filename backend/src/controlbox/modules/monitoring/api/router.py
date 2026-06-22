from datetime import datetime
from typing import Annotated
from uuid import UUID
import json

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect

from controlbox.modules.identity.api.dependencies import (
    AppState,
    RequestContext,
    get_current_context,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.identity.domain.services import TokenService
from controlbox.modules.monitoring.api.schemas import (
    DatabaseMetricSchema,
    DockerContainerSchema,
    HostMetricsSchema,
    MetricHistorySchema,
    MetricPointSchema,
    MonitoringHistorySchema,
    MonitoringOverviewSchema,
    ServiceHealthSchema,
    SupabaseMetricSchema,
    WebsiteMetricSchema,
)
from controlbox.modules.monitoring.infrastructure.broadcaster import MonitoringBroadcaster
from controlbox.modules.monitoring.infrastructure.service import MonitoringCollectorTask
from controlbox.modules.monitoring.infrastructure.store import MetricsStore
from controlbox.shared.domain.base import ForbiddenError, UnauthorizedError
from controlbox.shared.infrastructure.redis.client import RedisClient


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _get_collector(request: Request) -> MonitoringCollectorTask:
    return request.app.state.monitoring_collector


def _get_broadcaster(request: Request) -> MonitoringBroadcaster:
    return request.app.state.monitoring_broadcaster


def _get_store(request: Request) -> MetricsStore:
    container: AppState = request.app.state.container
    return MetricsStore(container.redis_client)


def _dict_to_overview(data: dict) -> MonitoringOverviewSchema:
    host = data.get("host", {})
    collected = data.get("collected_at")
    if isinstance(collected, str):
        collected = datetime.fromisoformat(collected)
    return MonitoringOverviewSchema(
        host=HostMetricsSchema(**host),
        docker=[DockerContainerSchema(**d) for d in data.get("docker", [])],
        databases=[DatabaseMetricSchema(**d) for d in data.get("databases", [])],
        supabase=[SupabaseMetricSchema(**s) for s in data.get("supabase", [])],
        websites=[WebsiteMetricSchema(**w) for w in data.get("websites", [])],
        services=[ServiceHealthSchema(**s) for s in data.get("services", [])],
        collected_at=collected,
    )


async def _fetch_overview(request: Request, tenant_id: UUID) -> MonitoringOverviewSchema:
    store = _get_store(request)
    cached = await store.get_snapshot(tenant_id)
    if cached:
        return _dict_to_overview(cached)
    collector = _get_collector(request)
    snapshot = await collector.collect_for_tenant(tenant_id)
    return _dict_to_overview(store._serialize_snapshot(snapshot))


@router.get("/overview", response_model=MonitoringOverviewSchema)
async def get_overview(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
) -> MonitoringOverviewSchema:
    tenant_id = _require_tenant(context)
    return await _fetch_overview(request, tenant_id)


@router.get("/history", response_model=MonitoringHistorySchema)
async def get_history(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
    limit: int = Query(default=60, ge=1, le=120),
) -> MonitoringHistorySchema:
    tenant_id = _require_tenant(context)
    store = _get_store(request)

    cpu = await store.get_history(tenant_id, "cpu", limit)
    memory = await store.get_history(tenant_id, "memory", limit)
    disk = await store.get_history(tenant_id, "disk", limit)
    net_in = await store.get_history(tenant_id, "network_in", limit)
    net_out = await store.get_history(tenant_id, "network_out", limit)

    to_schema = lambda points: [MetricPointSchema(timestamp=p.timestamp, value=p.value) for p in points]

    return MonitoringHistorySchema(
        cpu=to_schema(cpu),
        memory=to_schema(memory),
        disk=to_schema(disk),
        network_in=to_schema(net_in),
        network_out=to_schema(net_out),
    )


@router.get("/history/{metric}", response_model=MetricHistorySchema)
async def get_metric_history(
    metric: str,
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
    limit: int = Query(default=60, ge=1, le=120),
) -> MetricHistorySchema:
    tenant_id = _require_tenant(context)
    store = _get_store(request)
    points = await store.get_history(tenant_id, metric, limit)
    return MetricHistorySchema(
        metric=metric,
        points=[MetricPointSchema(timestamp=p.timestamp, value=p.value) for p in points],
    )


@router.get("/docker", response_model=list[DockerContainerSchema])
async def get_docker_metrics(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
) -> list[DockerContainerSchema]:
    overview = await _fetch_overview(request, _require_tenant(context))
    return overview.docker


@router.get("/databases", response_model=list[DatabaseMetricSchema])
async def get_database_metrics(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
) -> list[DatabaseMetricSchema]:
    overview = await _fetch_overview(request, _require_tenant(context))
    return overview.databases


@router.get("/supabase", response_model=list[SupabaseMetricSchema])
async def get_supabase_metrics(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
) -> list[SupabaseMetricSchema]:
    overview = await _fetch_overview(request, _require_tenant(context))
    return overview.supabase


@router.get("/websites", response_model=list[WebsiteMetricSchema])
async def get_website_metrics(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
) -> list[WebsiteMetricSchema]:
    overview = await _fetch_overview(request, _require_tenant(context))
    return overview.websites


@router.get("/services", response_model=list[ServiceHealthSchema])
async def get_service_health(
    request: Request,
    context: Annotated[RequestContext, Depends(get_current_context)],
    _: Annotated[None, Depends(require_permission("monitoring.read"))],
) -> list[ServiceHealthSchema]:
    overview = await _fetch_overview(request, _require_tenant(context))
    return overview.services


async def monitoring_websocket(
    websocket: WebSocket,
    token: str | None,
    app_state: AppState,
    broadcaster: MonitoringBroadcaster,
    session_cache,
    token_service: TokenService,
) -> None:
    from controlbox.shared.infrastructure.security.cookies import ACCESS_COOKIE_NAME

    if not token:
        token = websocket.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        claims = token_service.decode_access_token(token)
    except UnauthorizedError:
        await websocket.close(code=4401)
        return

    if await session_cache.is_access_token_blacklisted(claims.jti):
        await websocket.close(code=4401)
        return

    session_id = UUID(claims.session_id)
    if not await session_cache.is_session_active(session_id):
        await websocket.close(code=4401)
        return

    if "monitoring.read" not in claims.permissions:
        await websocket.close(code=4403)
        return

    tenant_id = UUID(claims.tenant_id) if claims.tenant_id else None
    if not tenant_id:
        await websocket.close(code=4403)
        return

    await broadcaster.connect(tenant_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            if raw == "ping" or raw == "pong":
                await websocket.send_text("pong")
                continue
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_text("pong")
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect(tenant_id, websocket)
