import os
import uuid

from controlbox.shared.infrastructure.redis.client import RedisClient


class LeaderLock:
    def __init__(self, redis_client: RedisClient, key: str, ttl_seconds: int = 55) -> None:
        self._redis = redis_client.client
        self._key = f"leader:{key}"
        self._ttl = ttl_seconds
        self._token = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"

    async def acquire(self) -> bool:
        return await self._redis.set(self._key, self._token, nx=True, ex=self._ttl)

    async def renew(self) -> bool:
        current = await self._redis.get(self._key)
        if current != self._token:
            return False
        await self._redis.expire(self._key, self._ttl)
        return True

    async def release(self) -> None:
        current = await self._redis.get(self._key)
        if current == self._token:
            await self._redis.delete(self._key)
