import asyncio
import logging
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import UUID

from controlbox.shared.infrastructure.celery.app import celery_app
from controlbox.modules.identity.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from controlbox.modules.streaming.infrastructure.epg_parser import EpgParser
from controlbox.modules.streaming.domain.entities import EpgProgram, ChannelStatus

logger = logging.getLogger("controlbox.streaming.tasks")


@celery_app.task(name="streaming.check_channels_health")
def check_channels_health() -> None:
    """Checks the health of all active IPTV channels."""
    async def run():
        uow = SqlAlchemyUnitOfWork()
        async with uow:
            channels = await uow.session.execute(
                "SELECT id, tenant_id, name, stream_url, status FROM streaming_channels WHERE is_active = true"
            )
            for row in channels:
                chan_id, tenant_id, name, url, old_status = row
                new_status = ChannelStatus.OFFLINE
                try:
                    # Perform a fast test request to verify stream availability
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "VLC/3.0.18"},
                        method="GET"
                    )
                    # We only read the first few bytes to check if connection succeeds
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        if resp.status in (200, 206, 302):
                            new_status = ChannelStatus.ONLINE
                except Exception:
                    new_status = ChannelStatus.OFFLINE

                if new_status != old_status:
                    await uow.session.execute(
                        "UPDATE streaming_channels SET status = :status, updated_at = now() WHERE id = :id",
                        {"status": new_status, "id": chan_id}
                    )
            await uow.commit()

    asyncio.run(run())


@celery_app.task(name="streaming.sync_epg")
def sync_epg(xmltv_url: str, tenant_id_str: str) -> None:
    """Downloads XMLTV and parses program guides for the tenant."""
    tenant_id = UUID(tenant_id_str)
    
    async def run():
        uow = SqlAlchemyUnitOfWork()
        async with uow:
            try:
                programs = EpgParser.parse_from_url(xmltv_url)
            except Exception as e:
                logger.error(f"Failed to fetch or parse EPG from {xmltv_url}: {e}")
                return

            # Clean programs older than 24 hours
            cutoff = datetime.now(timezone.utc) - timedelta(days=1)
            await uow.session.execute(
                "DELETE FROM streaming_epg WHERE tenant_id = :tenant_id AND end_time < :cutoff",
                {"tenant_id": tenant_id, "cutoff": cutoff}
            )

            # Bulk insert parsed programs
            for p in programs[:5000]:  # Cap at 5000 programs to prevent performance issues
                start_time = p["start_time"]
                end_time = p["end_time"]
                
                # Check duplicate
                dup = await uow.session.execute(
                    "SELECT 1 FROM streaming_epg WHERE tenant_id = :tenant_id "
                    "AND channel_epg_id = :channel_epg_id AND start_time = :start_time AND end_time = :end_time",
                    {
                        "tenant_id": tenant_id,
                        "channel_epg_id": p["channel_epg_id"],
                        "start_time": start_time,
                        "end_time": end_time
                    }
                )
                if dup.scalar_one_or_none():
                    continue

                entity = EpgProgram(
                    tenant_id=tenant_id,
                    channel_epg_id=p["channel_epg_id"],
                    title=p["title"],
                    description=p["description"],
                    start_time=start_time,
                    end_time=end_time
                )
                
                # Convert to DB insert
                await uow.session.execute(
                    "INSERT INTO streaming_epg (id, tenant_id, channel_epg_id, title, description, start_time, end_time) "
                    "VALUES (:id, :tenant_id, :channel_epg_id, :title, :description, :start_time, :end_time)",
                    {
                        "id": entity.id,
                        "tenant_id": entity.tenant_id,
                        "channel_epg_id": entity.channel_epg_id,
                        "title": entity.title,
                        "description": entity.description,
                        "start_time": entity.start_time,
                        "end_time": entity.end_time
                    }
                )
            await uow.commit()

    asyncio.run(run())
