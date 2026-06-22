"""WordPress deploy progress tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from controlbox.modules.wordpress.domain.entities import WordPressSite, WordPressStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_provision_step(site: WordPressSite, step: str, message: str) -> None:
    steps = list(site.settings.get("provision_steps") or [])
    steps.append({"step": step, "message": message, "at": _now_iso()})
    site.settings["provision_steps"] = steps


def set_provision_credentials(
    site: WordPressSite,
    *,
    db_name: str,
    db_user: str,
    db_password: str,
) -> None:
    login_url = site.url.rstrip("/") + "/wp-admin"
    site.settings["provision_credentials"] = {
        "site_url": site.url,
        "login_url": login_url,
        "admin_user": site.admin_user,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "db_host": site.settings.get("db_host", ""),
    }


def build_provision_status(site: WordPressSite) -> dict[str, Any]:
    steps = list(site.settings.get("provision_steps") or [])
    credentials = None
    if site.status == WordPressStatus.RUNNING:
        raw = site.settings.get("provision_credentials")
        if isinstance(raw, dict):
            credentials = dict(raw)
    return {
        "site_id": site.id,
        "status": site.status.value,
        "error_message": site.error_message,
        "steps": steps,
        "credentials": credentials,
    }
