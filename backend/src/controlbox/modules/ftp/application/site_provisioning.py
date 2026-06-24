"""Shared helper to auto-provision an FTP/SFTP account for a site.

Used by the WordPress and Websites modules so that toggling "Create FTP account"
during deployment results in a real, usable account: it first ensures the FTP
service is enabled and running, then creates the account.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.ftp.application.command_handlers import CreateFtpAccountHandler
from controlbox.modules.ftp.application.commands import CreateFtpAccountCommand
from controlbox.modules.ftp.domain.entities import FtpAccountStatus
from controlbox.modules.ftp.infrastructure.service_manager import FtpServiceManager
from controlbox.modules.identity.infrastructure.unit_of_work import Database

logger = logging.getLogger("controlbox.ftp.provision")


def slug_ftp_username(raw: str) -> str:
    base = re.sub(r"[^a-z0-9_]+", "_", (raw or "").lower()).strip("_")
    if not base:
        base = "siteftp"
    if not base[0].isalpha():
        base = f"u_{base}"
    return base[:31]


async def provision_site_ftp_account(
    database: Database,
    settings: Settings,
    *,
    tenant_id: UUID,
    owner_user_id: UUID | None,
    username: str,
    home_directory: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Ensure the FTP service is running and create an account for a site.

    Returns ``(username, password, home_directory, error_message)``. On success
    ``error_message`` is ``None``; on failure the first three values are ``None``.
    """
    manager = FtpServiceManager(settings)
    ok, message = await manager.ensure_running()
    if not ok:
        return None, None, None, message or "Servicio FTP no disponible"

    try:
        async with database.unit_of_work() as uow:
            account, password = await CreateFtpAccountHandler(uow, settings=settings).handle(
                CreateFtpAccountCommand(
                    tenant_id=tenant_id,
                    user_id=owner_user_id,
                    username=username,
                    password=None,
                    home_directory=home_directory,
                    quota_mb=0,
                    max_files=0,
                    upload_bandwidth_kbps=0,
                    download_bandwidth_kbps=0,
                )
            )
    except Exception as exc:  # noqa: BLE001 - surfaced to caller as a warning
        logger.exception("FTP account provisioning failed")
        return None, None, None, str(exc)

    if account.status == FtpAccountStatus.ACTIVE:
        return account.username, password, home_directory, None
    return None, None, None, account.error_message or "La cuenta FTP no pudo activarse"
