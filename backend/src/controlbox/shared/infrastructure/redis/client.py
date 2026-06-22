import json
from datetime import timedelta
from uuid import UUID

import redis.asyncio as redis

from controlbox.config.settings import Settings
from controlbox.shared.domain.base import utc_now


class RedisClient:
    def __init__(self, settings: Settings) -> None:
        self._client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )

    @property
    def client(self) -> redis.Redis:
        return self._client

    async def ping(self) -> bool:
        return await self._client.ping()

    async def close(self) -> None:
        await self._client.aclose()


class SessionCache:
    def __init__(self, redis_client: RedisClient, settings: Settings) -> None:
        self._redis = redis_client.client
        self._settings = settings
        self._prefix = "session:"
        self._blacklist_prefix = "token_blacklist:"

    def _session_key(self, session_id: UUID) -> str:
        return f"{self._prefix}{session_id}"

    async def store_session(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID | None,
        ttl_seconds: int,
    ) -> None:
        payload = {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id) if tenant_id else None,
            "active": True,
            "created_at": utc_now().isoformat(),
        }
        await self._redis.setex(self._session_key(session_id), ttl_seconds, json.dumps(payload))

    async def is_session_active(self, session_id: UUID) -> bool:
        data = await self._redis.get(self._session_key(session_id))
        if not data:
            return False
        parsed = json.loads(data)
        return parsed.get("active", False)

    async def revoke_session(self, session_id: UUID) -> None:
        data = await self._redis.get(self._session_key(session_id))
        if data:
            parsed = json.loads(data)
            parsed["active"] = False
            await self._redis.setex(self._session_key(session_id), 60, json.dumps(parsed))
        await self._redis.delete(self._session_key(session_id))

    async def blacklist_access_token(self, jti: str, expires_in_seconds: int) -> None:
        await self._redis.setex(f"{self._blacklist_prefix}{jti}", expires_in_seconds, "1")

    async def is_access_token_blacklisted(self, jti: str) -> bool:
        return await self._redis.exists(f"{self._blacklist_prefix}{jti}") > 0

    def refresh_ttl_seconds(self) -> int:
        return int(timedelta(days=self._settings.jwt_refresh_token_expire_days).total_seconds())
