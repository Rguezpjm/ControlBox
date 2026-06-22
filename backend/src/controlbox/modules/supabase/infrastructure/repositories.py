from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.supabase.domain.entities import (
    SupabaseBucket,
    SupabaseProject,
    SupabaseRealtimeChannel,
    SupabaseRlsPolicy,
    SupabaseSchema,
)
from controlbox.modules.supabase.domain.repositories import (
    SupabaseBucketRepository,
    SupabaseProjectRepository,
    SupabaseRealtimeChannelRepository,
    SupabaseRlsPolicyRepository,
    SupabaseSchemaRepository,
)
from controlbox.modules.supabase.infrastructure.mappers import (
    to_supabase_bucket,
    to_supabase_project,
    to_supabase_realtime_channel,
    to_supabase_rls_policy,
    to_supabase_schema,
)
from controlbox.modules.supabase.infrastructure.models import (
    SupabaseBucketModel,
    SupabaseProjectModel,
    SupabaseRealtimeChannelModel,
    SupabaseRlsPolicyModel,
    SupabaseSchemaModel,
)


class SqlAlchemySupabaseProjectRepository(SupabaseProjectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: SupabaseProject) -> None:
        model = SupabaseProjectModel(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            slug=project.slug,
            status=project.status.value,
            project_ref=project.project_ref,
            database_name=project.database_name,
            database_user=project.database_user,
            database_password_encrypted=project.database_password_encrypted,
            anon_key=project.anon_key,
            service_role_key=project.service_role_key,
            api_url=project.api_url,
            studio_url=project.studio_url,
            storage_used_mb=project.storage_used_mb,
            database_size_mb=project.database_size_mb,
            requests_count=project.requests_count,
            settings=project.settings,
            error_message=project.error_message,
            suspended_at=project.suspended_at,
        )
        self._session.add(model)

    async def save(self, project: SupabaseProject) -> None:
        result = await self._session.execute(
            select(SupabaseProjectModel).where(SupabaseProjectModel.id == project.id)
        )
        model = result.scalar_one()
        model.status = project.status.value
        model.anon_key = project.anon_key
        model.service_role_key = project.service_role_key
        model.database_password_encrypted = project.database_password_encrypted
        model.storage_used_mb = project.storage_used_mb
        model.database_size_mb = project.database_size_mb
        model.requests_count = project.requests_count
        model.settings = project.settings
        model.error_message = project.error_message
        model.suspended_at = project.suspended_at

    async def get_by_id(self, project_id: UUID) -> SupabaseProject | None:
        result = await self._session.execute(
            select(SupabaseProjectModel).where(SupabaseProjectModel.id == project_id)
        )
        model = result.scalar_one_or_none()
        return to_supabase_project(model) if model else None

    async def get_by_id_and_tenant(self, project_id: UUID, tenant_id: UUID) -> SupabaseProject | None:
        result = await self._session.execute(
            select(SupabaseProjectModel).where(
                SupabaseProjectModel.id == project_id,
                SupabaseProjectModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_supabase_project(model) if model else None

    async def get_by_slug(self, slug: str, tenant_id: UUID) -> SupabaseProject | None:
        result = await self._session.execute(
            select(SupabaseProjectModel).where(
                SupabaseProjectModel.slug == slug,
                SupabaseProjectModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_supabase_project(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[SupabaseProject]:
        result = await self._session.execute(
            select(SupabaseProjectModel)
            .where(SupabaseProjectModel.tenant_id == tenant_id)
            .order_by(SupabaseProjectModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [to_supabase_project(m) for m in result.scalars().all()]

    async def delete(self, project_id: UUID) -> None:
        await self._session.execute(delete(SupabaseProjectModel).where(SupabaseProjectModel.id == project_id))


class SqlAlchemySupabaseSchemaRepository(SupabaseSchemaRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, schema: SupabaseSchema) -> None:
        self._session.add(SupabaseSchemaModel(
            id=schema.id,
            project_id=schema.project_id,
            tenant_id=schema.tenant_id,
            name=schema.name,
            is_default=schema.is_default,
        ))

    async def list_by_project(self, project_id: UUID) -> list[SupabaseSchema]:
        result = await self._session.execute(
            select(SupabaseSchemaModel).where(SupabaseSchemaModel.project_id == project_id)
        )
        return [to_supabase_schema(m) for m in result.scalars().all()]

    async def get_by_id_and_project(self, schema_id: UUID, project_id: UUID) -> SupabaseSchema | None:
        result = await self._session.execute(
            select(SupabaseSchemaModel).where(
                SupabaseSchemaModel.id == schema_id,
                SupabaseSchemaModel.project_id == project_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_supabase_schema(model) if model else None

    async def delete(self, schema_id: UUID) -> None:
        await self._session.execute(delete(SupabaseSchemaModel).where(SupabaseSchemaModel.id == schema_id))


class SqlAlchemySupabaseBucketRepository(SupabaseBucketRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, bucket: SupabaseBucket) -> None:
        self._session.add(SupabaseBucketModel(
            id=bucket.id,
            project_id=bucket.project_id,
            tenant_id=bucket.tenant_id,
            name=bucket.name,
            public=bucket.public,
            file_size_limit_mb=bucket.file_size_limit_mb,
            status=bucket.status.value,
            objects_count=bucket.objects_count,
            size_mb=bucket.size_mb,
        ))

    async def save(self, bucket: SupabaseBucket) -> None:
        result = await self._session.execute(
            select(SupabaseBucketModel).where(SupabaseBucketModel.id == bucket.id)
        )
        model = result.scalar_one()
        model.status = bucket.status.value
        model.objects_count = bucket.objects_count
        model.size_mb = bucket.size_mb

    async def list_by_project(self, project_id: UUID) -> list[SupabaseBucket]:
        result = await self._session.execute(
            select(SupabaseBucketModel).where(SupabaseBucketModel.project_id == project_id)
        )
        return [to_supabase_bucket(m) for m in result.scalars().all()]

    async def get_by_id_and_project(self, bucket_id: UUID, project_id: UUID) -> SupabaseBucket | None:
        result = await self._session.execute(
            select(SupabaseBucketModel).where(
                SupabaseBucketModel.id == bucket_id,
                SupabaseBucketModel.project_id == project_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_supabase_bucket(model) if model else None

    async def delete(self, bucket_id: UUID) -> None:
        await self._session.execute(delete(SupabaseBucketModel).where(SupabaseBucketModel.id == bucket_id))


class SqlAlchemySupabaseRealtimeChannelRepository(SupabaseRealtimeChannelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, channel: SupabaseRealtimeChannel) -> None:
        self._session.add(SupabaseRealtimeChannelModel(
            id=channel.id,
            project_id=channel.project_id,
            tenant_id=channel.tenant_id,
            name=channel.name,
            table_name=channel.table_name,
            schema_name=channel.schema_name,
            events=channel.events,
            is_active=channel.is_active,
        ))

    async def list_by_project(self, project_id: UUID) -> list[SupabaseRealtimeChannel]:
        result = await self._session.execute(
            select(SupabaseRealtimeChannelModel).where(
                SupabaseRealtimeChannelModel.project_id == project_id
            )
        )
        return [to_supabase_realtime_channel(m) for m in result.scalars().all()]

    async def get_by_id_and_project(self, channel_id: UUID, project_id: UUID) -> SupabaseRealtimeChannel | None:
        result = await self._session.execute(
            select(SupabaseRealtimeChannelModel).where(
                SupabaseRealtimeChannelModel.id == channel_id,
                SupabaseRealtimeChannelModel.project_id == project_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_supabase_realtime_channel(model) if model else None

    async def delete(self, channel_id: UUID) -> None:
        await self._session.execute(
            delete(SupabaseRealtimeChannelModel).where(SupabaseRealtimeChannelModel.id == channel_id)
        )


class SqlAlchemySupabaseRlsPolicyRepository(SupabaseRlsPolicyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, policy: SupabaseRlsPolicy) -> None:
        self._session.add(SupabaseRlsPolicyModel(
            id=policy.id,
            project_id=policy.project_id,
            tenant_id=policy.tenant_id,
            name=policy.name,
            table_name=policy.table_name,
            schema_name=policy.schema_name,
            action=policy.action.value,
            role_name=policy.role_name,
            using_expression=policy.using_expression,
            check_expression=policy.check_expression,
            is_enabled=policy.is_enabled,
        ))

    async def list_by_project(self, project_id: UUID) -> list[SupabaseRlsPolicy]:
        result = await self._session.execute(
            select(SupabaseRlsPolicyModel).where(SupabaseRlsPolicyModel.project_id == project_id)
        )
        return [to_supabase_rls_policy(m) for m in result.scalars().all()]

    async def get_by_id_and_project(self, policy_id: UUID, project_id: UUID) -> SupabaseRlsPolicy | None:
        result = await self._session.execute(
            select(SupabaseRlsPolicyModel).where(
                SupabaseRlsPolicyModel.id == policy_id,
                SupabaseRlsPolicyModel.project_id == project_id,
            )
        )
        model = result.scalar_one_or_none()
        return to_supabase_rls_policy(model) if model else None

    async def delete(self, policy_id: UUID) -> None:
        await self._session.execute(
            delete(SupabaseRlsPolicyModel).where(SupabaseRlsPolicyModel.id == policy_id)
        )
