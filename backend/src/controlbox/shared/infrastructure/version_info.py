"""Resolve the running ControlBox version from env files, install state, and package metadata."""

from __future__ import annotations

import re
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.version import __version__

_IMAGE_TAG_RE = re.compile(r":([^:/@]+)$")


def _read_env_key(env_file: Path, key: str) -> str:
    try:
        if not env_file.is_file():
            return ""
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except (PermissionError, OSError):
        pass
    return ""


def _host_platform_env(settings: Settings) -> Path:
    config_dir = settings.platform_config_dir or ""
    if config_dir.startswith("/host/"):
        return Path(config_dir) / "platform.env"
    if settings.host_root_path:
        return Path(settings.host_root_path) / "etc/controlbox/platform.env"
    return Path(config_dir) / "platform.env"


def _host_install_state(settings: Settings) -> Path:
    data_dir = settings.controlbox_data_dir or "/var/lib/controlbox"
    if settings.host_root_path and not data_dir.startswith("/host/"):
        return Path(settings.host_root_path) / "var/lib/controlbox/state/install.state"
    if data_dir.startswith("/host/"):
        return Path(data_dir) / "state/install.state"
    return Path("/var/lib/controlbox/state/install.state")


def _normalize_version(raw: str) -> str:
    value = raw.strip().strip('"').strip("'")
    if not value or value.lower() in {"latest", "unknown", "null"}:
        return ""
    if value[0] in {"v", "V"}:
        value = value[1:]
    return value


def resolve_controlbox_version(settings: Settings) -> str:
    """Best-effort version: platform.env → runtime env → install.state → package __version__."""
    try:
        candidates: list[str] = []

        file_version = _normalize_version(_read_env_key(_host_platform_env(settings), "CONTROLBOX_VERSION"))
        if file_version:
            candidates.append(file_version)

        env_version = _normalize_version(settings.controlbox_version or "")
        if env_version and env_version not in candidates:
            candidates.append(env_version)

        state_file = _host_install_state(settings)
        if state_file.is_file():
            state_version = _normalize_version(_read_env_key(state_file, "VERSION"))
            if state_version and state_version not in candidates:
                candidates.append(state_version)

        if candidates:
            return candidates[0]
    except Exception:
        pass

    return __version__


def version_from_image_ref(image_ref: str) -> str:
    ref = image_ref.strip()
    if not ref:
        return ""
    match = _IMAGE_TAG_RE.search(ref)
    if not match:
        return ""
    tag = _normalize_version(match.group(1))
    if tag.lower() in {"latest", "hardened"}:
        return ""
    return tag
