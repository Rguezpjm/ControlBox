"""HTTP uptime checks and visit counting for hosted sites (Uptime Kuma-style)."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import time
from dataclasses import dataclass
from uuid import UUID

import httpx

from controlbox.config.settings import Settings
from controlbox.modules.monitoring.infrastructure.store import MetricsStore
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env
from controlbox.shared.infrastructure.redis.client import RedisClient
from controlbox.shared.infrastructure.ssl_certificates import SslCertificateService

logger = logging.getLogger("controlbox.site_monitor")

CLOUDFLARE_DOWN_CODES = {403, 520, 521, 522, 523, 524, 525, 526, 530}
UPTIME_HISTORY_LIMIT = 288  # 24h @ 5 min


@dataclass(frozen=True)
class SiteCheckTarget:
    site_type: str  # website | wordpress
    site_id: UUID
    tenant_id: UUID
    domain: str
    ssl_enabled: bool
    container_name: str | None
    monitoring_enabled: bool
    status: str


@dataclass(frozen=True)
class UptimeCheckResult:
    status: str  # up | down
    reason: str | None  # server | cloudflare | domain_expired | ssl | dns
    latency_ms: float
    http_status: int | None


UPTIME_CHECK_INTERVAL_SECONDS = 300  # 5 minutes


class SiteMonitorService:
    def __init__(self, settings: Settings, redis_client: RedisClient) -> None:
        self._settings = settings
        self._store = MetricsStore(redis_client)
        self._ssl = SslCertificateService(settings)

    def _prefix(self, site_type: str, site_id: UUID) -> str:
        return f"{site_type}:{site_id}"

    async def run_checks(self, targets: list[SiteCheckTarget]) -> None:
        for target in targets:
            if not target.monitoring_enabled:
                continue
            if target.status not in ("running", "error", "maintenance"):
                continue
            try:
                await self._check_one(target)
            except Exception as exc:
                logger.warning("Site monitor failed for %s: %s", target.domain, exc)

    async def _check_one(self, target: SiteCheckTarget) -> None:
        if not await self._should_run_check(target):
            return

        visits_delta = await self._count_visits_delta(target)
        if visits_delta > 0:
            await self._store.append_point(
                target.tenant_id,
                f"site:{self._prefix(target.site_type, target.site_id)}:visits",
                float(visits_delta),
            )

        result = await self._http_check(target)
        await self._store.append_uptime_check(
            target.tenant_id,
            self._prefix(target.site_type, target.site_id),
            {
                "status": result.status,
                "reason": result.reason,
                "latency_ms": result.latency_ms,
                "http_status": result.http_status,
            },
        )
        await self._mark_check_run(target)

    async def _should_run_check(self, target: SiteCheckTarget) -> bool:
        key = self._store._key(
            target.tenant_id,
            f"site:{self._prefix(target.site_type, target.site_id)}:last_uptime_check",
        )
        raw = await self._store._redis.get(key)
        if not raw:
            return True
        try:
            last = float(raw)
        except ValueError:
            return True
        return (time.time() - last) >= UPTIME_CHECK_INTERVAL_SECONDS

    async def _mark_check_run(self, target: SiteCheckTarget) -> None:
        key = self._store._key(
            target.tenant_id,
            f"site:{self._prefix(target.site_type, target.site_id)}:last_uptime_check",
        )
        await self._store._redis.setex(key, UPTIME_CHECK_INTERVAL_SECONDS * 2, str(time.time()))

    async def _count_visits_delta(self, target: SiteCheckTarget) -> int:
        if not target.container_name:
            return 0
        count = await asyncio.to_thread(self._read_access_log_lines, target.container_name)
        if count is None:
            return 0

        key = self._store._key(target.tenant_id, f"site:{self._prefix(target.site_type, target.site_id)}:log_lines")
        raw = await self._store._redis.get(key)
        previous = int(raw) if raw else 0
        await self._store._redis.setex(key, 86400 * 7, str(count))
        delta = count - previous if count >= previous else count
        return max(0, delta)

    def _read_access_log_lines(self, container_name: str) -> int | None:
        paths = (
            "/var/log/nginx/access.log",
            "/logs/access.log",
            "/var/log/apache2/access.log",
        )
        for path in paths:
            proc = __import__("subprocess").run(
                ["docker", "exec", container_name, "sh", "-c", f"wc -l < {path} 2>/dev/null"],
                capture_output=True,
                text=True,
                timeout=10,
                env=docker_subprocess_env(self._settings),
            )
            if proc.returncode == 0:
                match = re.search(r"(\d+)", proc.stdout.strip())
                if match:
                    return int(match.group(1))
        return None

    async def _http_check(self, target: SiteCheckTarget) -> UptimeCheckResult:
        if target.ssl_enabled:
            days = self._ssl.days_remaining(target.domain)
            if days is not None and days <= 0:
                return UptimeCheckResult("down", "domain_expired", 0.0, None)

        if not self._dns_resolves(target.domain):
            return UptimeCheckResult("down", "dns", 0.0, None)

        scheme = "https" if target.ssl_enabled else "http"
        url = f"{scheme}://{target.domain}/"
        start = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
                verify=True,
            ) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "ControlBox-Uptime/1.0"},
                )
        except httpx.ConnectError:
            return UptimeCheckResult("down", "server", 0.0, None)
        except httpx.TimeoutException:
            return UptimeCheckResult("down", "server", 0.0, None)
        except httpx.HTTPError as exc:
            msg = str(exc).lower()
            if "certificate" in msg or "ssl" in msg:
                return UptimeCheckResult("down", "ssl", 0.0, None)
            return UptimeCheckResult("down", "server", 0.0, None)

        latency = round((time.perf_counter() - start) * 1000, 1)
        headers = {k.lower(): v.lower() for k, v in response.headers.items()}
        is_cf = "cloudflare" in headers.get("server", "") or "cf-ray" in headers

        if is_cf and (response.status_code in CLOUDFLARE_DOWN_CODES or response.status_code >= 500):
            return UptimeCheckResult("down", "cloudflare", latency, response.status_code)

        if response.status_code >= 500:
            return UptimeCheckResult("down", "server", latency, response.status_code)

        if response.status_code >= 400:
            if is_cf:
                return UptimeCheckResult("down", "cloudflare", latency, response.status_code)
            return UptimeCheckResult("down", "server", latency, response.status_code)

        if response.status_code >= 200 and response.status_code < 400:
            return UptimeCheckResult("up", None, latency, response.status_code)

        return UptimeCheckResult("down", "server", latency, response.status_code)

    def _dns_resolves(self, domain: str) -> bool:
        try:
            socket.getaddrinfo(domain, None)
            return True
        except socket.gaierror:
            return False
