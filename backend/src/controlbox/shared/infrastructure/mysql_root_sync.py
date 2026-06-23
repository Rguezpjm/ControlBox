"""Resync MySQL root password with platform.env when the data volume holds a different secret."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path

from controlbox.config.settings import Settings, get_settings
from controlbox.shared.infrastructure.db_engine_cli import docker_env, docker_exec, spawn
from controlbox.shared.infrastructure.mysql_cli import (
    mysql_container_connection_args,
    mysql_exec_password_env,
)
from controlbox.shared.infrastructure.platform_env_file import (
    patch_env_key,
    read_env_key,
    repair_duplicate_env_keys,
)

logger = logging.getLogger("controlbox.mysql.sync")

MYSQL_CONTAINER = "controlbox-mysql"
MYSQL_IMAGE = "mysql:8.4"

_RESYNC_LOCK = asyncio.Lock()


def _sql_escape_password(password: str) -> str:
    return password.replace("\\", "\\\\").replace("'", "''")


def resolve_host_data_dir(settings: Settings | None = None) -> Path:
    """Host path for CONTROLBOX_DATA_DIR (never under /host/root inside the API container)."""
    settings = settings or get_settings()
    config_dir = settings.platform_config_dir
    if config_dir:
        raw = read_env_key(Path(config_dir) / "platform.env", "CONTROLBOX_DATA_DIR")
        if raw:
            if raw.startswith("/host/root"):
                return Path(raw.removeprefix("/host/root") or "/")
            if not raw.startswith("/host/"):
                return Path(raw)

    raw = (settings.controlbox_data_dir or "/var/lib/controlbox").strip()
    if raw.startswith("/host/root"):
        return Path(raw.removeprefix("/host/root") or "/")
    if raw.startswith("/host/"):
        return Path("/var/lib/controlbox")
    return Path(raw)


def resolve_mysql_admin_password(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    config_dir = settings.platform_config_dir
    if config_dir:
        from_file = read_env_key(Path(config_dir) / "platform.env", "MYSQL_ADMIN_PASSWORD")
        if from_file:
            return from_file
    return settings.mysql_admin_password


def mysql_password_candidates(settings: Settings | None = None) -> list[str]:
    """Unique passwords to try, most likely correct first."""
    settings = settings or get_settings()
    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: str | None) -> None:
        if not value or value in seen:
            return
        seen.add(value)
        ordered.append(value)

    add(resolve_mysql_admin_password(settings))
    add(settings.mysql_admin_password)

    config_dir = settings.platform_config_dir
    if config_dir:
        env_file = Path(config_dir) / "platform.env"
        if env_file.is_file():
            prefix = "MYSQL_ADMIN_PASSWORD="
            from controlbox.shared.infrastructure.platform_env_file import parse_env_value

            for line in reversed(env_file.read_text(encoding="utf-8").splitlines()):
                if line.startswith(prefix):
                    add(parse_env_value(line[len(prefix) :]))

    return ordered


async def mysql_data_mount_path(settings: Settings | None = None) -> str:
    """Absolute host path bound to /var/lib/mysql in controlbox-mysql."""
    settings = settings or get_settings()
    code, stdout, _ = await spawn(
        [
            "docker",
            "inspect",
            "-f",
            '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Source}}{{end}}{{end}}',
            MYSQL_CONTAINER,
        ],
        env=docker_env(settings),
    )
    mount = stdout.decode("utf-8", errors="replace").strip()
    if code == 0 and mount:
        return mount

    return str(resolve_host_data_dir(settings) / "mysql")


async def _read_container_mysql_root_password(settings: Settings) -> str | None:
    code, stdout, _ = await spawn(
        [
            "docker",
            "inspect",
            "-f",
            "{{range .Config.Env}}{{println .}}{{end}}",
            MYSQL_CONTAINER,
        ],
        env=docker_env(settings),
    )
    if code != 0:
        return None
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        if line.startswith("MYSQL_ROOT_PASSWORD="):
            return line.split("=", 1)[1]
    return None


async def mysql_probe_root_password(password: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
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


async def mysql_probe_root(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    for password in mysql_password_candidates(settings):
        if await mysql_probe_root_password(password, settings):
            return True
    container_password = await _read_container_mysql_root_password(settings)
    if container_password and container_password not in mysql_password_candidates(settings):
        return await mysql_probe_root_password(container_password, settings)
    return False


async def mysql_sync_working_password(settings: Settings | None = None) -> str | None:
    """If any known candidate authenticates, persist it as MYSQL_ADMIN_PASSWORD."""
    settings = settings or get_settings()
    env_file = Path(settings.platform_config_dir) / "platform.env" if settings.platform_config_dir else None

    for password in mysql_password_candidates(settings):
        if await mysql_probe_root_password(password, settings):
            if env_file and env_file.is_file():
                current = read_env_key(env_file, "MYSQL_ADMIN_PASSWORD")
                if current != password:
                    patch_env_key(env_file, "MYSQL_ADMIN_PASSWORD", password)
                    logger.info("MYSQL_ADMIN_PASSWORD alineado con credencial MySQL funcional")
            return password

    container_password = await _read_container_mysql_root_password(settings)
    if container_password and await mysql_probe_root_password(container_password, settings):
        if env_file and env_file.is_file():
            patch_env_key(env_file, "MYSQL_ADMIN_PASSWORD", container_password)
            logger.info("MYSQL_ADMIN_PASSWORD sincronizado desde contenedor MySQL")
        return container_password

    return None


async def mysql_resync_root_password(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.platform_config_dir:
        env_file = Path(settings.platform_config_dir) / "platform.env"
        if env_file.is_file():
            repair_duplicate_env_keys(env_file)

    password = resolve_mysql_admin_password(settings)
    mount_path = await mysql_data_mount_path(settings)

    inspect_code, _, _ = await spawn(
        ["docker", "inspect", MYSQL_CONTAINER],
        env=docker_env(settings),
    )
    if inspect_code != 0:
        raise RuntimeError(
            "Contenedor controlbox-mysql no encontrado. "
            "Active el perfil databases en Configuración y ejecute controlbox repair."
        )

    logger.warning(
        "Resincronizando contraseña root de MySQL con platform.env (volumen en %s)",
        mount_path,
    )

    sql_pass = _sql_escape_password(password)
    reset_sql = "\n".join(
        [
            "FLUSH PRIVILEGES;",
            f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{sql_pass}';",
            "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;",
            f"CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '{sql_pass}';",
            f"ALTER USER 'root'@'%' IDENTIFIED BY '{sql_pass}';",
            "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;",
            f"CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '{sql_pass}';",
            f"ALTER USER 'root'@'127.0.0.1' IDENTIFIED BY '{sql_pass}';",
            "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;",
            "FLUSH PRIVILEGES;",
        ]
    )
    sql_b64 = base64.b64encode(reset_sql.encode("utf-8")).decode("ascii")

    reset_script = f"""set -e
