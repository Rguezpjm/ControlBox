import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.identity.infrastructure.unit_of_work import Database
from controlbox.modules.monitoring.domain.entities import MonitoringSnapshot, ServiceHealth
from controlbox.modules.monitoring.infrastructure.broadcaster import MonitoringBroadcaster
from controlbox.modules.monitoring.infrastructure.collectors import HostMetricsCollector, TenantMetricsCollector
from controlbox.modules.monitoring.infrastructure.store import MetricsStore
from controlbox.modules.platform.application.alert_evaluator import ResourceAlertEvaluator
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env
from controlbox.shared.infrastructure.redis.client import RedisClient
from controlbox.shared.infrastructure.redis.leader_lock import LeaderLock
from controlbox.shared.infrastructure.site_monitor import SiteCheckTarget, SiteMonitorService

logger = logging.getLogger("controlbox.monitoring")

__all__ = ["MonitoringBroadcaster", "MonitoringCollectorTask"]


class MonitoringCollectorTask:
    def __init__(
        self,
        database: Database,
        redis_client: RedisClient,
        settings: Settings,
        broadcaster: MonitoringBroadcaster,
    ) -> None:
        self._database = database
        self._store = MetricsStore(redis_client)
        self._redis = redis_client
        self._settings = settings
        self._broadcaster = broadcaster
        self._host = HostMetricsCollector(settings)
        self._tenant = TenantMetricsCollector(settings)
        self._running = False
        self._lock = LeaderLock(redis_client, "monitoring_collector", ttl_seconds=30)
        self._alert_evaluator = ResourceAlertEvaluator(broadcaster, settings)
        self._last_site_traffic: dict[str, tuple[float, float]] = {}
        self._site_monitor = SiteMonitorService(settings, redis_client)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        if not self._settings.background_tasks_enabled:
            return
        self._running = True
        while self._running:
            try:
                if await self._lock.acquire():
                    await self._collect_cycle()
                    await self._lock.renew()
            except Exception as exc:
                logger.exception("Monitoring collection failed: %s", exc)
            await asyncio.sleep(self._settings.monitoring_interval_seconds)

    async def collect_for_tenant(self, tenant_id: UUID) -> MonitoringSnapshot:
        host = await self._host.collect()
        services = await self._check_services()

        async with self._database.unit_of_work() as uow:
            databases, supabase, websites, docker = await self._tenant.collect(uow, tenant_id)
            site_entities = await uow.websites.list_by_tenant(tenant_id)
            wp_entities = await uow.wordpress_sites.list_by_tenant(tenant_id, 500, 0)

        docker_by_name = {c.name: c for c in docker}
        now = time.time()
        monitor_targets: list[SiteCheckTarget] = []

        for site in site_entities:
            container = site.container_name or ""
            if container in docker_by_name:
                stat = docker_by_name[container]
                await self._record_site_traffic(
                    tenant_id, "website", site.id, stat.network_in_mb + stat.network_out_mb, now
                )
            monitor_targets.append(
                SiteCheckTarget(
                    site_type="website",
                    site_id=site.id,
                    tenant_id=tenant_id,
                    domain=site.domain,
                    ssl_enabled=site.ssl_enabled,
                    container_name=site.container_name,
                    monitoring_enabled=site.monitoring_enabled,
                    status=site.status.value,
                )
            )

        for wp in wp_entities:
            container = wp.nginx_container_name or wp.php_container_name or ""
            if container in docker_by_name:
                stat = docker_by_name[container]
                await self._record_site_traffic(
                    tenant_id, "wordpress", wp.id, stat.network_in_mb + stat.network_out_mb, now
                )
            monitor_targets.append(
                SiteCheckTarget(
                    site_type="wordpress",
                    site_id=wp.id,
                    tenant_id=tenant_id,
                    domain=wp.domain,
                    ssl_enabled=wp.ssl_enabled,
                    container_name=wp.nginx_container_name or wp.php_container_name,
                    monitoring_enabled=True,
                    status=wp.status.value,
                )
            )

        await self._site_monitor.run_checks(monitor_targets)

        snapshot = MonitoringSnapshot(
            host=host,
            docker=docker,
            databases=databases,
            supabase=supabase,
            websites=websites,
            services=services,
            collected_at=datetime.now(timezone.utc),
        )
        await self._store.append_snapshot(tenant_id, snapshot)
        return snapshot

    async def _record_site_traffic(
        self,
        tenant_id: UUID,
        site_type: str,
        site_id: UUID,
        total_mb: float,
        now: float,
    ) -> None:
        key = f"{tenant_id}:{site_type}:{site_id}"
        rate_mbps = 0.0
        previous = self._last_site_traffic.get(key)
        if previous is not None:
            prev_total, prev_ts = previous
            dt = max(now - prev_ts, 0.001)
            delta_mb = total_mb - prev_total
            if delta_mb >= 0:
                rate_mbps = (delta_mb * 8) / dt
        self._last_site_traffic[key] = (total_mb, now)
        await self._store.append_point(
            tenant_id,
            f"site:{site_type}:{site_id}:traffic_mbps",
            round(rate_mbps, 3),
        )

    async def _collect_cycle(self) -> None:
        tenant_ids = await self._list_active_tenant_ids()
        if not tenant_ids:
            host = await self._host.collect()
            services = await self._check_services()
            snapshot = MonitoringSnapshot(host=host, services=services, collected_at=datetime.now(timezone.utc))
            await self._store.append_snapshot(None, snapshot)
            return

        for tenant_id in tenant_ids:
            snapshot = await self.collect_for_tenant(tenant_id)
            async with self._database.unit_of_work() as uow:
                alerts = await self._alert_evaluator.evaluate(uow, tenant_id, snapshot)
                if alerts:
                    await uow.commit()
            if tenant_id in self._broadcaster.active_tenants():
                await self._broadcaster.broadcast(tenant_id, self._store._serialize_snapshot(snapshot))

    async def _list_active_tenant_ids(self) -> set[UUID]:
        async with self._database.unit_of_work() as uow:
            ids = await uow.tenants.list_active_ids()
            return set(ids)

    async def _check_services(self) -> list[ServiceHealth]:
        results: list[ServiceHealth] = []
        checks = [
            ("PostgreSQL", self._ping_postgres),
            ("Redis", self._ping_redis),
            ("Docker", self._ping_docker),
        ]
        for name, checker in checks:
            start = time.perf_counter()
            try:
                ok = await checker()
                latency = round((time.perf_counter() - start) * 1000, 1)
                results.append(ServiceHealth(name=name, status="healthy" if ok else "unhealthy", latency_ms=latency))
            except Exception:
                results.append(ServiceHealth(name=name, status="unhealthy"))
        return results

    async def _ping_postgres(self) -> bool:
        return await self._database.health_check()

    async def _ping_redis(self) -> bool:
        return await self._redis.ping()

    async def _ping_docker(self) -> bool:
        if not self._settings.monitoring_use_docker:
            return True
        proc = await asyncio.create_subprocess_exec(
            "docker", "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=docker_subprocess_env(self._settings),
        )
        await proc.wait()
        return proc.returncode == 0
