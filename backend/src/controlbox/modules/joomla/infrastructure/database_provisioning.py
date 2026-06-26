"""Provision and persist MySQL databases for Joomla sites."""

from __future__ import annotations

from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType, DatabaseStatus
from controlbox.modules.databases.domain.services import DatabaseDomainService
from controlbox.modules.databases.infrastructure.engine_adapters import generate_password
from controlbox.modules.databases.infrastructure.provisioner import (
    DatabaseProvisioner,
    build_database_user,
    build_managed_database,
)
from controlbox.modules.joomla.domain.entities import JoomlaSite
from controlbox.shared.application.unit_of_work import UnitOfWork


async def provision_joomla_managed_database(
    uow: UnitOfWork,
    settings: Settings,
    site: JoomlaSite,
) -> tuple[UUID, UUID, str, str, str]:
    """Create MySQL database + user, persist as ACTIVE in ControlBox."""
    db_domain = DatabaseDomainService(uow.managed_databases)
    db_prov = DatabaseProvisioner(settings)

    logical_name = site.settings.get("requested_db_name")
    if logical_name:
        slug = db_domain.validate_name(str(logical_name))
        await db_domain.ensure_name_available(slug, site.tenant_id)
    else:
        slug = f"jm_{site.id.hex[:8]}"

    mysql_database_name = db_domain.build_database_name(site.tenant_id, slug)
    database = build_managed_database(
        tenant_id=site.tenant_id,
        name=slug,
        engine=DatabaseEngineType.MYSQL,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database_name=mysql_database_name,
        charset="utf8mb4",
        max_connections=50,
    )

    await uow.managed_databases.add(database)
    try:
        await db_prov.provision_database(database)
    except Exception as exc:
        database.mark_error(str(exc))
        await uow.managed_databases.save(database)
        await uow.commit()
        raise RuntimeError(f"MySQL database creation failed: {exc}") from exc

    if database.status != DatabaseStatus.ACTIVE:
        message = database.error_message or "Database provisioning did not complete"
        database.mark_error(message)
        await uow.managed_databases.save(database)
        await uow.commit()
        raise RuntimeError(f"MySQL database creation failed: {message}")

    await uow.managed_databases.save(database)

    logical_user = site.settings.get("requested_db_user")
    if logical_user:
        short_user = db_domain.validate_username(str(logical_user))
    else:
        short_user = slug.replace("jm_", "u")[:30] or "jmuser"
        short_user = db_domain.validate_username(short_user)

    mysql_username = db_domain.build_username(site.tenant_id, short_user)
    requested_password = site.settings.get("requested_db_password")
    plain_password = str(requested_password) if requested_password else generate_password()
    if len(plain_password) < 8:
        plain_password = generate_password()

    user, _ = build_database_user(
        database_id=database.id,
        tenant_id=site.tenant_id,
        username=mysql_username,
        plain_password=plain_password,
        host="%",
        max_connections=20,
        grants=["ALL PRIVILEGES"],
    )
    await uow.database_users.add(user)
    try:
        await db_prov.provision_user(database, user, plain_password)
    except Exception as exc:
        await uow.database_users.delete(user.id)
        database.mark_error(str(exc))
        await uow.managed_databases.save(database)
        await uow.commit()
        raise RuntimeError(f"MySQL user creation failed: {exc}") from exc

    await uow.database_users.save(user)
    await uow.commit()

    site.settings.pop("requested_db_password", None)
    return database.id, user.id, mysql_database_name, mysql_username, plain_password
