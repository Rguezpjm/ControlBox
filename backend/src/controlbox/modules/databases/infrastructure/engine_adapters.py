import asyncio
import hashlib
import logging
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from controlbox.config.settings import get_settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType, ManagedDatabase
from controlbox.modules.databases.infrastructure.engine_config import EngineConfigResolver, EngineConnection
from controlbox.shared.infrastructure.db_engine_cli import docker_enabled, docker_exec, spawn
from controlbox.shared.infrastructure.docker.env import validate_container_name
from controlbox.shared.infrastructure.mysql_cli import (
    mysql_connection_args,
    mysql_container_connection_args,
    mysql_exec_password_env,
)
from controlbox.shared.infrastructure.mysql_root_sync import (
    mysql_resync_root_password_if_needed,
    resolve_mysql_admin_password,
)
from passlib.context import CryptContext

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class DatabaseEngineAdapter(ABC):
    @abstractmethod
    async def create_database(self, conn: EngineConnection, database_name: str, charset: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def drop_database(self, conn: EngineConnection, database_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_user(
        self,
        conn: EngineConnection,
        database_name: str,
        username: str,
        password: str,
        host: str,
        grants: list[str],
        max_connections: int,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def change_password(
        self,
        conn: EngineConnection,
        username: str,
        password: str,
        host: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def set_connection_limit(
        self,
        conn: EngineConnection,
        username: str,
        host: str,
        max_connections: int,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def drop_user(self, conn: EngineConnection, username: str, host: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def backup(self, conn: EngineConnection, database_name: str, output_path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    async def restore(self, conn: EngineConnection, database_name: str, input_path: Path) -> None:
        raise NotImplementedError


logger = logging.getLogger("controlbox.databases.mysql")

_PLATFORM_MYSQL_HOSTS = frozenset({
    "mysql",
    "mariadb",
    "controlbox-mysql",
    "controlbox-mariadb",
})

_MYSQL_PREP_LOCK = asyncio.Lock()
_MYSQL_PREPARED: set[str] = set()


class MySqlMariaAdapter(DatabaseEngineAdapter):
    def _container_name(self, conn: EngineConnection) -> str:
        host = conn.host.strip().lower().split(":")[0]
        if host in {"mariadb", "controlbox-mariadb"}:
            return "controlbox-mariadb"
        return "controlbox-mysql"

    def _use_container_exec(self, conn: EngineConnection) -> bool:
        if docker_enabled():
            return True
        host = conn.host.strip().lower().split(":")[0]
        return host in _PLATFORM_MYSQL_HOSTS

    def _conn_with_platform_password(self, conn: EngineConnection) -> EngineConnection:
        password = resolve_mysql_admin_password()
        if password == conn.admin_password:
            return conn
        return EngineConnection(
            host=conn.host,
            port=conn.port,
            admin_user=conn.admin_user,
            admin_password=password,
        )

    async def ensure_admin_access(self, conn: EngineConnection) -> None:
        conn = self._conn_with_platform_password(conn)
        key = self._container_name(conn)
        async with _MYSQL_PREP_LOCK:
            if key in _MYSQL_PREPARED:
                return
            await self._ensure_remote_root(conn)
            _MYSQL_PREPARED.add(key)

    @staticmethod
    def _sql_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "''")

    async def create_database(self, conn: EngineConnection, database_name: str, charset: str) -> None:
        conn = self._conn_with_platform_password(conn)
        await self.ensure_admin_access(conn)
        sql = f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET {charset} COLLATE {charset}_unicode_ci"
        await self._execute(conn, sql)

    async def drop_database(self, conn: EngineConnection, database_name: str) -> None:
        await self._execute(conn, f"DROP DATABASE IF EXISTS `{database_name}`")

    async def create_user(
        self,
        conn: EngineConnection,
        database_name: str,
        username: str,
        password: str,
        host: str,
        grants: list[str],
        max_connections: int,
    ) -> None:
        await self._execute(conn, f"CREATE USER IF NOT EXISTS '{username}'@'{host}' IDENTIFIED BY '{password}'")
        await self._execute(conn, f"ALTER USER '{username}'@'{host}' WITH MAX_USER_CONNECTIONS {max_connections}")
        for grant in grants or ["ALL PRIVILEGES"]:
            await self._execute(conn, f"GRANT {grant} ON `{database_name}`.* TO '{username}'@'{host}'")
        await self._execute(conn, "FLUSH PRIVILEGES")

    async def change_password(self, conn: EngineConnection, username: str, password: str, host: str) -> None:
        await self._execute(conn, f"ALTER USER '{username}'@'{host}' IDENTIFIED BY '{password}'")

    async def set_connection_limit(self, conn: EngineConnection, username: str, host: str, max_connections: int) -> None:
        await self._execute(conn, f"ALTER USER '{username}'@'{host}' WITH MAX_USER_CONNECTIONS {max_connections}")

    async def drop_user(self, conn: EngineConnection, username: str, host: str) -> None:
        await self._execute(conn, f"DROP USER IF EXISTS '{username}'@'{host}'")

    async def backup(self, conn: EngineConnection, database_name: str, output_path: Path) -> None:
        cmd = [
            "mysqldump",
            *mysql_connection_args(conn.host, conn.port, conn.admin_user, conn.admin_password),
            "--single-transaction",
            "--routines",
            "--triggers",
            database_name,
        ]
        await self._run_dump(cmd, output_path)

    async def restore(self, conn: EngineConnection, database_name: str, input_path: Path) -> None:
        data = input_path.read_bytes()
        if docker_enabled():
            container = validate_container_name(self._container_name(conn))
            code, _, stderr = await docker_exec(
                container,
                [
                    "mysql",
                    *mysql_container_connection_args(conn.port, conn.admin_user, conn.admin_password),
                    database_name,
                ],
                env=mysql_exec_password_env(conn.admin_password),
                input_data=data,
            )
            if code != 0:
                raise RuntimeError(stderr.decode())
            return
        cmd = [
            "mysql",
            *mysql_connection_args(conn.host, conn.port, conn.admin_user, conn.admin_password),
            database_name,
        ]
        code, _, stderr = await spawn(cmd, input_data=data)
        if code != 0:
            raise RuntimeError(stderr.decode())

    async def _execute(self, conn: EngineConnection, sql: str) -> None:
        if self._use_container_exec(conn):
            try:
                await self._execute_via_container(conn, sql)
                return
            except RuntimeError as exc:
                if not self._is_access_denied(str(exc)):
                    raise
                await self._ensure_remote_root(conn)
                await self._execute_via_container(conn, sql)
                return

        err = await self._run_mysql_cli(conn, sql)
        if err is None:
            return
        if self._is_access_denied(err):
            await self._ensure_remote_root(conn)
            if self._use_container_exec(conn):
                await self._execute_via_container(conn, sql)
                return
            err = await self._run_mysql_cli(conn, sql)
            if err is None:
                return
        raise RuntimeError(err)

    def _is_access_denied(self, err: str) -> bool:
        lowered = err.lower()
        return "1045" in err or "access denied" in lowered

    async def _run_mysql_cli(self, conn: EngineConnection, sql: str) -> str | None:
        cmd = [
            "mysql",
            *mysql_connection_args(conn.host, conn.port, conn.admin_user, conn.admin_password),
            "-e",
            sql,
        ]
        try:
            code, _, stderr = await spawn(cmd)
        except RuntimeError:
            if docker_enabled():
                await self._execute_via_container(conn, sql)
                return None
            raise
        if code != 0:
            return stderr.decode()
        return None

    async def _execute_via_container(self, conn: EngineConnection, sql: str) -> None:
        conn = self._conn_with_platform_password(conn)
        container = validate_container_name(self._container_name(conn))
        code, _, stderr = await docker_exec(
            container,
            [
                "mysql",
                *mysql_container_connection_args(conn.port, conn.admin_user, conn.admin_password),
                "-e",
                sql,
            ],
            env=mysql_exec_password_env(conn.admin_password),
        )
        if code != 0:
            message = stderr.decode().strip()
            lowered = message.lower()
            if "no such container" in lowered or "is not running" in lowered:
                raise RuntimeError(
                    f"Contenedor {container} no está en ejecución. "
                    "Active MySQL en Configuración del servidor y ejecute controlbox repair."
                )
            raise RuntimeError(message or f"Error ejecutando SQL en {container}")

    async def _ensure_remote_root(self, conn: EngineConnection) -> None:
        if conn.admin_user != "root":
            return
        conn = self._conn_with_platform_password(conn)
        message = await self._run_remote_root_sql(conn)
        if message is None:
            return
        if not self._is_access_denied(message):
            raise RuntimeError(message)

        logger.warning("MySQL root access denied; resyncing password from platform.env")
        key = self._container_name(conn)
        if await mysql_resync_root_password_if_needed():
            _MYSQL_PREPARED.discard(key)

        message = await self._run_remote_root_sql(conn)
        if message is None:
            return
        if self._is_access_denied(message):
            raise RuntimeError(
                f"MySQL rechazó root (revise MYSQL_ADMIN_PASSWORD en platform.env). {message}"
            )
        raise RuntimeError(message)

    async def _run_remote_root_sql(self, conn: EngineConnection) -> str | None:
        escaped = self._sql_escape(conn.admin_password)
        sql = (
            f"CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '{escaped}'; "
            f"ALTER USER 'root'@'%' IDENTIFIED BY '{escaped}'; "
            "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; "
            f"CREATE USER IF NOT EXISTS 'root'@'localhost' IDENTIFIED BY '{escaped}'; "
            f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{escaped}'; "
            "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION; "
            "FLUSH PRIVILEGES;"
        )
        container = validate_container_name(self._container_name(conn))
        code, _, stderr = await docker_exec(
            container,
            [
                "mysql",
                *mysql_container_connection_args(conn.port, conn.admin_user, conn.admin_password),
                "-e",
                sql,
            ],
            env=mysql_exec_password_env(conn.admin_password),
        )
        if code == 0:
            return None
        message = stderr.decode().strip()
        logger.warning("Could not ensure root@%% on %s: %s", container, message)
        return message

    async def _run_dump(self, cmd: list[str], output_path: Path) -> None:
        code, stdout, stderr = await spawn(cmd)
        if code != 0:
            raise RuntimeError(stderr.decode())
        output_path.write_bytes(stdout)


class PostgreSqlAdapter(DatabaseEngineAdapter):
    _CONTAINER = "controlbox-managed-postgres"

    def _use_container(self, conn: EngineConnection) -> bool:
        if not docker_enabled():
            return False
        host = conn.host.strip().lower()
        return host in {"managed-postgres", "controlbox-managed-postgres", "postgres"}

    async def create_database(self, conn: EngineConnection, database_name: str, charset: str) -> None:
        await self._execute(conn, f'CREATE DATABASE "{database_name}" ENCODING \'{charset}\'')

    async def drop_database(self, conn: EngineConnection, database_name: str) -> None:
        await self._execute(conn, f'DROP DATABASE IF EXISTS "{database_name}"')

    async def create_user(
        self,
        conn: EngineConnection,
        database_name: str,
        username: str,
        password: str,
        host: str,
        grants: list[str],
        max_connections: int,
    ) -> None:
        await self._execute(conn, f"CREATE USER \"{username}\" WITH PASSWORD '{password}' CONNECTION LIMIT {max_connections}")
        await self._execute(conn, f'GRANT ALL PRIVILEGES ON DATABASE "{database_name}" TO "{username}"')

    async def change_password(self, conn: EngineConnection, username: str, password: str, host: str) -> None:
        await self._execute(conn, f"ALTER USER \"{username}\" WITH PASSWORD '{password}'")

    async def set_connection_limit(self, conn: EngineConnection, username: str, host: str, max_connections: int) -> None:
        await self._execute(conn, f"ALTER USER \"{username}\" CONNECTION LIMIT {max_connections}")

    async def drop_user(self, conn: EngineConnection, username: str, host: str) -> None:
        await self._execute(conn, f'DROP USER IF EXISTS "{username}"')

    async def backup(self, conn: EngineConnection, database_name: str, output_path: Path) -> None:
        env = {"PGPASSWORD": conn.admin_password}
        cmd = [
            "pg_dump",
            "-h", conn.host,
            "-p", str(conn.port),
            "-U", conn.admin_user,
            "-Fc",
            "-f", str(output_path),
            database_name,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, env={**dict(await self._base_env()), **env})
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def restore(self, conn: EngineConnection, database_name: str, input_path: Path) -> None:
        env = {"PGPASSWORD": conn.admin_password}
        cmd = [
            "pg_restore",
            "-h", conn.host,
            "-p", str(conn.port),
            "-U", conn.admin_user,
            "-d", database_name,
            "--clean",
            "--if-exists",
            str(input_path),
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, env={**dict(await self._base_env()), **env})
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def _execute(self, conn: EngineConnection, sql: str) -> None:
        if self._use_container(conn):
            code, _, stderr = await docker_exec(
                validate_container_name(self._CONTAINER),
                ["psql", "-U", conn.admin_user, "-d", "postgres", "-c", sql],
                env={"PGPASSWORD": conn.admin_password},
            )
            if code != 0:
                raise RuntimeError(stderr.decode())
            return

        env = {**dict(await self._base_env()), "PGPASSWORD": conn.admin_password}
        cmd = ["psql", "-h", conn.host, "-p", str(conn.port), "-U", conn.admin_user, "-d", "postgres", "-c", sql]
        code, _, stderr = await spawn(cmd, env=env)
        if code != 0:
            raise RuntimeError(stderr.decode())

    async def _base_env(self):
        import os
        return os.environ


class MsSqlAdapter(DatabaseEngineAdapter):
    _CONTAINER = "controlbox-mssql"
    _SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"

    def _sqlcmd_args(self, conn: EngineConnection, sql: str, *, local: bool) -> list[str]:
        host = "localhost,1433" if local else f"{conn.host},{conn.port}"
        return [
            self._SQLCMD,
            "-S", host,
            "-U", conn.admin_user,
            "-P", conn.admin_password,
            "-C",
            "-Q", sql,
        ]

    async def create_database(self, conn: EngineConnection, database_name: str, charset: str) -> None:
        await self._execute(conn, f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{database_name}') CREATE DATABASE [{database_name}]")

    async def drop_database(self, conn: EngineConnection, database_name: str) -> None:
        await self._execute(conn, f"DROP DATABASE IF EXISTS [{database_name}]")

    async def create_user(
        self,
        conn: EngineConnection,
        database_name: str,
        username: str,
        password: str,
        host: str,
        grants: list[str],
        max_connections: int,
    ) -> None:
        await self._execute(conn, f"USE [{database_name}]; IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = N'{username}') CREATE USER [{username}] WITH PASSWORD = N'{password}'; ALTER ROLE db_owner ADD MEMBER [{username}]")

    async def change_password(self, conn: EngineConnection, username: str, password: str, host: str) -> None:
        await self._execute(conn, f"ALTER USER [{username}] WITH PASSWORD = N'{password}'")

    async def set_connection_limit(self, conn: EngineConnection, username: str, host: str, max_connections: int) -> None:
        return None

    async def drop_user(self, conn: EngineConnection, username: str, host: str) -> None:
        await self._execute(conn, f"DROP USER IF EXISTS [{username}]")

    async def backup(self, conn: EngineConnection, database_name: str, output_path: Path) -> None:
        backup_file = str(output_path).replace("/", "\\")
        await self._execute(conn, f"BACKUP DATABASE [{database_name}] TO DISK = N'{backup_file}' WITH FORMAT")

    async def restore(self, conn: EngineConnection, database_name: str, input_path: Path) -> None:
        backup_file = str(input_path).replace("/", "\\")
        await self._execute(conn, f"RESTORE DATABASE [{database_name}] FROM DISK = N'{backup_file}' WITH REPLACE")

    async def _execute(self, conn: EngineConnection, sql: str) -> None:
        if docker_enabled():
            code, _, stderr = await docker_exec(
                validate_container_name(self._CONTAINER),
                self._sqlcmd_args(conn, sql, local=True),
            )
            if code != 0:
                message = stderr.decode().strip()
                lowered = message.lower()
                if "no such container" in lowered or "is not running" in lowered:
                    raise RuntimeError(
                        f"Contenedor {self._CONTAINER} no está en ejecución. "
                        "Active el perfil databases con SQL Server o use MySQL."
                    )
                raise RuntimeError(message or "Error ejecutando SQL en SQL Server")
            return

        code, _, stderr = await spawn(self._sqlcmd_args(conn, sql, local=False))
        if code != 0:
            raise RuntimeError(stderr.decode())


class EngineAdapterFactory:
    @staticmethod
    def get(engine: DatabaseEngineType) -> DatabaseEngineAdapter:
        if engine in (DatabaseEngineType.MYSQL, DatabaseEngineType.MARIADB):
            return MySqlMariaAdapter()
        if engine == DatabaseEngineType.POSTGRESQL:
            return PostgreSqlAdapter()
        if engine == DatabaseEngineType.MSSQL:
            return MsSqlAdapter()
        raise ValueError(f"No adapter for {engine}")


def generate_password() -> str:
    return secrets.token_urlsafe(24)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def compute_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
