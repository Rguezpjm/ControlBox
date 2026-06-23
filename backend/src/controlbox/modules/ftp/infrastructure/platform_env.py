"""Read FTP settings from platform.env (written by the panel)."""

from __future__ import annotations

from pathlib import Path

from controlbox.config.settings import Settings


def _platform_env_file(settings: Settings) -> Path:
    config_dir = settings.platform_config_dir
    if config_dir.startswith("/host/"):
        return Path(config_dir) / "platform.env"
    return Path("/host/etc/controlbox/platform.env")


def read_platform_env_value(settings: Settings, key: str, default: str = "") -> str:
    env_file = _platform_env_file(settings)
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value

    settings_fallback = {
        "PUREFTPD_ENABLED": str(settings.pureftpd_enabled).lower(),
        "PUREFTPD_PROTOCOL": settings.pureftpd_protocol,
        "PUREFTPD_PORT": str(settings.pureftpd_port),
        "PUREFTPD_PUBLIC_HOST": settings.pureftpd_public_host,
        "PUREFTPD_PASSIVE_MIN": str(settings.pureftpd_passive_port_min),
        "PUREFTPD_PASSIVE_MAX": str(settings.pureftpd_passive_port_max),
        "PUREFTPD_TLS": str(int(settings.pureftpd_tls)),
        "PUREFTPD_HOST": settings.pureftpd_host,
    }
    if key in settings_fallback and settings_fallback[key]:
        return str(settings_fallback[key])
    return default


def is_ftp_service_enabled(settings: Settings) -> bool:
    return read_platform_env_value(settings, "PUREFTPD_ENABLED", "false").lower() == "true"
