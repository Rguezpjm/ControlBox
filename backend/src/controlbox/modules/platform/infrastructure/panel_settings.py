"""Panel settings — read/write tenant preferences and host paths."""

from __future__ import annotations

import asyncio
import ipaddress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controlbox.config.settings import Settings
from controlbox.shared.infrastructure.version_info import resolve_controlbox_version
from controlbox.modules.platform.domain.entities import TenantPlatformSettings
from controlbox.modules.platform.infrastructure.panel_config import PanelConfigService
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.modules.platform.infrastructure.telegram_notifier import TelegramNotifier


DEFAULT_PANEL_SETTINGS: dict[str, Any] = {
    "panel_alias": "",
    "session_timeout_hours": 24,
    "ipv6_enabled": False,
    "offline_mode": False,
    "cdn_proxy": False,
    "auto_fetch_favicon": True,
    "auto_backup_panel": True,
    "auto_backup_retention": 30,
    "server_ip_override": "",
    "sidebar_hidden_items": [],
    "panel_ip_whitelist": [],
}

PANEL_IP_WHITELIST_MAX = 64


def normalize_ip_whitelist(raw: object | None) -> list[str]:
    """Validate and canonicalize a list of IPs / CIDRs for the panel allowlist."""
    items: list[str]
    if isinstance(raw, str):
        items = [chunk for chunk in raw.replace("\n", ",").replace(";", ",").split(",")]
    elif isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        return []
    result: list[str] = []
    for item in items:
        value = item.strip()
        if not value:
            continue
        try:
            if "/" in value:
                norm = str(ipaddress.ip_network(value, strict=False))
            else:
                ip = ipaddress.ip_address(value)
                norm = f"{ip}/32" if ip.version == 4 else f"{ip}/128"
        except ValueError:
            continue
        if norm not in result:
            result.append(norm)
        if len(result) >= PANEL_IP_WHITELIST_MAX:
            break
    return result

SIDEBAR_NAV_IDS = frozenset({
    "dashboard",
    "websites",
    "wordpress",
    "staging",
    "domains",
    "dns",
    "email",
    "databases",
    "files",
    "ftp",
    "backups",
    "monitoring",
    "security",
    "team",
    "settings",
})
SIDEBAR_LOCKED_NAV_IDS = frozenset({"dashboard", "settings"})


def normalize_sidebar_hidden(raw: object | None) -> list[str]:
    if not isinstance(raw, list):
        return []
    hidden: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        nav_id = item.strip()
        if nav_id in SIDEBAR_NAV_IDS and nav_id not in SIDEBAR_LOCKED_NAV_IDS and nav_id not in hidden:
            hidden.append(nav_id)
    return hidden


def merge_panel_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULT_PANEL_SETTINGS, **(raw or {})}
    merged["session_timeout_hours"] = max(1, min(168, int(merged.get("session_timeout_hours") or 24)))
    merged["auto_backup_retention"] = max(1, min(365, int(merged.get("auto_backup_retention") or 30)))
    merged["sidebar_hidden_items"] = normalize_sidebar_hidden(merged.get("sidebar_hidden_items"))
    merged["panel_ip_whitelist"] = normalize_ip_whitelist(merged.get("panel_ip_whitelist"))
    return merged


class PanelSettingsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._panel = PanelConfigService(settings)

    def _env_file(self) -> Path:
        return Path(self._settings.platform_config_dir) / "platform.env"

    def _can_write_env(self) -> bool:
        return self._env_file().is_file()

    # --- Branding (custom panel logo) -------------------------------------
    LOGO_CONTENT_TYPES: dict[str, str] = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/svg+xml": "svg",
    }
    _LOGO_EXT_MEDIA: dict[str, str] = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "svg": "image/svg+xml",
    }
    LOGO_MAX_BYTES = 2 * 1024 * 1024

    def _branding_dir(self) -> Path:
        return Path(self._settings.platform_config_dir) / "branding"

    def find_logo(self) -> Path | None:
        branding = self._branding_dir()
        if not branding.is_dir():
            return None
        for ext in ("png", "svg", "webp", "jpg", "jpeg", "gif"):
            candidate = branding / f"panel-logo.{ext}"
            if candidate.is_file():
                return candidate
        return None

    def logo_media_type(self, path: Path) -> str:
        return self._LOGO_EXT_MEDIA.get(path.suffix.lstrip(".").lower(), "application/octet-stream")

    def save_logo(self, content: bytes, content_type: str) -> tuple[bool, str]:
        ext = self.LOGO_CONTENT_TYPES.get((content_type or "").split(";")[0].strip().lower())
        if not ext:
            return False, "Formato no soportado. Use PNG, JPG, WEBP, GIF o SVG."
        if not content:
            return False, "Archivo vacío"
        if len(content) > self.LOGO_MAX_BYTES:
            return False, "El logo supera el tamaño máximo de 2 MB"
        branding = self._branding_dir()
        try:
            branding.mkdir(parents=True, exist_ok=True)
            for existing in branding.glob("panel-logo.*"):
                existing.unlink(missing_ok=True)
            (branding / f"panel-logo.{ext}").write_bytes(content)
        except OSError as exc:
            return False, f"No se pudo guardar el logo: {exc}"
        return True, "Logo actualizado"

    def remove_logo(self) -> bool:
        branding = self._branding_dir()
        removed = False
        if branding.is_dir():
            for existing in branding.glob("panel-logo.*"):
                try:
                    existing.unlink(missing_ok=True)
                    removed = True
                except OSError:
                    pass
        return removed

    # --- Panel IP allowlist (Traefik dynamic middleware) ------------------
    def _traefik_dynamic_dir(self) -> Path:
        return Path(self._settings.platform_config_dir) / "traefik" / "dynamic"

    def _allowlist_file(self) -> Path:
        return self._traefik_dynamic_dir() / "panel-allowlist.yml"

    def ip_whitelist_supported(self) -> bool:
        """The Traefik allowlist only attaches when the panel is published via
        the file-provider router (IP-access mode, port 80)."""
        return (self._traefik_dynamic_dir() / "panel-ip.yml").is_file()

    def _panel_prefix(self) -> str:
        base = (self._settings.panel_base_path or "").strip()
        if base and not base.startswith("/"):
            base = f"/{base}"
        return base or "/"

    def _render_allowlist_yaml(self, ranges: list[str], use_forwarded: bool) -> str:
        prefix = self._panel_prefix()
        source_lines = "\n".join(f'          - "{r}"' for r in ranges)
        ip_strategy = "        ipStrategy:\n          depth: 1\n" if use_forwarded else ""
        return (
            "# Generated by ControlBox - panel IP allowlist. Do not edit by hand.\n"
            "http:\n"
            "  middlewares:\n"
            "    controlbox-panel-allowlist:\n"
            "      ipAllowList:\n"
            "        sourceRange:\n"
            f"{source_lines}\n"
            f"{ip_strategy}"
            "  routers:\n"
            "    controlbox-panel-guard:\n"
            f'      rule: "PathPrefix(`{prefix}`)"\n'
            "      entryPoints:\n"
            "        - web\n"
            "      service: controlbox-panel-guard-svc\n"
            "      priority: 200\n"
            "      middlewares:\n"
            "        - controlbox-panel-allowlist\n"
            "  services:\n"
            "    controlbox-panel-guard-svc:\n"
            "      loadBalancer:\n"
            "        servers:\n"
            '          - url: "http://panel:3000"\n'
        )

    def apply_ip_whitelist(self, platform: TenantPlatformSettings) -> tuple[bool, str]:
        prefs = merge_panel_settings(platform.panel_settings)
        ranges = prefs["panel_ip_whitelist"]
        allowlist_file = self._allowlist_file()
        if not ranges:
            try:
                allowlist_file.unlink(missing_ok=True)
            except OSError:
                pass
            return True, "Whitelist de IPs desactivada"
        if not self.ip_whitelist_supported():
            return (
                False,
                "La whitelist requiere el modo de acceso por IP (Traefik en puerto 80). "
                "Ejecute en el servidor: sudo controlbox repair --apply-panel",
            )
        use_forwarded = bool(prefs.get("cdn_proxy")) or bool(self._settings.security_trust_proxy)
        try:
            self._traefik_dynamic_dir().mkdir(parents=True, exist_ok=True)
            allowlist_file.write_text(self._render_allowlist_yaml(ranges, use_forwarded), encoding="utf-8")
        except OSError as exc:
            return False, f"No se pudo aplicar la whitelist: {exc}"
        return True, f"Whitelist aplicada ({len(ranges)} IP/rangos). Solo esas IPs pueden abrir el panel."

    def _ip_whitelist_view(self, prefs: dict[str, Any]) -> dict[str, Any]:
        return {
            "panel_ip_whitelist": prefs["panel_ip_whitelist"],
            "panel_ip_whitelist_active": self._allowlist_file().is_file(),
            "panel_ip_whitelist_supported": self.ip_whitelist_supported(),
        }

    def _logo_view(self) -> dict[str, Any]:
        logo = self.find_logo()
        if logo is None:
            return {"has_custom_logo": False, "logo_version": 0}
        try:
            version = int(logo.stat().st_mtime)
        except OSError:
            version = 0
        return {"has_custom_logo": True, "logo_version": version}

    def _backup_stats(self) -> dict[str, Any]:
        backup_root = Path(self._settings.backups_base_path)
        if not backup_root.is_dir():
            return {"count": 0, "used_mb": 0.0}
        files = list(backup_root.rglob("*"))
        file_items = [f for f in files if f.is_file()]
        total_bytes = sum(f.stat().st_size for f in file_items)
        return {"count": len(file_items), "used_mb": round(total_bytes / (1024 * 1024), 2)}

    def _server_time(self) -> dict[str, str]:
        now = datetime.now(timezone.utc).astimezone()
        return {
            "iso": now.isoformat(),
            "display": now.strftime("%Y-%m-%d %H:%M:%S %Z %z"),
            "timezone": str(now.tzinfo or "UTC"),
        }

    def build_view(self, platform: TenantPlatformSettings) -> dict[str, Any]:
        panel = self._panel.get_config()
        prefs = merge_panel_settings(platform.panel_settings)
        backup_stats = self._backup_stats()
        server_time = self._server_time()
        return {
            "panel_alias": prefs["panel_alias"],
            "session_timeout_hours": prefs["session_timeout_hours"],
            "panel_port": panel["panel_port"],
            "panel_base_path": panel["panel_base_path"],
            "panel_url_hint": panel["panel_url_hint"],
            "can_apply_host_changes": panel["can_apply_changes"],
            "default_site_folder": self._settings.sites_base_path,
            "default_backup_folder": self._settings.backups_base_path,
            "server_ip": prefs["server_ip_override"] or self._detect_server_ip(),
            "server_time": server_time,
            "ipv6_enabled": prefs["ipv6_enabled"],
            "offline_mode": prefs["offline_mode"],
            "cdn_proxy": prefs["cdn_proxy"],
            "site_monitor_enabled": platform.alerts_enabled,
            "auto_fetch_favicon": prefs["auto_fetch_favicon"],
            "auto_backup_panel": prefs["auto_backup_panel"],
            "auto_backup_retention": prefs["auto_backup_retention"],
            "auto_backup_count": backup_stats["count"],
            "auto_backup_used_mb": backup_stats["used_mb"],
            "cpu_threshold_percent": platform.cpu_threshold_percent,
            "memory_threshold_percent": platform.memory_threshold_percent,
            "disk_threshold_percent": platform.disk_threshold_percent,
            "alert_cooldown_minutes": platform.alert_cooldown_minutes,
            "telegram_alerts_enabled": platform.telegram_alerts_enabled,
            "telegram_chat_id": platform.telegram_chat_id or "",
            "telegram_bot_configured": bool(platform.telegram_bot_token_enc),
            "controlbox_version": resolve_controlbox_version(self._settings),
            "controlbox_profile": self._settings.controlbox_profile,
            "os_label": self._settings.controlbox_os_label,
            "sidebar_hidden_items": prefs["sidebar_hidden_items"],
            **self._logo_view(),
            **self._ip_whitelist_view(prefs),
        }

    def _detect_server_ip(self) -> str:
        if self._settings.controlbox_server_ip.strip():
            return self._settings.controlbox_server_ip.strip()
        prefs = merge_panel_settings({})
        override = prefs.get("server_ip_override", "")
        return override or "127.0.0.1"

    def apply_preferences(
        self,
        platform: TenantPlatformSettings,
        *,
        panel_alias: str | None = None,
        session_timeout_hours: int | None = None,
        ipv6_enabled: bool | None = None,
        offline_mode: bool | None = None,
        cdn_proxy: bool | None = None,
        auto_fetch_favicon: bool | None = None,
        auto_backup_panel: bool | None = None,
        auto_backup_retention: int | None = None,
        server_ip: str | None = None,
        panel_ip_whitelist: list[str] | None = None,
        site_monitor_enabled: bool | None = None,
        cpu_threshold_percent: float | None = None,
        memory_threshold_percent: float | None = None,
        disk_threshold_percent: float | None = None,
        alert_cooldown_minutes: int | None = None,
        telegram_alerts_enabled: bool | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
        sidebar_hidden_items: list[str] | None = None,
    ) -> None:
        prefs = merge_panel_settings(platform.panel_settings)
        if panel_alias is not None:
            prefs["panel_alias"] = panel_alias.strip()[:128]
        if session_timeout_hours is not None:
            prefs["session_timeout_hours"] = max(1, min(168, session_timeout_hours))
        if ipv6_enabled is not None:
            prefs["ipv6_enabled"] = ipv6_enabled
        if offline_mode is not None:
            prefs["offline_mode"] = offline_mode
        if cdn_proxy is not None:
            prefs["cdn_proxy"] = cdn_proxy
        if auto_fetch_favicon is not None:
            prefs["auto_fetch_favicon"] = auto_fetch_favicon
        if auto_backup_panel is not None:
            prefs["auto_backup_panel"] = auto_backup_panel
        if auto_backup_retention is not None:
            prefs["auto_backup_retention"] = max(1, min(365, auto_backup_retention))
        if server_ip is not None:
            prefs["server_ip_override"] = server_ip.strip()[:64]
        if panel_ip_whitelist is not None:
            prefs["panel_ip_whitelist"] = normalize_ip_whitelist(panel_ip_whitelist)
        if sidebar_hidden_items is not None:
            prefs["sidebar_hidden_items"] = normalize_sidebar_hidden(sidebar_hidden_items)
        platform.panel_settings = prefs

        if site_monitor_enabled is not None:
            platform.alerts_enabled = site_monitor_enabled
        if cpu_threshold_percent is not None:
            platform.cpu_threshold_percent = cpu_threshold_percent
        if memory_threshold_percent is not None:
            platform.memory_threshold_percent = memory_threshold_percent
        if disk_threshold_percent is not None:
            platform.disk_threshold_percent = disk_threshold_percent
        if alert_cooldown_minutes is not None:
            platform.alert_cooldown_minutes = alert_cooldown_minutes

        if telegram_alerts_enabled is not None:
            platform.telegram_alerts_enabled = telegram_alerts_enabled
        if telegram_chat_id is not None:
            platform.telegram_chat_id = telegram_chat_id.strip()[:64] or None
        if telegram_bot_token:
            encryptor = SecretEncryptor(self._settings)
            platform.telegram_bot_token_enc = encryptor.encrypt(telegram_bot_token.strip())

    async def test_telegram(
        self,
        platform: TenantPlatformSettings,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> tuple[bool, str]:
        notifier = TelegramNotifier(SecretEncryptor(self._settings))
        token = bot_token
        cid = chat_id or platform.telegram_chat_id
        if not token and platform.telegram_bot_token_enc:
            token = SecretEncryptor(self._settings).decrypt(platform.telegram_bot_token_enc)
        if not token or not cid:
            return False, "Bot token and chat ID are required"
        return await notifier.test_connection(bot_token=token, chat_id=cid)

    async def notify_telegram_alert(
        self,
        platform: TenantPlatformSettings,
        *,
        message: str,
        severity: str,
    ) -> None:
        if not platform.telegram_alerts_enabled:
            return
        notifier = TelegramNotifier(SecretEncryptor(self._settings))
        await notifier.send_alert(
            bot_token_enc=platform.telegram_bot_token_enc,
            chat_id=platform.telegram_chat_id,
            message=message,
            severity=severity,
        )

    async def update_host_paths(
        self,
        *,
        default_site_folder: str | None = None,
        default_backup_folder: str | None = None,
    ) -> dict[str, Any]:
        env_file = self._env_file()
        if not env_file.is_file():
            return {
                "applied": False,
                "message": "Host config not writable from API. Run: controlbox repair",
            }
        content = env_file.read_text(encoding="utf-8")
        if default_site_folder is not None:
            content = self._panel._replace_env_value(content, "SITES_BASE_PATH", default_site_folder.strip())[0]
        if default_backup_folder is not None:
            content = self._panel._replace_env_value(content, "BACKUPS_BASE_PATH", default_backup_folder.strip())[0]
        env_file.write_text(content, encoding="utf-8")
        install_env = Path(self._settings.controlbox_install_dir) / ".env"
        if install_env.exists():
            install_env.write_text(content, encoding="utf-8")
        return {"applied": True, "message": "Paths saved. Restart API/worker to apply fully."}

    async def sync_server_time(self) -> dict[str, str]:
        cmd = ["timedatectl", "set-ntp", "true"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        except OSError:
            pass
        return self._server_time()

    async def shutdown_panel_only(self) -> dict[str, Any]:
        install_dir = Path(self._settings.controlbox_install_dir)
        compose = install_dir / "docker-compose.yml"
        if not compose.is_file():
            return {"success": False, "message": "Panel compose file not found on host"}
        env_file = f"{self._settings.platform_config_dir}/platform.env"
        cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose), "stop", "panel"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                return {"success": False, "message": stderr.decode() or "Failed to stop panel"}
            return {"success": True, "message": "Panel stopped. Websites and databases keep running."}
        except OSError as exc:
            return {"success": False, "message": str(exc)}
