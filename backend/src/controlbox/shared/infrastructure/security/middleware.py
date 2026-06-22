import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from controlbox.config.settings import get_settings
from controlbox.shared.infrastructure.security.protection import IpReputation, RateLimiter, WafInspector

logger = logging.getLogger("controlbox.security")


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._settings = get_settings()
        self._waf = WafInspector()

    def _redis_services(self, request: Request) -> tuple[RateLimiter, IpReputation] | None:
        container = getattr(request.app.state, "container", None)
        if container is None:
            return None
        redis = container.redis_client
        return RateLimiter(redis), IpReputation(redis)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        services = self._redis_services(request)
        if self._settings.security_enabled and services:
            rate_limiter, ip_reputation = services
            client_ip = _client_ip(request, self._settings)
            if client_ip and await ip_reputation.is_blocked(client_ip):
                return _blocked_response("IP blocked due to security policy", request_id)

            if self._settings.security_waf_enabled:
                body_preview = ""
                if request.method in ("POST", "PUT", "PATCH"):
                    body_bytes = await request.body()

                    async def receive():
                        return {"type": "http.request", "body": body_bytes, "more_body": False}

                    request._receive = receive
                    body_preview = body_bytes[:4096].decode("utf-8", errors="ignore")
                waf_result = self._waf.inspect(request.url.path, str(request.url.query), body_preview)
                if waf_result.blocked:
                    logger.warning("WAF blocked %s from %s: %s", request.url.path, client_ip, waf_result.reason)
                    if client_ip:
                        await ip_reputation.block(client_ip, f"waf:{waf_result.reason}", 1800)
                    return _blocked_response("Request blocked by WAF", request_id)

            limit, window = self._rate_config(request.url.path)
            if client_ip and limit > 0:
                allowed, _ = await rate_limiter.check(f"{client_ip}:{request.url.path}", limit, window)
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Rate limit exceeded", "code": "rate_limit"},
                        headers={
                            "X-Request-Id": request_id,
                            "Retry-After": str(window),
                            "X-RateLimit-Remaining": "0",
                        },
                    )
            global_limit = self._settings.security_rate_limit_global
            if client_ip and global_limit > 0:
                allowed, _ = await rate_limiter.check(f"global:{client_ip}", global_limit, 60)
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Global rate limit exceeded", "code": "rate_limit"},
                        headers={"X-Request-Id": request_id, "Retry-After": "60"},
                    )

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if self._settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        if self._settings.security_csp:
            response.headers["Content-Security-Policy"] = self._settings.security_csp
        return response

    def _rate_config(self, path: str) -> tuple[int, int]:
        if "/auth/login" in path or "/webauthn" in path:
            return self._settings.security_rate_limit_login, 60
        if path.startswith("/api/"):
            return self._settings.security_rate_limit_api, 60
        return 0, 60


def _client_ip(request: Request, settings) -> str | None:
    if settings.security_trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _blocked_response(message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": message, "code": "forbidden"},
        headers={"X-Request-Id": request_id},
    )
