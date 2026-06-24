"""Provision and persist a real managed database for a Website.

Unlike :class:`DatabaseProvisioner` in ``provisioner.py`` (which only builds
connection metadata), this actually creates the database + user in the target
engine and registers it as a ControlBox managed database so it also shows up in
the Databases tab.
"""

from __future__ import annotations

import re

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType, DatabaseStatus
from controlbox.modules.databases.domain.services import DatabaseDomainService
from controlbox.modules.databases.infrastructure.engine_adapters import generate_password
from controlbox.modules.databases.infrastructure.provisioner import (
    DatabaseProvisioner,
    build_database_user,
    build_managed_database,
)
from controlbox.modules.websites.domain.entities import DatabaseEngine, Website
from controlbox.shared.application.unit_of_work import UnitOfWork

_ENGINE_MAP: dict[DatabaseEngine, DatabaseEngineType] = {
    DatabaseEngine.MYSQL: DatabaseEngineType.MYSQL,
    DatabaseEngine.MSSQL: DatabaseEngineType.MSSQL,
    DatabaseEngine.SUPABASE: DatabaseEngineType.POSTGRESQL,
}


def _slug_for(website: Website) -> str:
    base = (website.domain.split(".", 1)[0] if website.domain else "") or website.name or "site"
    slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_")
    if not slug:
        slug = "site"
    if not slug[0].isalpha():
        slug = f"s_{slug}"
    return slug[:24]


def _connection_url(
    engine: DatabaseEngineType, user: str, password: str, host: str, port: int, database: str
) -> str:
    if engine in (DatabaseEngineType.MYSQL, DatabaseEngineType.MARIADB):
        return f"mysql://{user}:{password}@{host}:{port}/{database}"
    if engine == DatabaseEngineType.POSTGRESQL:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    if engine == DatabaseEngineType.MSSQL:
        return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}"
    return ""


async def provision_website_managed_database(
    uow: UnitOfWork,
    settings: Settings,
    website: Website,
) -> dict:
    """Create the database + user for ``website`` and return its connection config."""
    engine_type = _ENGINE_MAP.get(website.database_engine)
    if engine_type is None:
        return {}

    db_domain = DatabaseDomainService(uow.managed_databases)
    db_prov = DatabaseProvisioner(settings)

    suffix = website.id.hex[:6]
    slug = db_domain.validate_name(f"{_slug_for(website)}_{suffix}")
    await db_domain.ensure_name_available(slug, website.tenant_id)

    database_name = db_domain.build_database_name(website.tenant_id, slug)
    host, port = db_prov.resolve_host_port(engine_type)
    database = build_managed_database(
        tenant_id=website.tenant_id,
        name=slug,
        engine=engine_type,
        host=host,
        port=port,
        database_name=database_name,
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
        raise RuntimeError(f"Database creation failed: {exc}") from exc

    if database.status != DatabaseStatus.ACTIVE:
        message = database.error_message or "Database provisioning did not complete"
        database.mark_error(message)
        await uow.managed_databases.save(database)
        await uow.commit()
        raise RuntimeError(f"Database creation failed: {message}")

    await uow.managed_databases.save(database)

    short_user = db_domain.validate_username(f"u_{suffix}")
    username = db_domain.build_username(website.tenant_id, short_user)
    password = generate_password()

    user, _ = build_database_user(
        database_id=database.id,
        tenant_id=website.tenant_id,
        username=username,
        plain_password=password,
        host="%",
        max_connections=20,
        grants=["ALL PRIVILEGES"],
    )
    await uow.database_users.add(user)
    try:
        await db_prov.provision_user(database, user, password)
    except Exception as exc:
        await uow.database_users.delete(user.id)
        database.mark_error(str(exc))
        await uow.managed_databases.save(database)
        await uow.commit()
        raise RuntimeError(f"Database user creation failed: {exc}") from exc

    await uow.database_users.save(user)
    await uow.commit()

    return {
        "engine": engine_type.value,
        "database_name": database_name,
        "username": username,
        "password": password,
        "host": host,
        "port": port,
        "connection_url": _connection_url(engine_type, username, password, host, port, database_name),
        "status": "active",
        "managed_database_id": str(database.id),
    }
