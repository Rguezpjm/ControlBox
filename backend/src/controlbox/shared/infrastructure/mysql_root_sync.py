"""Resync MySQL root password with platform.env when the data volume holds a different secret."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from controlbox.config.settings import Settings, get_settings
from controlbox.shared.infrastructure.db_engine_cli import docker_env, docker_exec, spawn
from controlbox.shared.infrastructure.mysql_cli import (
    mysql_container_connection_args,
    mysql_exec_password_env,
)
from controlbox.shared.infrastructure.platform_env_file import read_env_key

logger = logging.getLogger("controlbox.mysql.sync")

MYSQL_CONTAINER = "controlbox-mysql"
MYSQL_IMAGE = "mysql:8.4"

_RESYNC_LOCK = asyncio.Lock()


def resolve_mysql_admin_password(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    config_dir = settings.platform_config_dir
    if config_dir:
        from_file = read_env_key(Path(config_dir) / "platform.env", "MYSQL_ADMIN_PASSWORD")
        if from_file:
            return from_file
    return settings.mysql_admin_password


def mysql_data_dir_on_host(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    data_dir = settings.controlbox_data_dir.strip("/")
    host_root = settings.host_root_path.rstrip("/")
    if host_root:
        return Path(f"{host_root}/{data_dir}/mysql")
    return Path(f"/{data_dir}/mysql")


def mysql_data_dir_for_docker_mount(settings: Settings | None = None) -> str:
    """Host path for docker run -v (strip /host/root prefix used inside the API container)."""
    path = mysql_data_dir_on_host(settings)
    host_root = (settings or get_settings()).host_root_path.rstrip("/")
    if host_root and path.as_posix().startswith(f"{host_root}/"):
        return "/" + path.as_posix()[len(host_root) + 1 :]
    return path.as_posix()


async def mysql_probe_root(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    password = resolve_mysql_admin_password(settings)
    code, _, _ = await docker_exec(
        MYSQL_CONTAINER,
        [
            "mysql",
            *mysql_container_connection_args(settings.mysql_port, "root", password),
            "-e",
            "SELECT 1",
        ],
        settings=settings,
        env=mysql_exec_password_env(password),
    )
    return code == 0


async def mysql_resync_root_password(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    password = resolve_mysql_admin_password(settings)
    mount_path = mysql_data_dir_for_docker_mount(settings)
    data_path = mysql_data_dir_on_host(settings)

    if not data_path.is_dir():
        raise RuntimeError(
            f"Directorio MySQL no encontrado ({data_path}). "
            "Active el perfil databases y ejecute controlbox repair."
        )

    logger.warning(
        "Resincronizando contraseña root de MySQL con platform.env (volumen en %s)",
        mount_path,
    )

    env = docker_env(settings)
    await spawn(["docker", "stop", MYSQL_CONTAINER], env=env)

    sql_pass = password.replace("\\", "\\\\").replace("'", "''")
    reset_script = f"""
set -e
mysqld --user=mysql --skip-grant-tables --skip-networking &
pid=$!
for i in $(seq 1 90); do
  if mysqladmin ping --silent 2>/dev/null; then break; fi
  sleep 1
done
mysql -e "FLUSH PRIVILEGES;"
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '{sql_pass}';"
mysql -e "CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '{sql_pass}';"
mysql -e "ALTER USER 'root'@'%' IDENTIFIED BY '{sql_pass}';"
mysql -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;"
mysql -e "FLUSH PRIVILEGES;"
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
"""

    code, _, stderr = await spawn(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{mount_path}:/var/lib/mysql:rw",
            "--entrypoint",
            "bash",
            MYSQL_IMAGE,
            "-c",
            reset_script,
        ],
        env=env,
    )
    if code != 0:
        raise RuntimeError(
            f"No se pudo resincronizar la contraseña root de MySQL: {stderr.decode().strip()}"
        )

    await spawn(["docker", "start", MYSQL_CONTAINER], env=env)

    for _ in range(45):
        code, _, _ = await docker_exec(
            MYSQL_CONTAINER,
            ["mysqladmin", "ping", "-h", "127.0.0.1"],
            settings=settings,
        )
        if code == 0:
            break
        await asyncio.sleep(2)
    else:
        raise RuntimeError("MySQL no respondió tras resincronizar la contraseña root")


async def mysql_resync_root_password_if_needed(settings: Settings | None = None) -> bool:
    """Return True when a resync was performed."""
    settings = settings or get_settings()
    if await mysql_probe_root(settings):
        return False
    async with _RESYNC_LOCK:
        if await mysql_probe_root(settings):
            return False
        await mysql_resync_root_password(settings)
        if not await mysql_probe_root(settings):
            raise RuntimeError(
                "MySQL sigue rechazando root tras resincronizar. "
                "Revise MYSQL_ADMIN_PASSWORD en platform.env o ejecute controlbox repair."
            )
        return True
