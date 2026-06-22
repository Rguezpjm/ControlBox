"""Cloudflare credentials and settings helpers."""

from __future__ import annotations

from controlbox.config.settings import Settings
from controlbox.modules.cloudflare.infrastructure.cloudflare_client import CloudflareApiError, CloudflareClient
from controlbox.modules.platform.domain.entities import TenantPlatformSettings
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor


class CloudflareSettingsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._encryptor = SecretEncryptor(settings)

    def build_settings_view(self, platform: TenantPlatformSettings) -> dict:
        return {
            "enabled": platform.cloudflare_enabled,
            "configured": bool(platform.cloudflare_api_token_enc),
            "account_id": platform.cloudflare_account_id or "",
            "tunnel_enabled": platform.cloudflare_tunnel_enabled,
            "tunnel_id": platform.cloudflare_tunnel_id or "",
            "tunnel_hostname": platform.cloudflare_tunnel_hostname or "",
            "tunnel_running": platform.cloudflare_tunnel_enabled and bool(platform.cloudflare_tunnel_token_enc),
        }

    def apply_settings(
        self,
        platform: TenantPlatformSettings,
        *,
        enabled: bool | None = None,
        api_token: str | None = None,
        account_id: str | None = None,
        tunnel_enabled: bool | None = None,
        tunnel_hostname: str | None = None,
    ) -> None:
        if enabled is not None:
            platform.cloudflare_enabled = enabled
        if account_id is not None:
            platform.cloudflare_account_id = account_id.strip()[:64] or None
        if api_token:
            platform.cloudflare_api_token_enc = self._encryptor.encrypt(api_token.strip())
            platform.cloudflare_enabled = True
        if tunnel_enabled is not None:
            platform.cloudflare_tunnel_enabled = tunnel_enabled
        if tunnel_hostname is not None:
            platform.cloudflare_tunnel_hostname = tunnel_hostname.strip()[:255] or None

    def get_api_token(self, platform: TenantPlatformSettings) -> str | None:
        if not platform.cloudflare_api_token_enc:
            return None
        return self._encryptor.decrypt(platform.cloudflare_api_token_enc)

    def get_tunnel_token(self, platform: TenantPlatformSettings) -> str | None:
        if not platform.cloudflare_tunnel_token_enc:
            return None
        return self._encryptor.decrypt(platform.cloudflare_tunnel_token_enc)

    def store_tunnel_credentials(
        self,
        platform: TenantPlatformSettings,
        *,
        tunnel_id: str,
        tunnel_token: str,
    ) -> None:
        platform.cloudflare_tunnel_id = tunnel_id
        platform.cloudflare_tunnel_token_enc = self._encryptor.encrypt(tunnel_token)

    def clear_tunnel(self, platform: TenantPlatformSettings) -> None:
        platform.cloudflare_tunnel_enabled = False
        platform.cloudflare_tunnel_id = None
        platform.cloudflare_tunnel_token_enc = None

    async def client_for(self, platform: TenantPlatformSettings) -> CloudflareClient:
        token = self.get_api_token(platform)
        if not token:
            raise CloudflareApiError("Cloudflare API token is not configured")
        return CloudflareClient(token, platform.cloudflare_account_id)

    async def test_connection(
        self,
        platform: TenantPlatformSettings,
        *,
        api_token: str | None = None,
        account_id: str | None = None,
    ) -> tuple[bool, str, str | None]:
        token = (api_token or "").strip() or self.get_api_token(platform)
        if not token:
            return False, "API token is required", None
        client = CloudflareClient(token, account_id or platform.cloudflare_account_id)
        try:
            verify = await client.verify_token()
            status = str(verify.get("status", "active"))
            resolved_account = await client.resolve_account_id()
            return True, f"Token valid ({status})", resolved_account
        except CloudflareApiError as exc:
            return False, str(exc), None
