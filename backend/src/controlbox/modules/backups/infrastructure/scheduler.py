import asyncio
import logging
from datetime import datetime, timezone

from controlbox.config.settings import Settings
from controlbox.modules.backups.domain.entities import BackupTriggerType
from controlbox.modules.backups.infrastructure.engine import BackupEngine, compute_next_run
from controlbox.modules.identity.infrastructure.unit_of_work import Database
from controlbox.shared.infrastructure.redis.client import RedisClient
from controlbox.shared.infrastructure.redis.leader_lock import LeaderLock

logger = logging.getLogger("controlbox.backups")


class BackupScheduler:
    def __init__(self, database: Database, settings: Settings, redis_client: RedisClient | None = None) -> None:
        self._database = database
        self._settings = settings
        self._redis = redis_client
        self._running = False
        self._lock: LeaderLock | None = None

    async def run(self) -> None:
        if not self._settings.background_tasks_enabled:
            return
        self._running = True
        if self._redis:
            self._lock = LeaderLock(self._redis, "backup_scheduler", ttl_seconds=55)
        while self._running:
            try:
                if self._lock and not await self._lock.acquire():
                    await asyncio.sleep(60)
                    continue
                await self._process_due_schedules()
                if self._lock:
                    await self._lock.renew()
            except Exception as exc:
                logger.exception("Backup scheduler error: %s", exc)
            await asyncio.sleep(60)

    def stop(self) -> None:
        self._running = False

    async def _process_due_schedules(self) -> None:
        now = datetime.now(timezone.utc)
        uow = self._database.unit_of_work()

        async with uow:
            schedules = await uow.backup_schedules.list_due(now)
            if not schedules:
                return

            for schedule in schedules:
                destination = await uow.backup_destinations.get_by_id(schedule.destination_id)
                if not destination or not destination.is_active:
                    schedule.pause()
                    await uow.backup_schedules.save(schedule)
                    continue

                engine = BackupEngine(uow, self._settings)
                try:
                    await engine.run_backup(
                        tenant_id=schedule.tenant_id,
                        destination=destination,
                        source_type=schedule.source_type,
                        resource_id=schedule.resource_id,
                        name=f"{schedule.name}-{now.strftime('%Y%m%d%H%M')}",
                        trigger_type=BackupTriggerType.SCHEDULED,
                        schedule=schedule,
                        max_versions=schedule.max_versions,
                        retention_days=schedule.retention_days,
                    )
                except Exception as exc:
                    logger.error("Scheduled backup failed %s: %s", schedule.id, exc)

                schedule.mark_run(compute_next_run(schedule.cron_expression, now))
                await uow.backup_schedules.save(schedule)

            await uow.commit()
