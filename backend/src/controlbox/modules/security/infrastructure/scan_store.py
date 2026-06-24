"""Redis-backed storage for vulnerability web scans.

Scans are transient operational data (not domain state), so we keep them in
Redis with a TTL instead of adding a new SQL table/migration. Provides an async
store for the API and a sync store for the Celery worker.
"""

from __future__ import annotations

import json
from typing import Any

import redis
import redis.asyncio as aioredis

from controlbox.config.settings import Settings

SCAN_TTL_SECONDS = 7 * 24 * 3600
INDEX_MAX = 50


def _item_key(tenant_id: str, scan_id: str) -> str:
    return f"vulnscan:item:{tenant_id}:{scan_id}"


def _index_key(tenant_id: str) -> str:
    return f"vulnscan:index:{tenant_id}"


class ScanStore:
    """Async store used by the API (FastAPI)."""

    def __init__(self, settings: Settings) -> None:
        self._r = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def save(self, tenant_id: str, scan: dict[str, Any]) -> None:
        scan_id = scan["id"]
        await self._r.setex(_item_key(tenant_id, scan_id), SCAN_TTL_SECONDS, json.dumps(scan))

    async def add_to_index(self, tenant_id: str, scan_id: str) -> None:
        key = _index_key(tenant_id)
        await self._r.lrem(key, 0, scan_id)
        await self._r.lpush(key, scan_id)
        await self._r.ltrim(key, 0, INDEX_MAX - 1)
        await self._r.expire(key, SCAN_TTL_SECONDS)

    async def get(self, tenant_id: str, scan_id: str) -> dict[str, Any] | None:
        raw = await self._r.get(_item_key(tenant_id, scan_id))
        return json.loads(raw) if raw else None

    async def list(self, tenant_id: str) -> list[dict[str, Any]]:
        ids = await self._r.lrange(_index_key(tenant_id), 0, INDEX_MAX - 1)
        out: list[dict[str, Any]] = []
        for scan_id in ids:
            raw = await self._r.get(_item_key(tenant_id, scan_id))
            if raw:
                out.append(json.loads(raw))
        return out

    async def close(self) -> None:
        await self._r.aclose()


class SyncScanStore:
    """Sync store used by the Celery worker."""

    def __init__(self, settings: Settings) -> None:
        self._r = redis.from_url(settings.redis_url, decode_responses=True)

    def get(self, tenant_id: str, scan_id: str) -> dict[str, Any] | None:
        raw = self._r.get(_item_key(tenant_id, scan_id))
        return json.loads(raw) if raw else None

    def save(self, tenant_id: str, scan: dict[str, Any]) -> None:
        self._r.setex(_item_key(tenant_id, scan["id"]), SCAN_TTL_SECONDS, json.dumps(scan))
