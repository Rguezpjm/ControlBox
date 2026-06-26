from typing import Annotated
from uuid import UUID, uuid4
from datetime import datetime, timezone
import logging
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, PlainTextResponse

from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    require_permission,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.modules.streaming.api.schemas import (
    CreateStreamingSourceRequest,
    StreamingSourceResponse,
    StreamingCategoryResponse,
    StreamingChannelResponse,
    CreateStreamingClientRequest,
    StreamingClientResponse,
    ImportChannelsRequest,
    ActiveConnectionResponse,
    EpgProgramResponse,
    StreamingStatsResponse,
)
from controlbox.modules.streaming.domain.entities import (
    StreamingSource,
    StreamingCategory,
    StreamingChannel,
    StreamingClient,
    StreamingConnection,
    StreamingSourceType,
    ChannelStatus,
)
from controlbox.modules.streaming.infrastructure.m3u_parser import M3uParser
from controlbox.modules.streaming.infrastructure.xtream_codes import XtreamCodesClient
from controlbox.modules.streaming.infrastructure.stream_relay import StreamRelayManager
from controlbox.modules.streaming.workers.tasks import sync_epg

logger = logging.getLogger("controlbox.streaming.api")
router = APIRouter(prefix="/streaming", tags=["streaming"])
relay_manager = StreamRelayManager()


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required")
    return context.tenant_id


# ==========================================
# ADMIN ENDPOINTS
# ==========================================

