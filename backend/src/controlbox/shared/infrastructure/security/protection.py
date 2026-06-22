import json
import re
import time
from dataclasses import dataclass

from controlbox.shared.infrastructure.redis.client import RedisClient

WAF_PATTERNS = [
    re.compile(r"(?i)(union\s+select|drop\s+table|insert\s+into|delete\s+from|;\s*--)", re.I),
    re.compile(r"(?i)(<script|javascript:|onerror\s*=|onload\s*=)", re.I),
    re.compile(r"\.\./|\.\.\\"),
    re.compile(r"(?i)(/etc/passwd|/proc/self|cmd\.exe|powershell)", re.I),
]


@dataclass
class WafResult:
    blocked: bool
    reason: str | None = None


class WafInspector:
    def inspect(self, path: str, query: str, body: str | None) -> WafResult:
        combined = f"{path}?{query}"
        if body:
            combined += body[:4096]
        for pattern in WAF_PATTERNS:
            if pattern.search(combined):
                return WafResult(blocked=True, reason="suspicious_pattern")
        if len(path) > 2048:
            return WafResult(blocked=True, reason="path_too_long")
        return WafResult(blocked=False)


class RateLimiter:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client.client

    async def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = int(time.time())
        bucket = f"ratelimit:{key}:{now // window_seconds}"
        count = await self._redis.incr(bucket)
        if count == 1:
            await self._redis.expire(bucket, window_seconds + 1)
        remaining = max(0, limit - count)
        return count <= limit, remaining

    async def reset(self, key: str, window_seconds: int) -> None:
        now = int(time.time())
        bucket = f"ratelimit:{key}:{now // window_seconds}"
        await self._redis.delete(bucket)


class IpReputation:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client.client

    async def is_blocked(self, ip: str) -> bool:
        if not ip:
            return False
        return await self._redis.exists(f"blocked_ip:{ip}") > 0

    async def block(self, ip: str, reason: str, ttl_seconds: int = 3600) -> None:
        payload = json.dumps({"reason": reason, "blocked_at": time.time()})
        await self._redis.setex(f"blocked_ip:{ip}", ttl_seconds, payload)

    async def record_failed_login(self, ip: str, email: str) -> int:
        key = f"failed_login:{ip}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 900)
        await self._redis.lpush(
            f"failed_login_log:{ip}",
            json.dumps({"email": email, "ts": time.time()}),
        )
        await self._redis.ltrim(f"failed_login_log:{ip}", 0, 49)
        return count

    async def clear_failed_logins(self, ip: str) -> None:
        await self._redis.delete(f"failed_login:{ip}")

    async def list_blocked_ips(self, limit: int = 100) -> list[dict]:
        keys = []
        async for key in self._redis.scan_iter("blocked_ip:*", count=200):
            keys.append(key)
            if len(keys) >= limit:
                break
        results = []
        for key in keys:
            ip = key.replace("blocked_ip:", "", 1)
            raw = await self._redis.get(key)
            ttl = await self._redis.ttl(key)
            data = json.loads(raw) if raw else {}
            results.append({"ip": ip, "reason": data.get("reason", "unknown"), "ttl_seconds": ttl})
        return results

    async def unblock(self, ip: str) -> None:
        await self._redis.delete(f"blocked_ip:{ip}")
        await self._redis.delete(f"failed_login:{ip}")


class CsrfProtection:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client.client

    async def issue_token(self, session_id: str) -> str:
        import secrets
        token = secrets.token_urlsafe(32)
        await self._redis.setex(f"csrf:{session_id}", 3600, token)
        return token

    async def validate(self, session_id: str, token: str | None) -> bool:
        if not token:
            return False
        stored = await self._redis.get(f"csrf:{session_id}")
        return stored == token
