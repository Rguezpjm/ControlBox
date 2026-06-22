"""Cloudflare API v4 client."""

from __future__ import annotations

import logging
import secrets
from typing import Any

import httpx

logger = logging.getLogger("controlbox.cloudflare")

CF_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, errors: list | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []


class CloudflareClient:
    def __init__(self, api_token: str, account_id: str | None = None) -> None:
        self._token = api_token.strip()
        self._account_id = (account_id or "").strip() or None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        url = f"{CF_BASE}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                params=params,
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise CloudflareApiError(
                f"Invalid Cloudflare response ({response.status_code})",
                status_code=response.status_code,
            ) from exc

        if not payload.get("success"):
            errors = payload.get("errors") or []
            message = "; ".join(
                str(item.get("message", item)) for item in errors
            ) or f"Cloudflare API error ({response.status_code})"
            raise CloudflareApiError(message, status_code=response.status_code, errors=errors)
        return payload.get("result")

    async def verify_token(self) -> dict[str, Any]:
        return await self._request("GET", "/user/tokens/verify")

    async def resolve_account_id(self) -> str:
        if self._account_id:
            return self._account_id
        accounts = await self._request("GET", "/accounts", params={"per_page": 50})
        if not accounts:
            raise CloudflareApiError("No Cloudflare accounts found for this token")
        account_id = str(accounts[0]["id"])
        self._account_id = account_id
        return account_id

    async def list_zones(self, *, page: int = 1, per_page: int = 50) -> list[dict[str, Any]]:
        result = await self._request(
            "GET",
            "/zones",
            params={"page": page, "per_page": per_page, "order": "name", "direction": "asc"},
        )
        return result or []

    async def get_security_level(self, zone_id: str) -> str:
        result = await self._request("GET", f"/zones/{zone_id}/settings/security_level")
        if isinstance(result, dict):
            return str(result.get("value", "medium"))
        return "medium"

    async def get_zone(self, zone_id: str) -> dict[str, Any]:
        zone = await self._request("GET", f"/zones/{zone_id}")
        if isinstance(zone, dict):
            try:
                zone["security_level"] = await self.get_security_level(zone_id)
            except CloudflareApiError:
                zone.setdefault("security_level", "medium")
        return zone

    async def create_zone(self, name: str, account_id: str | None = None) -> dict[str, Any]:
        acct = account_id or await self.resolve_account_id()
        return await self._request(
            "POST",
            "/zones",
            json={"name": name.strip().lower(), "account": {"id": acct}, "type": "full", "jump_start": False},
        )

    async def set_zone_paused(self, zone_id: str, paused: bool) -> dict[str, Any]:
        return await self._request("PATCH", f"/zones/{zone_id}", json={"paused": paused})

    async def set_security_level(self, zone_id: str, level: str) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/zones/{zone_id}/settings/security_level",
            json={"value": level},
        )

    async def delete_zone(self, zone_id: str) -> None:
        await self._request("DELETE", f"/zones/{zone_id}")

    async def list_dns_records(self, zone_id: str, *, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        result = await self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"page": page, "per_page": per_page},
        )
        return result or []

    async def create_dns_record(
        self,
        zone_id: str,
        *,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool | None = None,
        priority: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": record_type.upper(),
            "name": name,
            "content": content,
            "ttl": ttl,
        }
        if proxied is not None:
            body["proxied"] = proxied
        if priority is not None:
            body["priority"] = priority
        return await self._request("POST", f"/zones/{zone_id}/dns_records", json=body)

    async def update_dns_record(
        self,
        zone_id: str,
        record_id: str,
        *,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool | None = None,
        priority: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": record_type.upper(),
            "name": name,
            "content": content,
            "ttl": ttl,
        }
        if proxied is not None:
            body["proxied"] = proxied
        if priority is not None:
            body["priority"] = priority
        return await self._request("PATCH", f"/zones/{zone_id}/dns_records/{record_id}", json=body)

    async def delete_dns_record(self, zone_id: str, record_id: str) -> None:
        await self._request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")

    async def create_tunnel(self, name: str, account_id: str | None = None) -> dict[str, Any]:
        acct = account_id or await self.resolve_account_id()
        secret = secrets.token_urlsafe(32)
        return await self._request(
            "POST",
            f"/accounts/{acct}/cfd_tunnel",
            json={"name": name, "tunnel_secret": secret, "config_src": "cloudflare"},
        )

    async def get_tunnel_token(self, tunnel_id: str, account_id: str | None = None) -> str:
        acct = account_id or await self.resolve_account_id()
        result = await self._request(
            "POST",
            f"/accounts/{acct}/cfd_tunnel/{tunnel_id}/token",
        )
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and result.get("token"):
            return str(result["token"])
        raise CloudflareApiError("Could not obtain Cloudflare Tunnel token")

    async def configure_tunnel_ingress(
        self,
        tunnel_id: str,
        hostname: str,
        service_url: str,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        acct = account_id or await self.resolve_account_id()
        config = {
            "config": {
                "ingress": [
                    {"hostname": hostname, "service": service_url},
                    {"service": "http_status:404"},
                ]
            }
        }
        return await self._request(
            "PUT",
            f"/accounts/{acct}/cfd_tunnel/{tunnel_id}/configurations",
            json=config,
        )

    async def delete_tunnel(self, tunnel_id: str, account_id: str | None = None) -> None:
        acct = account_id or await self.resolve_account_id()
        await self._request("DELETE", f"/accounts/{acct}/cfd_tunnel/{tunnel_id}")
