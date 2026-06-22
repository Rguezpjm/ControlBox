from dataclasses import dataclass
from uuid import UUID

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.supabase.application.queries import (
    GetSupabaseCredentialsQuery,
    GetSupabaseProjectQuery,
    GetSupabaseUsageQuery,
    ListSupabaseBucketsQuery,
    ListSupabaseProjectsQuery,
    ListSupabaseRealtimeChannelsQuery,
    ListSupabaseRlsPoliciesQuery,
    ListSupabaseSchemasQuery,
)
from controlbox.modules.supabase.domain.entities import (
    SupabaseBucket,
    SupabaseProject,
    SupabaseRealtimeChannel,
    SupabaseRlsPolicy,
    SupabaseSchema,
)
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.modules.supabase.infrastructure.provisioner import SupabaseProvisioner, SupabaseStorageClient
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


@dataclass
class SupabaseCredentials:
    database_name: str
    database_user: str
    database_password: str
    anon_key: str
    service_role_key: str
    api_url: str
    studio_url: str
    connection_url: str


@dataclass
class SupabaseUsage:
    database_size_mb: int
    storage_used_mb: int
    buckets_count: int
    schemas_count: int
    realtime_channels_count: int
    rls_policies_count: int
    requests_count: int


class ListSupabaseProjectsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSupabaseProjectsQuery) -> list[SupabaseProject]:
        async with self._uow:
            return await self._uow.supabase_projects.list_by_tenant(
                query.tenant_id, query.limit, query.offset
            )


class GetSupabaseProjectHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetSupabaseProjectQuery) -> SupabaseProject:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")
            return project


class GetSupabaseCredentialsHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._encryptor = SecretEncryptor(self._settings)

    async def handle(self, query: GetSupabaseCredentialsQuery) -> SupabaseCredentials:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")

            password = self._encryptor.decrypt(project.database_password_encrypted)
            host = self._settings.supabase_db_host
            port = self._settings.supabase_db_port
            connection_url = (
                f"postgresql://{project.database_user}:{password}@{host}:{port}/{project.database_name}"
            )

            return SupabaseCredentials(
                database_name=project.database_name,
                database_user=project.database_user,
                database_password=password,
                anon_key=project.anon_key,
                service_role_key=project.service_role_key,
                api_url=project.api_url,
                studio_url=project.studio_url,
                connection_url=connection_url,
            )


class GetSupabaseUsageHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = SupabaseProvisioner(self._settings)
        self._storage = SupabaseStorageClient(self._settings)

    async def handle(self, query: GetSupabaseUsageQuery) -> SupabaseUsage:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")

            try:
                db_size = await self._provisioner.get_database_size_mb(project.database_name)
            except Exception:
                db_size = project.database_size_mb

            buckets = await self._uow.supabase_buckets.list_by_project(project.id)
            schemas = await self._uow.supabase_schemas.list_by_project(project.id)
            channels = await self._uow.supabase_realtime_channels.list_by_project(project.id)
            policies = await self._uow.supabase_rls_policies.list_by_project(project.id)

            storage_mb = sum(b.size_mb for b in buckets)
            project.database_size_mb = db_size
            project.storage_used_mb = storage_mb
            await self._uow.supabase_projects.save(project)
            await self._uow.commit()

            return SupabaseUsage(
                database_size_mb=db_size,
                storage_used_mb=storage_mb,
                buckets_count=len(buckets),
                schemas_count=len(schemas),
                realtime_channels_count=len(channels),
                rls_policies_count=len(policies),
                requests_count=project.requests_count,
            )


class ListSupabaseSchemasHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSupabaseSchemasQuery) -> list[SupabaseSchema]:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")
            return await self._uow.supabase_schemas.list_by_project(project.id)


class ListSupabaseBucketsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSupabaseBucketsQuery) -> list[SupabaseBucket]:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")
            return await self._uow.supabase_buckets.list_by_project(project.id)


class ListSupabaseRealtimeChannelsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSupabaseRealtimeChannelsQuery) -> list[SupabaseRealtimeChannel]:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")
            return await self._uow.supabase_realtime_channels.list_by_project(project.id)


class ListSupabaseRlsPoliciesHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSupabaseRlsPoliciesQuery) -> list[SupabaseRlsPolicy]:
        async with self._uow:
            project = await self._uow.supabase_projects.get_by_id_and_tenant(
                query.project_id, query.tenant_id
            )
            if not project:
                raise NotFoundError("Project not found")
            return await self._uow.supabase_rls_policies.list_by_project(project.id)
