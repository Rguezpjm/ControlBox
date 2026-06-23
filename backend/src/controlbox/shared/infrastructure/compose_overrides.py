"""Resolve dynamic Docker Compose override files on the host."""

from __future__ import annotations

from pathlib import Path

from controlbox.config.settings import Settings

FTP_OVERRIDE_FILENAME = "docker-compose.ftp.yml"


def host_install_dir(settings: Settings) -> Path:
    raw = settings.controlbox_install_dir
    if raw.startswith("/host/"):
        return Path(raw)
    return Path("/host/opt/controlbox")


def host_config_dir(settings: Settings) -> Path:
    raw = settings.platform_config_dir
    if raw.startswith("/host/"):
        return Path(raw)
    return Path("/host/etc/controlbox")


def ftp_override_write_path(settings: Settings) -> Path:
    """Path where the panel writes FTP port mappings (writable config dir)."""
    return host_config_dir(settings) / FTP_OVERRIDE_FILENAME


def ftp_override_read_path(settings: Settings) -> Path | None:
    """Existing FTP override file (config dir preferred, install dir legacy)."""
    primary = ftp_override_write_path(settings)
    legacy = host_install_dir(settings) / FTP_OVERRIDE_FILENAME
    if primary.is_file() and primary.stat().st_size > 0:
        return primary
    if legacy.is_file() and legacy.stat().st_size > 0:
        return legacy
    if primary.is_file():
        return primary
    if legacy.is_file():
        return legacy
    return None


def write_ftp_override(settings: Settings, content: str) -> Path:
    """Write FTP compose override; config dir first, install dir as fallback."""
    candidates = (
        ftp_override_write_path(settings),
        host_install_dir(settings) / FTP_OVERRIDE_FILENAME,
    )
    errors: list[str] = []
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return path
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    detail = "; ".join(errors)
    raise OSError(
        f"No se pudo escribir {FTP_OVERRIDE_FILENAME} ({detail}). "
        "En el VPS ejecute: controlbox repair && "
        "docker compose --env-file /etc/controlbox/platform.env up -d --force-recreate api worker"
    )


def compose_override_files(settings: Settings) -> list[Path]:
    """Extra compose files to pass after docker-compose.yml."""
    install_dir = host_install_dir(settings)
    paths: list[Path] = []
    for name in (
        "docker-compose.override.yml",
        "docker-compose.ports.yml",
        "docker-compose.build.yml",
        "docker-compose.cloudflare.yml",
    ):
        path = install_dir / name
        if path.is_file():
            paths.append(path)
    ftp = ftp_override_read_path(settings)
    if ftp is not None:
        paths.append(ftp)
    return paths
