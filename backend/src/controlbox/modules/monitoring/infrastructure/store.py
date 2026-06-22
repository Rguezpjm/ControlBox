import json
from datetime import datetime, timezone
from uuid import UUID

from controlbox.modules.monitoring.domain.entities import MetricPoint, MonitoringSnapshot
from controlbox.shared.infrastructure.redis.client import RedisClient

HISTORY_LIMIT = 120
HISTORY_TTL = 3600
UPTIME_TTL = 86400 * 7
UPTIME_LIMIT = 288


class MetricsStore:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client.client

    def _key(self, tenant_id: UUID | None, metric: str) -> str:
        tenant = str(tenant_id) if tenant_id else "global"
        return f"monitoring:{tenant}:{metric}"

    async def append_point(self, tenant_id: UUID | None, metric: str, value: float, ts: datetime | None = None) -> None:
        point = {
            "timestamp": (ts or datetime.now(timezone.utc)).isoformat(),
            "value": value,
        }
        key = self._key(tenant_id, metric)
        pipe = self._redis.pipeline()
        pipe.lpush(key, json.dumps(point))
        pipe.ltrim(key, 0, HISTORY_LIMIT - 1)
        pipe.expire(key, HISTORY_TTL)
        await pipe.execute()

    async def append_snapshot(self, tenant_id: UUID | None, snapshot: MonitoringSnapshot) -> None:
        host = snapshot.host
        await self.append_point(tenant_id, "cpu", host.cpu_percent, snapshot.collected_at)
        await self.append_point(tenant_id, "memory", host.memory_percent, snapshot.collected_at)
        await self.append_point(tenant_id, "disk", host.disk_percent, snapshot.collected_at)
        await self.append_point(tenant_id, "network_in", host.network_in_mbps, snapshot.collected_at)
        await self.append_point(tenant_id, "network_out", host.network_out_mbps, snapshot.collected_at)

        key = self._key(tenant_id, "snapshot")
        payload = self._serialize_snapshot(snapshot)
        pipe = self._redis.pipeline()
        pipe.setex(key, HISTORY_TTL, json.dumps(payload))
        await pipe.execute()

    async def get_history(self, tenant_id: UUID | None, metric: str, limit: int = 60) -> list[MetricPoint]:
        key = self._key(tenant_id, metric)
        raw_items = await self._redis.lrange(key, 0, limit - 1)
        points: list[MetricPoint] = []
        for item in reversed(raw_items):
            data = json.loads(item)
            points.append(
                MetricPoint(
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    value=float(data["value"]),
                )
            )
        return points

    async def append_uptime_check(
        self,
        tenant_id: UUID | None,
        site_key: str,
        payload: dict,
    ) -> None:
        point = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        key = self._key(tenant_id, f"site:{site_key}:uptime")
        pipe = self._redis.pipeline()
        pipe.lpush(key, json.dumps(point))
        pipe.ltrim(key, 0, UPTIME_LIMIT - 1)
        pipe.expire(key, UPTIME_TTL)
        await pipe.execute()

    async def get_uptime_timeline(
        self,
        tenant_id: UUID | None,
        site_key: str,
        limit: int = UPTIME_LIMIT,
    ) -> list[dict]:
        key = self._key(tenant_id, f"site:{site_key}:uptime")
        raw_items = await self._redis.lrange(key, 0, limit - 1)
        items: list[dict] = []
        for item in reversed(raw_items):
            items.append(json.loads(item))
        return items

    async def get_snapshot(self, tenant_id: UUID | None) -> dict | None:
        key = self._key(tenant_id, "snapshot")
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    def _serialize_snapshot(self, snapshot: MonitoringSnapshot) -> dict:
        return {
            "host": snapshot.host.__dict__,
            "docker": [c.__dict__ for c in snapshot.docker],
            "databases": [d.__dict__ for d in snapshot.databases],
            "supabase": [s.__dict__ for s in snapshot.supabase],
            "websites": [w.__dict__ for w in snapshot.websites],
            "services": [s.__dict__ for s in snapshot.services],
            "collected_at": snapshot.collected_at.isoformat() if snapshot.collected_at else None,
        }
