import asyncio
import hashlib
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType, ManagedDatabase
from controlbox.modules.databases.infrastructure.engine_config import EngineConfigResolver, EngineConnection
from controlbox.shared.infrastructure.mysql_cli import mysql_connection_args
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


class MySqlMariaAdapter(DatabaseEngineAdapter):
    async def create_database(self, conn: EngineConnection, database_name: str, charset: str) -> None:
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
        cmd = [
            "mysql",
            *mysql_connection_args(conn.host, conn.port, conn.admin_user, conn.admin_password),
            database_name,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        data = input_path.read_bytes()
        _, stderr = await proc.communicate(input=data)
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def _execute(self, conn: EngineConnection, sql: str) -> None:
        cmd = [
            "mysql",
            *mysql_connection_args(conn.host, conn.port, conn.admin_user, conn.admin_password),
            "-e",
            sql,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def _run_dump(self, cmd: list[str], output_path: Path) -> None:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())
        output_path.write_bytes(stdout)


class PostgreSqlAdapter(DatabaseEngineAdapter):
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
        env = {"PGPASSWORD": conn.admin_password}
        cmd = ["psql", "-h", conn.host, "-p", str(conn.port), "-U", conn.admin_user, "-d", "postgres", "-c", sql]
        proc = await asyncio.create_subprocess_exec(*cmd, env={**dict(await self._base_env()), **env})
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def _base_env(self):
        import os
        return os.environ


class MsSqlAdapter(DatabaseEngineAdapter):
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
        cmd = [
            "/opt/mssql-tools18/bin/sqlcmd",
            "-S", f"{conn.host},{conn.port}",
            "-U", conn.admin_user,
            "-P", conn.admin_password,
            "-C",
            "-Q", sql,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
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
