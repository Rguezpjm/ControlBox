"""Bootstrap the first tenant during installation without enabling public registration."""



from __future__ import annotations



import asyncio

import logging

import os

import sys



from controlbox.config.settings import get_settings

from controlbox.modules.identity.application.command_handlers import RegisterTenantHandler

from controlbox.modules.identity.application.commands import RegisterTenantCommand

from controlbox.modules.identity.domain.services import PasswordService, SessionService, TokenService

from controlbox.modules.identity.infrastructure.unit_of_work import Database

from controlbox.modules.team_members.domain.entities import TeamMember, TeamMemberStatus

from controlbox.shared.domain.base import NotFoundError, utc_now

from controlbox.shared.infrastructure.redis.client import RedisClient, SessionCache



logger = logging.getLogger("controlbox.installer")





def _env_first(*keys: str) -> str:

    for key in keys:

        value = os.environ.get(key, "").strip()

        if value:

            return value

    return ""





def _resolve_bootstrap_config() -> dict[str, str]:

    settings = get_settings()

    return {

        "name": _env_first("INSTALLER_TENANT_NAME", "TENANT_NAME", "CONTROLBOX_TENANT_NAME"),

        "slug": _env_first("INSTALLER_TENANT_SLUG", "TENANT_SLUG", "CONTROLBOX_TENANT_SLUG"),

        "admin_email": _env_first(

            "INSTALLER_TENANT_ADMIN_EMAIL",

            "TENANT_ADMIN_EMAIL",

            "CONTROLBOX_TENANT_ADMIN_EMAIL",

        ),

        "admin_password": _env_first(

            "TENANT_ADMIN_PASSWORD",

            "INSTALLER_TENANT_ADMIN_PASSWORD",

            "CONTROLBOX_TENANT_ADMIN_PASSWORD",

        ),

        "admin_full_name": _env_first(

            "INSTALLER_TENANT_ADMIN_FULL_NAME",

            "TENANT_ADMIN_FULL_NAME",

            "CONTROLBOX_TENANT_ADMIN_FULL_NAME",

        ) or "Administrador",

        "bootstrap_token": _env_first("INSTALLER_BOOTSTRAP_TOKEN") or settings.installer_bootstrap_token.strip(),

    }





def _normalize_password(value: str) -> str:

    cleaned = value.strip().strip('"').strip("'")

    cleaned = cleaned.splitlines()[0].strip()

    cleaned = cleaned.replace("\r", "").replace("\n", "").replace(" ", "")

    byte_len = len(cleaned.encode("utf-8"))

    if byte_len > 72:

        logger.error(

            "Admin password too long for bcrypt (%s bytes, max 72). "

            "Fix TENANT_ADMIN_PASSWORD in platform.env (8-64 characters).",

            byte_len,

        )

        raise ValueError("admin password exceeds bcrypt limit")

    if len(cleaned) < 8:

        raise ValueError("admin password must be at least 8 characters")

    return cleaned





async def _ensure_bootstrap_admin_privileges(uow, admin_email: str, admin_password: str) -> bool:

    """Sync password and ensure Owner + platform admin for the bootstrap account."""

    email = admin_email.strip().lower()

    user = await uow.users.get_by_email(email, None)

    if user is None:

        return False



    passwords = PasswordService()

    user.password_hash = passwords.hash(admin_password)

    if not user.is_platform_admin:

        user.is_platform_admin = True

    await uow.users.save(user)



    if user.tenant_id is None:

        return True



    owner_role = await uow.team_roles.get_by_slug("owner")

    if owner_role is None:

        raise NotFoundError("Team role 'owner' not found; run database migrations")



    existing = await uow.team_members.get_by_user_and_tenant(user.id, user.tenant_id)

    if existing is None:

        await uow.team_members.add(

            TeamMember(

                tenant_id=user.tenant_id,

                user_id=user.id,

                team_role_id=owner_role.id,

                status=TeamMemberStatus.ACTIVE,

                joined_at=utc_now(),

            )

        )

    elif existing.team_role_id != owner_role.id:

        existing.team_role_id = owner_role.id

        existing.status = TeamMemberStatus.ACTIVE

        await uow.team_members.save(existing)



    return True





async def bootstrap_tenant() -> int:

    config = _resolve_bootstrap_config()



    if not config["bootstrap_token"]:

        logger.error("INSTALLER_BOOTSTRAP_TOKEN is not configured in platform.env")

        return 1



    try:

        config["admin_password"] = _normalize_password(config["admin_password"])

    except ValueError as exc:

        logger.error("%s", exc)

        return 1



    missing = [

        label

        for label, value in {

            "name": config["name"],

            "slug": config["slug"],

            "admin_email": config["admin_email"],

            "admin_password": config["admin_password"],

            "admin_full_name": config["admin_full_name"],

        }.items()

        if not value.strip()

    ]

    if missing:

        logger.error("Missing required tenant fields: %s", ", ".join(missing))

        return 1



    settings = get_settings()

    database = Database(settings)

    redis_client = RedisClient(settings)

    session_cache = SessionCache(redis_client, settings)



    try:

        async with database.unit_of_work() as uow:

            existing = await uow.tenants.list_active_ids()

            if existing:

                synced = await _ensure_bootstrap_admin_privileges(

                    uow,

                    config["admin_email"],

                    config["admin_password"],

                )

                await uow.commit()

                if synced:

                    logger.info(

                        "Bootstrap admin synced: Owner role + platform admin + password",

                        extra={"admin_email": config["admin_email"].strip().lower()},

                    )

                    print(f"TENANT_SLUG={config['slug']}")

                    print(f"TENANT_ADMIN_EMAIL={config['admin_email'].strip().lower()}")

                    print("TENANT_PASSWORD_SYNCED=true")

                    print("TENANT_OWNER_SYNCED=true")

                    return 0



                logger.info("Tenant bootstrap skipped: %s tenant(s) already exist", len(existing))

                return 0



            token_service = TokenService(settings)

            handler = RegisterTenantHandler(

                uow=uow,

                password_service=PasswordService(),

                token_service=token_service,

                session_service=SessionService(token_service),

                session_cache=session_cache,

            )

            tenant, user, _tokens = await handler.handle(

                RegisterTenantCommand(

                    name=config["name"].strip(),

                    slug=config["slug"].strip().lower(),

                    admin_email=config["admin_email"].strip(),

                    admin_password=config["admin_password"],

                    admin_full_name=config["admin_full_name"].strip(),

                )

            )



        logger.info(

            "Tenant bootstrap completed",

            extra={"tenant_slug": tenant.slug, "admin_email": user.email},

        )

        print(f"TENANT_SLUG={tenant.slug}")

        print(f"TENANT_ADMIN_EMAIL={user.email}")

        return 0

    except Exception:

        logger.exception("Tenant bootstrap failed")

        return 1

    finally:

        await database.dispose()

        await redis_client.close()





def main() -> None:

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sys.exit(asyncio.run(bootstrap_tenant()))





if __name__ == "__main__":

    main()

