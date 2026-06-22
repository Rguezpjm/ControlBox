"""Enrich site list responses with SSL, traffic, visits and uptime timeline."""

from __future__ import annotations

from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.monitoring.infrastructure.store import MetricsStore
from controlbox.shared.infrastructure.redis.client import RedisClient
from controlbox.shared.infrastructure.ssl_certificates import SslCertificateService

TRAFFIC_METRIC_SUFFIX = ":traffic_mbps"
VISITS_METRIC_SUFFIX = ":visits"

REASON_LABELS = {
    "server": "Servidor / contenedor",
    "cloudflare": "Cloudflare / CDN",
    "domain_expired": "Dominio o SSL vencido",
    "ssl": "Certificado SSL inválido",
    "dns": "DNS no resuelve",
}


async def get_site_traffic_stats(
    redis_client: RedisClient,
    tenant_id: UUID,
    site_id: UUID,
    site_type: str = "website",
    limit: int = 24,
) -> tuple[float, list[float]]:
    store = MetricsStore(redis_client)
    prefix = f"{site_type}:{site_id}"
    history = await store.get_history(tenant_id, f"site:{prefix}{TRAFFIC_METRIC_SUFFIX}", limit)
    if not history:
        history = await store.get_history(tenant_id, f"site:{site_id}{TRAFFIC_METRIC_SUFFIX}", limit)
    sparkline = [round(p.value, 2) for p in history]
    latest = sparkline[-1] if sparkline else 0.0
    return latest, sparkline


async def get_site_visit_stats(
    redis_client: RedisClient,
    tenant_id: UUID,
    site_id: UUID,
    site_type: str = "website",
    limit: int = 24,
) -> tuple[int, list[float]]:
    store = MetricsStore(redis_client)
    prefix = f"{site_type}:{site_id}"
    history = await store.get_history(tenant_id, f"site:{prefix}{VISITS_METRIC_SUFFIX}", limit)
    sparkline = [round(p.value, 1) for p in history]
    total = int(sum(sparkline))
    return total, sparkline


async def get_site_uptime_stats(
    redis_client: RedisClient,
    tenant_id: UUID,
    site_id: UUID,
    site_type: str = "website",
    limit: int = 288,
) -> dict:
    store = MetricsStore(redis_client)
    prefix = f"{site_type}:{site_id}"
    timeline = await store.get_uptime_timeline(tenant_id, prefix, limit)

    if not timeline:
        return {
            "uptime_timeline": [],
            "uptime_percent": 100.0,
            "last_down_reason": None,
            "last_down_reason_label": None,
            "is_up": True,
        }

    up_count = sum(1 for t in timeline if t.get("status") == "up")
    uptime_percent = round((up_count / len(timeline)) * 100, 1)

    last_down = None
    for entry in reversed(timeline):
        if entry.get("status") != "up":
            last_down = entry
            break

    reason = last_down.get("reason") if last_down else None
    return {
        "uptime_timeline": timeline,
        "uptime_percent": uptime_percent,
        "last_down_reason": reason,
        "last_down_reason_label": REASON_LABELS.get(reason or "", reason),
        "is_up": timeline[-1].get("status") == "up" if timeline else True,
    }


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


async def enrich_site_monitoring_fields(
    redis_client: RedisClient,
    tenant_id: UUID,
    site_id: UUID,
    site_type: str,
) -> dict:
    traffic_mbps, traffic_sparkline = await get_site_traffic_stats(
        redis_client, tenant_id, site_id, site_type
    )
    visit_count, visits_sparkline = await get_site_visit_stats(
        redis_client, tenant_id, site_id, site_type
    )
    uptime = await get_site_uptime_stats(redis_client, tenant_id, site_id, site_type)
    return {
        "traffic_mbps": traffic_mbps,
        "traffic_sparkline": traffic_sparkline,
        "visit_count": visit_count,
        "visits_sparkline": visits_sparkline,
        **uptime,
    }
