from dataclasses import dataclass
from uuid import UUID

from controlbox.config.settings import Settings, get_settings
from controlbox.modules.supabase.application.commands import (
    CreateSupabaseBucketCommand,
    CreateSupabaseProjectCommand,
    CreateSupabaseRealtimeChannelCommand,
    CreateSupabaseRlsPolicyCommand,
    CreateSupabaseSchemaCommand,
    DeleteSupabaseBucketCommand,
    DeleteSupabaseProjectCommand,
    DeleteSupabaseRealtimeChannelCommand,
    DeleteSupabaseRlsPolicyCommand,
    DeleteSupabaseSchemaCommand,
    ResumeSupabaseProjectCommand,
    RotateSupabaseKeysCommand,
    SuspendSupabaseProjectCommand,
)
from controlbox.modules.supabase.domain.entities import (
    BucketStatus,
    RlsPolicyAction,
    SupabaseBucket,
    SupabaseProject,
    SupabaseProjectStatus,
    SupabaseRealtimeChannel,
    SupabaseRlsPolicy,
    SupabaseSchema,
)
from controlbox.modules.supabase.domain.services import SupabaseDomainService
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor
from controlbox.modules.supabase.infrastructure.provisioner import SupabaseProvisioner, SupabaseStorageClient
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError


async def _get_project(uow: UnitOfWork, project_id: UUID, tenant_id: UUID) -> SupabaseProject:
    project = await uow.supabase_projects.get_by_id_and_tenant(project_id, tenant_id)
    if not project:
        raise NotFoundError("Project not found")
    return project


class CreateSupabaseProjectHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = SupabaseProvisioner(self._settings)
        self._encryptor = SecretEncryptor(self._settings)

    async def handle(self, command: CreateSupabaseProjectCommand) -> SupabaseProject:
        domain = SupabaseDomainService(self._uow.supabase_projects)
        slug = domain.validate_name(command.name)
        await domain.ensure_slug_available(slug, command.tenant_id)

        project_ref = domain.build_project_ref(command.tenant_id, slug)
        db_name = domain.build_database_name(command.tenant_id, slug)
        db_user = domain.build_database_user(command.tenant_id, slug)
        db_password = self._provisioner.generate_password()
        anon_key, service_key = self._provisioner.generate_keys(project_ref, str(command.tenant_id))

        project = SupabaseProject(
            tenant_id=command.tenant_id,
            name=command.name,
            slug=slug,
            status=SupabaseProjectStatus.PENDING,
            project_ref=project_ref,
            database_name=db_name,
            database_user=db_user,
            database_password_encrypted=self._encryptor.encrypt(db_password),
            anon_key=anon_key,
            service_role_key=service_key,
            api_url=self._settings.supabase_url,
            studio_url=self._settings.supabase_studio_url,
        )

        async with self._uow:
            await self._uow.supabase_projects.add(project)
            try:
                await self._provisioner.provision_project(project, db_password)
                project.mark_active()
                default_schema = SupabaseSchema(
                    project_id=project.id,
                    tenant_id=command.tenant_id,
                    name="public",
                    is_default=True,
                )
                await self._uow.supabase_schemas.add(default_schema)
                project.database_size_mb = await self._provisioner.get_database_size_mb(project.database_name)
                await self._uow.supabase_projects.save(project)
            except Exception as exc:
                project.mark_error(str(exc))
                await self._uow.supabase_projects.save(project)
            await self._uow.commit()

        return project


class SuspendSupabaseProjectHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: SuspendSupabaseProjectCommand) -> SupabaseProject:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            await self._provisioner.suspend_project(project)
            project.mark_suspended()
            await self._uow.supabase_projects.save(project)
            await self._uow.commit()
        return project


class ResumeSupabaseProjectHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: ResumeSupabaseProjectCommand) -> SupabaseProject:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            await self._provisioner.resume_project(project)
            project.mark_active()
            await self._uow.supabase_projects.save(project)
            await self._uow.commit()
        return project


class DeleteSupabaseProjectHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._provisioner = SupabaseProvisioner(self._settings)
        self._storage = SupabaseStorageClient(self._settings)

    async def handle(self, command: DeleteSupabaseProjectCommand) -> None:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            buckets = await self._uow.supabase_buckets.list_by_project(project.id)
            for bucket in buckets:
                try:
                    await self._storage.delete_bucket(bucket.name, project)
                except Exception:
                    pass
            try:
                await self._provisioner.deprovision_project(project)
            except Exception:
                pass
            await self._uow.supabase_projects.delete(project.id)
            await self._uow.commit()


class RotateSupabaseKeysHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: RotateSupabaseKeysCommand) -> SupabaseProject:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            anon_key, service_key = self._provisioner.generate_keys(
                project.project_ref, str(command.tenant_id)
            )
            project.anon_key = anon_key
            project.service_role_key = service_key
            await self._uow.supabase_projects.save(project)
            await self._uow.commit()
        return project


class CreateSupabaseSchemaHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: CreateSupabaseSchemaCommand) -> SupabaseSchema:
        domain = SupabaseDomainService(self._uow.supabase_projects)
        schema_name = domain.validate_schema_name(command.name)

        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            await self._provisioner.create_schema(project, schema_name)
            schema = SupabaseSchema(
                project_id=project.id,
                tenant_id=command.tenant_id,
                name=schema_name,
            )
            await self._uow.supabase_schemas.add(schema)
            await self._uow.commit()
        return schema


class DeleteSupabaseSchemaHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: DeleteSupabaseSchemaCommand) -> None:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            schema = await self._uow.supabase_schemas.get_by_id_and_project(command.schema_id, project.id)
            if not schema:
                raise NotFoundError("Schema not found")
            if schema.is_default:
                raise NotFoundError("Cannot delete default schema")
            await self._provisioner.drop_schema(project, schema.name)
            await self._uow.supabase_schemas.delete(schema.id)
            await self._uow.commit()


class CreateSupabaseBucketHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._settings = settings or get_settings()
        self._storage = SupabaseStorageClient(self._settings)

    async def handle(self, command: CreateSupabaseBucketCommand) -> SupabaseBucket:
        domain = SupabaseDomainService(self._uow.supabase_projects)

        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            bucket_name = domain.build_bucket_name(project.project_ref, command.name)
            bucket = SupabaseBucket(
                project_id=project.id,
                tenant_id=command.tenant_id,
                name=bucket_name,
                public=command.public,
                file_size_limit_mb=command.file_size_limit_mb,
                status=BucketStatus.ACTIVE,
            )
            await self._storage.create_bucket(bucket, project)
            await self._uow.supabase_buckets.add(bucket)
            await self._uow.commit()
        return bucket


class DeleteSupabaseBucketHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._storage = SupabaseStorageClient(settings or get_settings())

    async def handle(self, command: DeleteSupabaseBucketCommand) -> None:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            bucket = await self._uow.supabase_buckets.get_by_id_and_project(command.bucket_id, project.id)
            if not bucket:
                raise NotFoundError("Bucket not found")
            await self._storage.delete_bucket(bucket.name, project)
            await self._uow.supabase_buckets.delete(bucket.id)
            await self._uow.commit()


class CreateSupabaseRealtimeChannelHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: CreateSupabaseRealtimeChannelCommand) -> SupabaseRealtimeChannel:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            channel = SupabaseRealtimeChannel(
                project_id=project.id,
                tenant_id=command.tenant_id,
                name=command.name,
                table_name=command.table_name,
                schema_name=command.schema_name,
                events=command.events or ["INSERT", "UPDATE", "DELETE"],
            )
            await self._provisioner.setup_realtime_channel(project, channel)
            await self._uow.supabase_realtime_channels.add(channel)
            await self._uow.commit()
        return channel


class DeleteSupabaseRealtimeChannelHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: DeleteSupabaseRealtimeChannelCommand) -> None:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            channel = await self._uow.supabase_realtime_channels.get_by_id_and_project(
                command.channel_id, project.id
            )
            if not channel:
                raise NotFoundError("Channel not found")
            await self._provisioner.remove_realtime_channel(project, channel)
            await self._uow.supabase_realtime_channels.delete(channel.id)
            await self._uow.commit()


class CreateSupabaseRlsPolicyHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: CreateSupabaseRlsPolicyCommand) -> SupabaseRlsPolicy:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            policy = SupabaseRlsPolicy(
                project_id=project.id,
                tenant_id=command.tenant_id,
                name=command.name,
                table_name=command.table_name,
                schema_name=command.schema_name,
                action=RlsPolicyAction(command.action),
                role_name=command.role_name,
                using_expression=command.using_expression,
                check_expression=command.check_expression,
            )
            await self._provisioner.apply_rls_policy(project, policy)
            await self._uow.supabase_rls_policies.add(policy)
            await self._uow.commit()
        return policy


class DeleteSupabaseRlsPolicyHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings | None = None) -> None:
        self._uow = uow
        self._provisioner = SupabaseProvisioner(settings or get_settings())

    async def handle(self, command: DeleteSupabaseRlsPolicyCommand) -> None:
        async with self._uow:
            project = await _get_project(self._uow, command.project_id, command.tenant_id)
            policy = await self._uow.supabase_rls_policies.get_by_id_and_project(
                command.policy_id, project.id
            )
            if not policy:
                raise NotFoundError("Policy not found")
            await self._provisioner.remove_rls_policy(project, policy)
            await self._uow.supabase_rls_policies.delete(policy.id)
            await self._uow.commit()