@router.post("/sources", response_model=StreamingSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: CreateStreamingSourceRequest,
    context: Annotated[RequestContext, Depends(require_permission("streaming.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StreamingSourceResponse:
    tenant_id = _require_tenant(context)
    source = StreamingSource(
        tenant_id=tenant_id,
        name=payload.name,
        type=StreamingSourceType(payload.type),
        url=payload.url,
        username=payload.username,
        password=payload.password,
    )
    async with uow:
        await uow.streaming_sources.add(source)
        await uow.commit()

    return StreamingSourceResponse(
        id=source.id,
        name=source.name,
        type=source.type.value,
        url=source.url,
        username=source.username,
        status=source.status,
        last_sync_at=source.last_sync_at,
        created_at=source.created_at,
    )


@router.get("/sources", response_model=list[StreamingSourceResponse])
async def list_sources(
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[StreamingSourceResponse]:
    tenant_id = _require_tenant(context)
    async with uow:
        sources = await uow.streaming_sources.list_by_tenant(tenant_id)
        return [
            StreamingSourceResponse(
                id=s.id,
                name=s.name,
                type=s.type.value,
                url=s.url,
                username=s.username,
                status=s.status,
                last_sync_at=s.last_sync_at,
                created_at=s.created_at,
            )
            for s in sources
        ]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("streaming.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    async with uow:
        existing = await uow.streaming_sources.get_by_id_and_tenant(source_id, tenant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")
        await uow.streaming_sources.delete(source_id)
        await uow.commit()


@router.get("/sources/{source_id}/catalog")
async def get_source_catalog(
    source_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    download_txt: bool = False,
):
    """Downloads channels from external M3U/Xtream source and returns metadata catalog."""
    tenant_id = _require_tenant(context)
    async with uow:
        source = await uow.streaming_sources.get_by_id_and_tenant(source_id, tenant_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

    try:
        if source.type == StreamingSourceType.M3U:
            catalog = M3uParser.parse_from_url(source.url)
        else:
            client = XtreamCodesClient(source.url, source.username or "", source.password or "")
            catalog = client.fetch_as_catalog()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse source playlist: {str(e)}")

    if download_txt:
        # Export catalog list to a clean .txt attachment
        lines = []
        for index, item in enumerate(catalog):
            lines.append(
                f"INDEX: {index + 1} | NAME: {item['name']} | CATEGORY: {item['category_name']} | "
                f"EPG_ID: {item.get('epg_id') or 'N/A'} | URL: {item['stream_url']}"
            )
        txt_content = "\n".join(lines)
        return Response(
            content=txt_content,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=catalog_{source.id}.txt"}
        )

    return catalog


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_channels(
    payload: ImportChannelsRequest,
    context: Annotated[RequestContext, Depends(require_permission("streaming.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    tenant_id = _require_tenant(context)
    async with uow:
        source = await uow.streaming_sources.get_by_id_and_tenant(payload.source_id, tenant_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Cargar todas las categorías del tenant en memoria para evitar consultas repetitivas en bucle
        db_categories = await uow.streaming_categories.list_by_tenant(tenant_id)
        categories_by_name = {c.name.lower(): c for c in db_categories}

        # Cargar todos los canales existentes de la fuente en memoria para evitar consultas repetitivas
        from controlbox.modules.streaming.infrastructure.models import StreamingChannelModel
        from controlbox.modules.streaming.infrastructure.mappers import channel_to_entity
        
        result = await uow.session.execute(
            select(StreamingChannelModel).where(
                StreamingChannelModel.source_id == source.id,
                StreamingChannelModel.tenant_id == tenant_id
            )
        )
        db_channel_models = result.scalars().all()
        channels_by_stream_id = {}
        channels_by_url = {}
        
        for m in db_channel_models:
            chan_entity = channel_to_entity(m)
            if chan_entity.stream_id is not None:
                channels_by_stream_id[chan_entity.stream_id] = chan_entity
            channels_by_url[chan_entity.stream_url] = chan_entity

        imported_count = 0
        for item in payload.channels:
            # 1. Resolver categoría
            category_key = item.category_name.lower()
            category = categories_by_name.get(category_key)
            if not category:
                category = StreamingCategory(tenant_id=tenant_id, name=item.category_name)
                await uow.streaming_categories.add(category)
                categories_by_name[category_key] = category

            # 2. Comprobar canal duplicado
            existing = None
            if item.stream_id is not None:
                existing = channels_by_stream_id.get(item.stream_id)
            if not existing:
                existing = channels_by_url.get(item.stream_url)

            if existing:
                existing.name = item.name
                existing.category_id = category.id
                existing.epg_id = item.epg_id
                existing.logo_url = item.logo_url
                existing.stream_id = item.stream_id
                await uow.streaming_channels.save(existing)
            else:
                channel = StreamingChannel(
                    tenant_id=tenant_id,
                    source_id=source.id,
                    category_id=category.id,
                    name=item.name,
                    stream_url=item.stream_url,
                    logo_url=item.logo_url,
                    epg_id=item.epg_id,
                    stream_id=item.stream_id,
                    is_active=True,
                )
                await uow.streaming_channels.add(channel)
                # Agregar al caché local para evitar duplicados si vienen en el mismo payload
                if channel.stream_id is not None:
                    channels_by_stream_id[channel.stream_id] = channel
                channels_by_url[channel.stream_url] = channel
                imported_count += 1

        source.last_sync_at = datetime.utcnow()
        await uow.streaming_sources.save(source)
        await uow.commit()

    return {"status": "success", "imported": imported_count}


@router.get("/channels", response_model=list[StreamingChannelResponse])
async def list_channels(
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[StreamingChannelResponse]:
    tenant_id = _require_tenant(context)
    async with uow:
        channels = await uow.streaming_channels.list_by_tenant(tenant_id)
        return [
            StreamingChannelResponse(
                id=c.id,
                source_id=c.source_id,
                category_id=c.category_id,
                name=c.name,
                stream_url=c.stream_url,
                logo_url=c.logo_url,
                epg_id=c.epg_id,
                is_active=c.is_active,
                status=c.status.value,
            )
            for c in channels
        ]


@router.get("/categories", response_model=list[StreamingCategoryResponse])
async def list_categories(
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[StreamingCategoryResponse]:
    tenant_id = _require_tenant(context)
    async with uow:
        categories = await uow.streaming_categories.list_by_tenant(tenant_id)
        return [StreamingCategoryResponse(id=cat.id, name=cat.name) for cat in categories]


@router.post("/clients", response_model=StreamingClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: CreateStreamingClientRequest,
    context: Annotated[RequestContext, Depends(require_permission("streaming.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StreamingClientResponse:
    tenant_id = _require_tenant(context)
    client = StreamingClient(
        tenant_id=tenant_id,
        username=payload.username,
        password=payload.password,
        max_connections=payload.max_connections,
        is_active=payload.is_active,
        expires_at=payload.expires_at,
        allowed_categories=payload.allowed_categories,
    )
    async with uow:
        # Check duplicate username
        dup = await uow.streaming_clients.get_by_username_and_tenant(payload.username, tenant_id)
        if dup:
            raise HTTPException(status_code=400, detail="Client username already exists")
        await uow.streaming_clients.add(client)
        await uow.commit()

    return StreamingClientResponse(
        id=client.id,
        username=client.username,
        password=client.password,
        max_connections=client.max_connections,
        is_active=client.is_active,
        expires_at=client.expires_at,
        allowed_categories=client.allowed_categories,
        created_at=client.created_at,
    )


@router.get("/clients", response_model=list[StreamingClientResponse])
async def list_clients(
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[StreamingClientResponse]:
    tenant_id = _require_tenant(context)
    async with uow:
        clients = await uow.streaming_clients.list_by_tenant(tenant_id)
        return [
            StreamingClientResponse(
                id=c.id,
                username=c.username,
                password=c.password,
                max_connections=c.max_connections,
                is_active=c.is_active,
                expires_at=c.expires_at,
                allowed_categories=c.allowed_categories,
                created_at=c.created_at,
            )
            for c in clients
        ]


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("streaming.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    async with uow:
        existing = await uow.streaming_clients.get_by_id_and_tenant(client_id, tenant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Client not found")
        await uow.streaming_clients.delete(client_id)
        await uow.commit()


@router.get("/active-connections", response_model=list[ActiveConnectionResponse])
async def list_active_connections(
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[ActiveConnectionResponse]:
    tenant_id = _require_tenant(context)
    async with uow:
        connections = await uow.streaming_connections.list_active_by_tenant(tenant_id)
        results = []
        for conn in connections:
            client = await uow.streaming_clients.get_by_id_and_tenant(conn.client_id, tenant_id)
            channel = await uow.streaming_channels.get_by_id_and_tenant(conn.channel_id, tenant_id)
            results.append(
                ActiveConnectionResponse(
                    id=conn.id,
                    client_username=client.username if client else "Unknown Client",
                    channel_name=channel.name if channel else "Unknown Channel",
                    ip_address=conn.ip_address,
                    user_agent=conn.user_agent,
                    bytes_transferred=conn.bytes_transferred,
                    connected_at=conn.connected_at,
                )
            )
        return results


@router.post("/sync-epg-trigger")
async def trigger_epg_sync(
    url: str,
    context: Annotated[RequestContext, Depends(require_permission("streaming.manage"))],
):
    tenant_id = _require_tenant(context)
    # Trigger XMLTV EPG download in background
    sync_epg.delay(url, str(tenant_id))
    return {"status": "sync_queued"}


@router.get("/stats", response_model=StreamingStatsResponse)
async def get_dashboard_stats(
    context: Annotated[RequestContext, Depends(require_permission("streaming.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> StreamingStatsResponse:
    tenant_id = _require_tenant(context)
    async with uow:
        active_conns = await uow.streaming_connections.list_active_by_tenant(tenant_id)
        channels = await uow.streaming_channels.list_by_tenant(tenant_id)
        
        # Calculate real-time stats
        unique_clients = len(set(c.client_id for c in active_conns))
        # Simulated bandwidth calculation (mocked for graphing, or summed from active transfer rates)
        bandwidth = len(active_conns) * 2.5  # average 2.5 Mbps per viewer session
        
        # Ingestion count
        from controlbox.modules.streaming.infrastructure.stream_relay import ACTIVE_INGESTS
        active_ingest_processes = len(ACTIVE_INGESTS)

        return StreamingStatsResponse(
            connected_users=unique_clients,
            bandwidth_mbps=bandwidth,
            active_streams=active_ingest_processes,
            total_channels=len(channels)
        )


# ==========================================
# CLIENT REDISTRIBUTION & STREAM DELIVERY
# ==========================================

@router.get("/get.php")
async def generate_m3u_list(
    username: str,
    password: str,
    request: Request,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
):
    """Exposes a custom M3U playlist file for authorized streaming clients."""
    async with uow:
        # Direct lookup of clients across tenants (we match client credentials)
        client_res = await uow.session.execute(
            select(StreamingClientModel).where(
                StreamingClientModel.username == username,
                StreamingClientModel.password == password,
                StreamingClientModel.is_active == True
            )
        )
        client_model = client_res.scalar_one_or_none()
        if not client_model:
            raise HTTPException(status_code=401, detail="Invalid streaming credentials")

        if client_model.expires_at and client_model.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Client account has expired")

        # Fetch channels
        chan_res = await uow.session.execute(
            select(StreamingChannelModel).where(
                StreamingChannelModel.tenant_id == client_model.tenant_id,
                StreamingChannelModel.is_active == True
            )
        )
        channels = chan_res.scalars().all()

        # Build custom M3U redirecting back to our server
        host_url = f"{request.url.scheme}://{request.url.netloc}"
        lines = ["#EXTM3U"]
        for chan in channels:
            # Resolve category name
            cat_name = "Uncategorized"
            if chan.category_id:
                cat_res = await uow.session.execute(
                    select(StreamingCategoryModel).where(StreamingCategoryModel.id == chan.category_id)
                )
                cat = cat_res.scalar_one_or_none()
                if cat:
                    cat_name = cat.name

            # Stream url points to our play endpoint
            play_url = f"{host_url}/api/v1/streaming/play/{username}/{password}/{chan.id}.ts"
            logo_attr = f' tvg-logo="{chan.logo_url}"' if chan.logo_url else ""
            epg_attr = f' tvg-id="{chan.epg_id}"' if chan.epg_id else ""
            lines.append(
                f'#EXTINF:-1{epg_attr}{logo_attr} group-title="{cat_name}",{chan.name}\n{play_url}'
            )

        content = "\n".join(lines)
        return Response(
            content=content,
            media_type="application/x-mpegurl",
            headers={"Content-Disposition": "attachment; filename=playlist.m3u"}
        )


@router.get("/player_api.php")
async def xtream_codes_emulation(
    username: str,
    password: str,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    action: str | None = None,
):
    """Emulates a Xtream Codes panel API server."""
    async with uow:
        client_res = await uow.session.execute(
            select(StreamingClientModel).where(
                StreamingClientModel.username == username,
                StreamingClientModel.password == password,
                StreamingClientModel.is_active == True
            )
        )
        client = client_res.scalar_one_or_none()
        if not client:
            return {"user_info": {"auth": 0}}

        exp_timestamp = int(client.expires_at.timestamp()) if client.expires_at else "0"

        # 1. No action: return authorization and credentials response
        if not action:
            return {
                "user_info": {
                    "username": client.username,
                    "password": client.password,
                    "auth": 1,
                    "status": "Active",
                    "exp_date": exp_timestamp,
                    "max_connections": client.max_connections,
                    "active_cons": 0
                },
                "server_info": {
                    "server_timezone": "UTC",
                    "time_now": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
            }

        # 2. Get Categories
        if action == "get_live_categories":
            cats_res = await uow.session.execute(
                select(StreamingCategoryModel).where(StreamingCategoryModel.tenant_id == client.tenant_id)
            )
            return [
                {
                    "category_id": str(c.id),
                    "category_name": c.name,
                    "parent_id": 0
                }
                for c in cats_res.scalars().all()
            ]

        # 3. Get Streams
        if action == "get_live_streams":
            chans_res = await uow.session.execute(
                select(StreamingChannelModel).where(
                    StreamingChannelModel.tenant_id == client.tenant_id,
                    StreamingChannelModel.is_active == True
                )
            )
            streams = []
            for chan in chans_res.scalars().all():
                streams.append({
                    "num": chan.stream_id or 1,
                    "name": chan.name,
                    "stream_type": "live",
                    "stream_id": str(chan.id),
                    "stream_icon": chan.logo_url or "",
                    "epg_channel_id": chan.epg_id or "",
                    "category_id": str(chan.category_id) if chan.category_id else "0",
                })
            return streams

        return {"error": "unknown_action"}


@router.get("/play/{username}/{password}/{channel_id}.ts")
async def play_stream(
    username: str,
    password: str,
    channel_id: UUID,
    request: Request,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
):
    """Relays the video stream back to the authorized client in MPEG-TS format."""
    # 1. Auth client
    async with uow:
        client_res = await uow.session.execute(
            select(StreamingClientModel).where(
                StreamingClientModel.username == username,
                StreamingClientModel.password == password,
                StreamingClientModel.is_active == True
            )
        )
        client = client_res.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=401, detail="Unauthorized")

        if client.expires_at and client.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Subscription expired")

        # 2. Check channel
        channel = await uow.streaming_channels.get_by_id_and_tenant(channel_id, client.tenant_id)
        if not channel or not channel.is_active:
            raise HTTPException(status_code=404, detail="Channel not active or not found")

        # 3. Connection limits
        active_conns = await uow.streaming_connections.get_active_by_client(client.id, client.tenant_id)
        if len(active_conns) >= client.max_connections:
            raise HTTPException(status_code=429, detail="Concurrent connection limit exceeded")

        # 4. Log active connection
        conn = StreamingConnection(
            tenant_id=client.tenant_id,
            client_id=client.id,
            channel_id=channel.id,
            ip_address=request.client.host if request.client else "127.0.0.1",
            user_agent=request.headers.get("User-Agent"),
        )
        await uow.streaming_connections.add(conn)
        await uow.commit()

    conn_id = conn.id

    async def update_traffic(bytes_read: int):
        # Background write update stats in db
        async with get_unit_of_work() as inner_uow:
            db_conn = await inner_uow.streaming_connections.get_by_id(conn_id)
            if db_conn:
                db_conn.bytes_transferred += bytes_read
                await inner_uow.streaming_connections.save(db_conn)
                await inner_uow.commit()

    # Generator helper that cleans up on finish
    async def stream_wrapper():
        try:
            generator = relay_manager.ts_proxy_generator(channel.stream_url, on_chunk_read=update_traffic)
            async for chunk in generator:
                yield chunk
        finally:
            # Client disconnected: Delete connection record
            async with get_unit_of_work() as final_uow:
                await final_uow.streaming_connections.delete(conn_id)
                await final_uow.commit()

    return StreamingResponse(stream_wrapper(), media_type="video/mp2t")


@router.get("/epg.xml", response_class=PlainTextResponse)
async def generate_epg_xml(
    username: str,
    password: str,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
):
    """Serves the program guide (XMLTV format) dynamically to clients."""
    async with uow:
        # Validate client
        client_res = await uow.session.execute(
            select(StreamingClientModel).where(
                StreamingClientModel.username == username,
                StreamingClientModel.password == password,
                StreamingClientModel.is_active == True
            )
        )
        client = client_res.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Fetch EPG programs
        epg_res = await uow.session.execute(
            select(EpgProgramModel).where(EpgProgramModel.tenant_id == client.tenant_id)
        )
        programs = epg_res.scalars().all()

        # Build XML element tree
        tv = Element("tv")
        
        # Add channel display headers
        chan_res = await uow.session.execute(
            select(StreamingChannelModel).where(
                StreamingChannelModel.tenant_id == client.tenant_id,
                StreamingChannelModel.epg_id != None
            )
        )
        for chan in chan_res.scalars().all():
            ch_elem = SubElement(tv, "channel", id=chan.epg_id)
            disp = SubElement(ch_elem, "display-name")
            disp.text = chan.name

        for prog in programs:
            p_elem = SubElement(
                tv,
                "programme",
                start=prog.start_time.strftime("%Y%m%d%H%M%S +0000"),
                stop=prog.end_time.strftime("%Y%m%d%H%M%S +0000"),
                channel=prog.channel_epg_id
            )
            title = SubElement(p_elem, "title")
            title.text = prog.title
            if prog.description:
                desc = SubElement(p_elem, "desc")
                desc.text = prog.description

        xml_string = tostring(tv, encoding="utf-8")
        return Response(content=xml_string, media_type="application/xml")


@router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)]
):
    """Exposes real-time stats in standard Prometheus metrics format."""
    # Direct fetch across all tenants
    async with uow:
        conns_res = await uow.session.execute(select(StreamingConnectionModel))
        connections = conns_res.scalars().all()
        channels_res = await uow.session.execute(select(StreamingChannelModel))
        channels = channels_res.scalars().all()

    active_connections_count = len(connections)
    total_channels_count = len(channels)

    # Sum total bytes transferred
    total_bytes = sum(c.bytes_transferred for c in connections)

    lines = [
        "# HELP controlbox_streaming_active_connections Current active client video streams",
        "# TYPE controlbox_streaming_active_connections gauge",
        f"controlbox_streaming_active_connections {active_connections_count}",
        "# HELP controlbox_streaming_total_channels Total imported channels count",
        "# TYPE controlbox_streaming_total_channels gauge",
        f"controlbox_streaming_total_channels {total_channels_count}",
        "# HELP controlbox_streaming_bytes_transferred_total Total bytes transferred by active play streams",
        "# TYPE controlbox_streaming_bytes_transferred_total counter",
        f"controlbox_streaming_bytes_transferred_total {total_bytes}"
    ]

    return "\n".join(lines)
