"""Joomla deploy progress tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from controlbox.modules.joomla.domain.entities import JoomlaSite, JoomlaStatus
from controlbox.modules.joomla.infrastructure.site_access import build_site_access_info


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_provision_step(site: JoomlaSite, step: str, message: str) -> None:
    steps = list(site.settings.get("provision_steps") or [])
    steps.append({"step": step, "message": message, "at": _now_iso()})
    site.settings["provision_steps"] = steps


def set_provision_credentials(
    site: JoomlaSite,
    *,
    db_name: str,
    db_user: str,
    db_password: str,
    ftp_username: str | None = None,
    ftp_password: str | None = None,
    ftp_home: str | None = None,
) -> None:
    login_url = site.url.rstrip("/") + "/administrator"
    site.settings["provision_credentials"] = {
        "site_url": site.url,
        "login_url": login_url,
        "admin_user": site.admin_user,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "db_host": site.settings.get("db_host", ""),
        "ftp_username": ftp_username,
        "ftp_password": ftp_password,
        "ftp_home": ftp_home,
    }


def build_provision_status(site: JoomlaSite, settings=None) -> dict[str, Any]:
    steps = list(site.settings.get("provision_steps") or [])
    credentials = None
    raw = site.settings.get("provision_credentials")
    if isinstance(raw, dict):
        credentials = dict(raw)
    elif site.settings.get("db_name") and settings is not None:
        credentials = build_site_access_info(site, settings).__dict__
    elif site.status == JoomlaStatus.RUNNING and settings is not None:
        credentials = build_site_access_info(site, settings).__dict__
    return {
        "site_id": site.id,
        "status": site.status.value,
        "error_message": site.error_message,
        "steps": steps,
        "credentials": credentials,
    }
