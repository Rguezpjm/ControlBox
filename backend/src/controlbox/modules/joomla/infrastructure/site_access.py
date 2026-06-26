"""Build Joomla site access / credential views for the panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from controlbox.config.settings import Settings
from controlbox.modules.joomla.domain.entities import JoomlaSite
from controlbox.modules.joomla.infrastructure.provisioner import JoomlaProvisioner


@dataclass(frozen=True)
class JoomlaSiteAccessInfo:
    site_url: str
    login_url: str
    admin_user: str
    admin_email: str
    db_name: str | None = None
    db_user: str | None = None
    db_host: str | None = None
    db_password: str | None = None
    ftp_username: str | None = None
    ftp_password: str | None = None
    ftp_home: str | None = None


def build_site_access_info(
    site: JoomlaSite,
    settings: Settings | None = None,
    *,
    decrypt_db_password: bool = True,
) -> JoomlaSiteAccessInfo:
    creds: dict[str, Any] = {}
    raw = site.settings.get("provision_credentials")
    if isinstance(raw, dict):
        creds = raw

    login_url = str(creds.get("login_url") or f"{site.url.rstrip('/')}/administrator")
    db_name = creds.get("db_name") or site.settings.get("db_name")
    db_user = creds.get("db_user") or site.settings.get("db_user")
    db_host = creds.get("db_host") or site.settings.get("db_host") or ""
    db_password = creds.get("db_password")

    if not db_password and decrypt_db_password and settings and site.settings.get("db_password_enc"):
        try:
            db_password = JoomlaProvisioner(settings).decrypt_db_password(
                str(site.settings["db_password_enc"])
            )
        except Exception:
            db_password = None

    return JoomlaSiteAccessInfo(
        site_url=str(creds.get("site_url") or site.url),
        login_url=login_url,
        admin_user=site.admin_user,
        admin_email=site.admin_email,
        db_name=str(db_name) if db_name else None,
        db_user=str(db_user) if db_user else None,
        db_host=str(db_host) if db_host else None,
        db_password=str(db_password) if db_password else None,
        ftp_username=creds.get("ftp_username"),
        ftp_password=creds.get("ftp_password"),
        ftp_home=creds.get("ftp_home"),
    )
