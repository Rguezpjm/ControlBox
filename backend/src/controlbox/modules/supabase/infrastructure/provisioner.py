import asyncio
import os
import secrets
import time
from dataclasses import dataclass

import httpx
from jose import jwt

from controlbox.config.settings import Settings
from controlbox.modules.supabase.domain.entities import (
    RlsPolicyAction,
    SupabaseBucket,
    SupabaseProject,
    SupabaseRealtimeChannel,
    SupabaseRlsPolicy,
)


@dataclass(frozen=True)
class SupabaseConnection:
    host: str
    port: int
    admin_user: str
    admin_password: str


class SupabaseProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn = SupabaseConnection(
            host=settings.supabase_db_host,
            port=settings.supabase_db_port,
            admin_user=settings.supabase_db_admin_user,
            admin_password=settings.supabase_db_admin_password,
        )

    def generate_password(self) -> str:
        return secrets.token_urlsafe(24)

    def generate_keys(self, project_ref: str, tenant_id: str) -> tuple[str, str]:
        now = int(time.time())
        exp = now + 60 * 60 * 24 * 365 * 10
        base_claims = {
            "iss": "supabase",
            "iat": now,
            "exp": exp,
            "ref": project_ref,
            "tenant_id": tenant_id,
        }
        anon = jwt.encode(
            {**base_claims, "role": "anon"},
            self._settings.supabase_jwt_secret,
            algorithm="HS256",
        )
        service = jwt.encode(
            {**base_claims, "role": "service_role"},
            self._settings.supabase_jwt_secret,
            algorithm="HS256",
        )
        return anon, service

    async def provision_project(
        self,
        project: SupabaseProject,
        database_password: str,
    ) -> None:
        await self._execute(
            f'CREATE DATABASE "{project.database_name}" ENCODING \'UTF8\'',
        )
        await self._execute(
            f"CREATE USER \"{project.database_user}\" WITH PASSWORD '{database_password}' "
            f"CONNECTION LIMIT 50",
        )
        await self._execute(
            f'GRANT ALL PRIVILEGES ON DATABASE "{project.database_name}" TO "{project.database_user}"',
        )
        await self._execute_on_db(
            project.database_name,
            f'GRANT ALL ON SCHEMA public TO "{project.database_user}"',
        )
        await self._execute_on_db(
            project.database_name,
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{project.database_user}"',
        )
        await self._execute_on_db(
            project.database_name,
            "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"",
        )
        await self._execute_on_db(
            project.database_name,
            "CREATE EXTENSION IF NOT EXISTS pgcrypto",
        )
        await self._execute_on_db(
            project.database_name,
            f'ALTER DATABASE "{project.database_name}" OWNER TO "{project.database_user}"',
        )

    async def create_schema(self, project: SupabaseProject, schema_name: str) -> None:
        await self._execute_on_db(
            project.database_name,
            f'CREATE SCHEMA IF NOT EXISTS "{schema_name}" AUTHORIZATION "{project.database_user}"',
        )

    async def drop_schema(self, project: SupabaseProject, schema_name: str) -> None:
        await self._execute_on_db(
            project.database_name,
            f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE',
        )

    async def apply_rls_policy(self, project: SupabaseProject, policy: SupabaseRlsPolicy) -> None:
        table = f'"{policy.schema_name}"."{policy.table_name}"'
        policy_name = f"cb_{policy.name}"[:63]
        await self._execute_on_db(project.database_name, f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        await self._execute_on_db(
            project.database_name,
            f'DROP POLICY IF EXISTS "{policy_name}" ON {table}',
        )
        action = policy.action.value if policy.action != RlsPolicyAction.ALL else "ALL"
        check_clause = ""
        if policy.check_expression:
            check_clause = f" WITH CHECK ({policy.check_expression})"
        await self._execute_on_db(
            project.database_name,
            f'CREATE POLICY "{policy_name}" ON {table} FOR {action} TO {policy.role_name} '
            f"USING ({policy.using_expression}){check_clause}",
        )

    async def remove_rls_policy(self, project: SupabaseProject, policy: SupabaseRlsPolicy) -> None:
        table = f'"{policy.schema_name}"."{policy.table_name}"'
        policy_name = f"cb_{policy.name}"[:63]
        await self._execute_on_db(
            project.database_name,
            f'DROP POLICY IF EXISTS "{policy_name}" ON {table}',
        )

    async def setup_realtime_channel(self, project: SupabaseProject, channel: SupabaseRealtimeChannel) -> None:
        pub_name = f"cb_{project.project_ref}_{channel.name}"[:63]
        table = f'"{channel.schema_name}"."{channel.table_name}"'
        await self._execute_on_db(project.database_name, "CREATE PUBLICATION IF NOT EXISTS supabase_realtime")
        await self._execute_on_db(
            project.database_name,
            f'ALTER PUBLICATION supabase_realtime ADD TABLE {table}',
        )

    async def remove_realtime_channel(self, project: SupabaseProject, channel: SupabaseRealtimeChannel) -> None:
        table = f'"{channel.schema_name}"."{channel.table_name}"'
        await self._execute_on_db(
            project.database_name,
            f'ALTER PUBLICATION supabase_realtime DROP TABLE {table}',
        )

    async def suspend_project(self, project: SupabaseProject) -> None:
        await self._execute(
            f'ALTER USER "{project.database_user}" CONNECTION LIMIT 0',
        )
        await self._execute(
            f'REVOKE CONNECT ON DATABASE "{project.database_name}" FROM "{project.database_user}"',
        )

    async def resume_project(self, project: SupabaseProject) -> None:
        await self._execute(
            f'GRANT CONNECT ON DATABASE "{project.database_name}" TO "{project.database_user}"',
        )
        await self._execute(
            f'ALTER USER "{project.database_user}" CONNECTION LIMIT 50',
        )

    async def deprovision_project(self, project: SupabaseProject) -> None:
        await self._execute(
            f'REVOKE CONNECT ON DATABASE "{project.database_name}" FROM PUBLIC',
        )
        await self._execute(
            f'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = \'{project.database_name}\'',
        )
        await self._execute(f'DROP DATABASE IF EXISTS "{project.database_name}"')
        await self._execute(f'DROP USER IF EXISTS "{project.database_user}"')

    async def get_database_size_mb(self, database_name: str) -> int:
        sql = (
            f"SELECT pg_database_size('{database_name}') AS size"
        )
        result = await self._query(sql)
        for line in result.splitlines():
            if line.strip().isdigit():
                return max(1, int(line.strip()) // (1024 * 1024))
        return 0

    async def _execute(self, sql: str) -> None:
        env = {"PGPASSWORD": self._conn.admin_password}
        cmd = [
            "psql",
            "-h", self._conn.host,
            "-p", str(self._conn.port),
            "-U", self._conn.admin_user,
            "-d", "postgres",
            "-c", sql,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env={**os.environ, **env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def _execute_on_db(self, database_name: str, sql: str) -> None:
        env = {"PGPASSWORD": self._conn.admin_password}
        cmd = [
            "psql",
            "-h", self._conn.host,
            "-p", str(self._conn.port),
            "-U", self._conn.admin_user,
            "-d", database_name,
            "-c", sql,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env={**os.environ, **env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())

    async def _query(self, sql: str) -> str:
        env = {"PGPASSWORD": self._conn.admin_password}
        cmd = [
            "psql",
            "-h", self._conn.host,
            "-p", str(self._conn.port),
            "-U", self._conn.admin_user,
            "-d", "postgres",
            "-t", "-A",
            "-c", sql,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env={**os.environ, **env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode())
        return stdout.decode()


class SupabaseStorageClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.supabase_storage_url.rstrip("/")
        self._service_key = settings.supabase_service_key

    async def create_bucket(self, bucket: SupabaseBucket, project: SupabaseProject) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/bucket",
                headers={
                    "Authorization": f"Bearer {project.service_role_key}",
                    "apikey": project.service_role_key,
                    "Content-Type": "application/json",
                },
                json={
                    "id": bucket.name,
                    "name": bucket.name,
                    "public": bucket.public,
                    "file_size_limit": bucket.file_size_limit_mb * 1024 * 1024,
                },
            )
            if response.status_code not in (200, 201) and response.status_code != 409:
                raise RuntimeError(f"Storage API error: {response.text}")

    async def delete_bucket(self, bucket_name: str, project: SupabaseProject) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(
                f"{self._base_url}/bucket/{bucket_name}",
                headers={
                    "Authorization": f"Bearer {project.service_role_key}",
                    "apikey": project.service_role_key,
                },
            )
            if response.status_code not in (200, 204, 404):
                raise RuntimeError(f"Storage API error: {response.text}")

    async def list_buckets(self, project: SupabaseProject) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/bucket",
                headers={
                    "Authorization": f"Bearer {project.service_role_key}",
                    "apikey": project.service_role_key,
                },
            )
            if response.status_code != 200:
                return []
            return response.json()
