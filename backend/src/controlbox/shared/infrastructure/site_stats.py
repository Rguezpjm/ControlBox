"""Enrich site list responses with SSL expiry and traffic stats."""

from __future__ import annotations

from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.monitoring.infrastructure.store import MetricsStore
from controlbox.shared.infrastructure.redis.client import RedisClient
from controlbox.shared.infrastructure.ssl_certificates import SslCertificateService


async def get_site_traffic_stats(
    redis_client: RedisClient,
    tenant_id: UUID,
    site_id: UUID,
    limit: int = 24,
) -> tuple[int, list[float]]:
    store = MetricsStore(redis_client)
    history = await store.get_history(tenant_id, f"site:{site_id}:traffic", limit)
    sparkline = [round(p.value, 1) for p in history]
    if not sparkline:
        return 0, []
    latest = sparkline[-1]
    requests = max(0, int(latest * 10))
    return requests, sparkline


def get_ssl_days_remaining(settings: Settings, domain: str, ssl_enabled: bool, ssl_status: str) -> int | None:
    if not ssl_enabled:
        return None
    if ssl_status not in ("active", "pending"):
        return None
    service = SslCertificateService(settings)
    days = service.days_remaining(domain)
    if days is not None:
        return days
    if ssl_status == "active":
        return 90
    return None