mysqld --user=mysql --skip-grant-tables --skip-networking &
pid=$!
ready=0
for i in $(seq 1 90); do
  if mysqladmin ping --silent 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" != "1" ]; then
  echo "MySQL no arrancó en modo skip-grant-tables" >&2
  exit 1
fi
echo {sql_b64} | base64 -d | mysql -uroot --protocol=socket
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
"""

    env = docker_env(settings)
    await spawn(["docker", "stop", MYSQL_CONTAINER], env=env)

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
        await spawn(["docker", "start", MYSQL_CONTAINER], env=env)
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"No se pudo resincronizar la contraseña root de MySQL en {mount_path}: {detail}"
        )

    await spawn(["docker", "start", MYSQL_CONTAINER], env=env)

    for _ in range(45):
        if await mysql_probe_root_password(password, settings):
            return
        await asyncio.sleep(2)

    raise RuntimeError("MySQL no aceptó la contraseña de platform.env tras resincronizar")


async def mysql_resync_root_password_if_needed(settings: Settings | None = None) -> bool:
    """Return True when a resync was performed."""
    settings = settings or get_settings()
    working = await mysql_sync_working_password(settings)
    if working is not None:
        return False

    if await mysql_probe_root(settings):
        return False

    async with _RESYNC_LOCK:
        working = await mysql_sync_working_password(settings)
        if working is not None:
            return False
        if await mysql_probe_root(settings):
            return False
        await mysql_resync_root_password(settings)
        if not await mysql_probe_root_password(resolve_mysql_admin_password(settings), settings):
            raise RuntimeError(
                "MySQL sigue rechazando root tras resincronizar. "
                "Revise MYSQL_ADMIN_PASSWORD en platform.env o ejecute controlbox repair."
            )
        return True
