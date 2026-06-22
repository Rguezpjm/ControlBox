"""Reset the panel admin password to match platform.env (installer recovery)."""

from __future__ import annotations

import asyncio
import logging
import sys

from controlbox.config.settings import get_settings
from controlbox.installer.bootstrap_tenant import (
    _ensure_bootstrap_admin_privileges,
    _normalize_password,
    _resolve_bootstrap_config,
)
from controlbox.modules.identity.infrastructure.unit_of_work import Database

logger = logging.getLogger("controlbox.installer")


async def reset_admin_password() -> int:
    config = _resolve_bootstrap_config()

    try:
        config["admin_password"] = _normalize_password(config["admin_password"])
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    if not config["admin_email"] or not config["admin_password"]:
        logger.error("TENANT_ADMIN_EMAIL and TENANT_ADMIN_PASSWORD must be set in platform.env")
        return 1

    settings = get_settings()
    database = Database(settings)

    try:
        async with database.unit_of_work() as uow:
            synced = await _ensure_bootstrap_admin_privileges(
                uow,
                config["admin_email"],
                config["admin_password"],
            )
            if not synced:
                logger.error("Admin user not found: %s", config["admin_email"].strip().lower())
                return 1
            await uow.commit()

        email = config["admin_email"].strip().lower()
        logger.info("Admin password reset and Owner privileges synced for %s", email)
        print(f"ADMIN_PASSWORD_RESET={email}")
        print("TENANT_OWNER_SYNCED=true")
        return 0
    except Exception:
        logger.exception("Admin password reset failed")
        return 1
    finally:
        await database.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(asyncio.run(reset_admin_password()))


if __name__ == "__main__":
    main()
