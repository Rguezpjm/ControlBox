from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.supabase.api.schemas import (
    CreateBucketRequest,
    CreateRealtimeChannelRequest,
    CreateRlsPolicyRequest,
    CreateSchemaRequest,
    CreateSupabaseProjectRequest,
    SupabaseBucketSchema,
    SupabaseCredentialsSchema,
    SupabaseProjectSchema,
    SupabaseRealtimeChannelSchema,
    SupabaseRlsPolicySchema,
    SupabaseSchemaSchema,
    SupabaseServiceStatusSchema,
    SupabaseUsageSchema,
)
from controlbox.modules.supabase.application.command_handlers import (
    CreateSupabaseBucketHandler,
    CreateSupabaseProjectHandler,
    CreateSupabaseRealtimeChannelHandler,
    CreateSupabaseRlsPolicyHandler,
    CreateSupabaseSchemaHandler,
    DeleteSupabaseBucketHandler,
    DeleteSupabaseProjectHandler,
    DeleteSupabaseRealtimeChannelHandler,
    DeleteSupabaseRlsPolicyHandler,
    DeleteSupabaseSchemaHandler,
    ResumeSupabaseProjectHandler,
    RotateSupabaseKeysHandler,
    SuspendSupabaseProjectHandler,
)
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
from controlbox.modules.supabase.application.query_handlers import (
    GetSupabaseCredentialsHandler,
    GetSupabaseProjectHandler,
    GetSupabaseUsageHandler,
    ListSupabaseBucketsHandler,
    ListSupabaseProjectsHandler,
    ListSupabaseRealtimeChannelsHandler,
    ListSupabaseRlsPoliciesHandler,
    ListSupabaseSchemasHandler,
)
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
from controlbox.modules.supabase.infrastructure.provisioner import SupabaseProvisioner
from controlbox.modules.supabase.domain.entities import SupabaseProject
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError


router = APIRouter(prefix="/supabase", tags=["supabase"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


def _to_project_schema(p: SupabaseProject) -> SupabaseProjectSchema:
    return SupabaseProjectSchema(
        id=p.id,
        tenant_id=p.tenant_id,
        name=p.name,
        slug=p.slug,
        status=p.status.value,
        project_ref=p.project_ref,
        database_name=p.database_name,
        database_user=p.database_user,
        api_url=p.api_url,
        studio_url=p.studio_url,
        storage_used_mb=p.storage_used_mb,
        database_size_mb=p.database_size_mb,
        requests_count=p.requests_count,
        error_message=p.error_message,
        suspended_at=p.suspended_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/status", response_model=SupabaseServiceStatusSchema)
async def get_supabase_status(
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
) -> SupabaseServiceStatusSchema:
    _require_tenant(context)
    settings = get_settings()
    provisioner = SupabaseProvisioner(settings)
    ok, message = await provisioner.check_connection()
    return SupabaseServiceStatusSchema(
        enabled=ok,
        status="healthy" if ok else "unavailable",
        host=settings.supabase_db_host,
        port=settings.supabase_db_port,
        message=message,
    )


@router.get("/projects", response_model=list[SupabaseProjectSchema])
async def list_projects(
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[SupabaseProjectSchema]:
    tenant_id = _require_tenant(context)
    try:
        handler = ListSupabaseProjectsHandler(uow=uow)
        projects = await handler.handle(ListSupabaseProjectsQuery(tenant_id=tenant_id, limit=limit, offset=offset))
        return [_to_project_schema(p) for p in projects]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects", response_model=SupabaseProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateSupabaseProjectRequest,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseProjectSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = CreateSupabaseProjectHandler(uow=uow, settings=get_settings())
        project = await handler.handle(CreateSupabaseProjectCommand(tenant_id=tenant_id, name=body.name))
        return _to_project_schema(project)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}", response_model=SupabaseProjectSchema)
async def get_project(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseProjectSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = GetSupabaseProjectHandler(uow=uow)
        project = await handler.handle(GetSupabaseProjectQuery(tenant_id=tenant_id, project_id=project_id))
        return _to_project_schema(project)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects/{project_id}/suspend", response_model=SupabaseProjectSchema)
async def suspend_project(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseProjectSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = SuspendSupabaseProjectHandler(uow=uow, settings=get_settings())
        project = await handler.handle(SuspendSupabaseProjectCommand(tenant_id=tenant_id, project_id=project_id))
        return _to_project_schema(project)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/projects/{project_id}/resume", response_model=SupabaseProjectSchema)
async def resume_project(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseProjectSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = ResumeSupabaseProjectHandler(uow=uow, settings=get_settings())
        project = await handler.handle(ResumeSupabaseProjectCommand(tenant_id=tenant_id, project_id=project_id))
        return _to_project_schema(project)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        handler = DeleteSupabaseProjectHandler(uow=uow, settings=get_settings())
        await handler.handle(DeleteSupabaseProjectCommand(tenant_id=tenant_id, project_id=project_id))
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects/{project_id}/rotate-keys", response_model=SupabaseCredentialsSchema)
async def rotate_keys(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseCredentialsSchema:
    tenant_id = _require_tenant(context)
    try:
        await RotateSupabaseKeysHandler(uow=uow, settings=get_settings()).handle(
            RotateSupabaseKeysCommand(tenant_id=tenant_id, project_id=project_id)
        )
        creds = await GetSupabaseCredentialsHandler(uow=uow, settings=get_settings()).handle(
            GetSupabaseCredentialsQuery(tenant_id=tenant_id, project_id=project_id)
        )
        return SupabaseCredentialsSchema(**creds.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}/credentials", response_model=SupabaseCredentialsSchema)
async def get_credentials(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseCredentialsSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = GetSupabaseCredentialsHandler(uow=uow, settings=get_settings())
        creds = await handler.handle(GetSupabaseCredentialsQuery(tenant_id=tenant_id, project_id=project_id))
        return SupabaseCredentialsSchema(**creds.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}/usage", response_model=SupabaseUsageSchema)
async def get_usage(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseUsageSchema:
    tenant_id = _require_tenant(context)
    try:
        handler = GetSupabaseUsageHandler(uow=uow, settings=get_settings())
        usage = await handler.handle(GetSupabaseUsageQuery(tenant_id=tenant_id, project_id=project_id))
        return SupabaseUsageSchema(**usage.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}/schemas", response_model=list[SupabaseSchemaSchema])
async def list_schemas(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[SupabaseSchemaSchema]:
    tenant_id = _require_tenant(context)
    try:
        schemas = await ListSupabaseSchemasHandler(uow=uow).handle(
            ListSupabaseSchemasQuery(tenant_id=tenant_id, project_id=project_id)
        )
        return [
            SupabaseSchemaSchema(
                id=s.id, project_id=s.project_id, name=s.name,
                is_default=s.is_default, created_at=s.created_at,
            )
            for s in schemas
        ]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects/{project_id}/schemas", response_model=SupabaseSchemaSchema, status_code=status.HTTP_201_CREATED)
async def create_schema(
    project_id: UUID,
    body: CreateSchemaRequest,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseSchemaSchema:
    tenant_id = _require_tenant(context)
    try:
        schema = await CreateSupabaseSchemaHandler(uow=uow, settings=get_settings()).handle(
            CreateSupabaseSchemaCommand(tenant_id=tenant_id, project_id=project_id, name=body.name)
        )
        return SupabaseSchemaSchema(
            id=schema.id, project_id=schema.project_id, name=schema.name,
            is_default=schema.is_default, created_at=schema.created_at,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/projects/{project_id}/schemas/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema(
    project_id: UUID,
    schema_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteSupabaseSchemaHandler(uow=uow, settings=get_settings()).handle(
            DeleteSupabaseSchemaCommand(tenant_id=tenant_id, project_id=project_id, schema_id=schema_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}/buckets", response_model=list[SupabaseBucketSchema])
async def list_buckets(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[SupabaseBucketSchema]:
    tenant_id = _require_tenant(context)
    try:
        buckets = await ListSupabaseBucketsHandler(uow=uow).handle(
            ListSupabaseBucketsQuery(tenant_id=tenant_id, project_id=project_id)
        )
        return [
            SupabaseBucketSchema(
                id=b.id, project_id=b.project_id, name=b.name, public=b.public,
                file_size_limit_mb=b.file_size_limit_mb, status=b.status.value,
                objects_count=b.objects_count, size_mb=b.size_mb, created_at=b.created_at,
            )
            for b in buckets
        ]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects/{project_id}/buckets", response_model=SupabaseBucketSchema, status_code=status.HTTP_201_CREATED)
async def create_bucket(
    project_id: UUID,
    body: CreateBucketRequest,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseBucketSchema:
    tenant_id = _require_tenant(context)
    try:
        bucket = await CreateSupabaseBucketHandler(uow=uow, settings=get_settings()).handle(
            CreateSupabaseBucketCommand(
                tenant_id=tenant_id, project_id=project_id, name=body.name,
                public=body.public, file_size_limit_mb=body.file_size_limit_mb,
            )
        )
        return SupabaseBucketSchema(
            id=bucket.id, project_id=bucket.project_id, name=bucket.name, public=bucket.public,
            file_size_limit_mb=bucket.file_size_limit_mb, status=bucket.status.value,
            objects_count=bucket.objects_count, size_mb=bucket.size_mb, created_at=bucket.created_at,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/projects/{project_id}/buckets/{bucket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bucket(
    project_id: UUID,
    bucket_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteSupabaseBucketHandler(uow=uow, settings=get_settings()).handle(
            DeleteSupabaseBucketCommand(tenant_id=tenant_id, project_id=project_id, bucket_id=bucket_id)
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}/realtime-channels", response_model=list[SupabaseRealtimeChannelSchema])
async def list_realtime_channels(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[SupabaseRealtimeChannelSchema]:
    tenant_id = _require_tenant(context)
    try:
        channels = await ListSupabaseRealtimeChannelsHandler(uow=uow).handle(
            ListSupabaseRealtimeChannelsQuery(tenant_id=tenant_id, project_id=project_id)
        )
        return [
            SupabaseRealtimeChannelSchema(
                id=c.id, project_id=c.project_id, name=c.name, table_name=c.table_name,
                schema_name=c.schema_name, events=c.events, is_active=c.is_active, created_at=c.created_at,
            )
            for c in channels
        ]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects/{project_id}/realtime-channels", response_model=SupabaseRealtimeChannelSchema, status_code=status.HTTP_201_CREATED)
async def create_realtime_channel(
    project_id: UUID,
    body: CreateRealtimeChannelRequest,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseRealtimeChannelSchema:
    tenant_id = _require_tenant(context)
    try:
        channel = await CreateSupabaseRealtimeChannelHandler(uow=uow, settings=get_settings()).handle(
            CreateSupabaseRealtimeChannelCommand(
                tenant_id=tenant_id, project_id=project_id, name=body.name,
                table_name=body.table_name, schema_name=body.schema_name, events=body.events,
            )
        )
        return SupabaseRealtimeChannelSchema(
            id=channel.id, project_id=channel.project_id, name=channel.name,
            table_name=channel.table_name, schema_name=channel.schema_name,
            events=channel.events, is_active=channel.is_active, created_at=channel.created_at,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/projects/{project_id}/realtime-channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_realtime_channel(
    project_id: UUID,
    channel_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteSupabaseRealtimeChannelHandler(uow=uow, settings=get_settings()).handle(
            DeleteSupabaseRealtimeChannelCommand(
                tenant_id=tenant_id, project_id=project_id, channel_id=channel_id
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/projects/{project_id}/rls-policies", response_model=list[SupabaseRlsPolicySchema])
async def list_rls_policies(
    project_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[SupabaseRlsPolicySchema]:
    tenant_id = _require_tenant(context)
    try:
        policies = await ListSupabaseRlsPoliciesHandler(uow=uow).handle(
            ListSupabaseRlsPoliciesQuery(tenant_id=tenant_id, project_id=project_id)
        )
        return [
            SupabaseRlsPolicySchema(
                id=p.id, project_id=p.project_id, name=p.name, table_name=p.table_name,
                schema_name=p.schema_name, action=p.action.value, role_name=p.role_name,
                using_expression=p.using_expression, check_expression=p.check_expression,
                is_enabled=p.is_enabled, created_at=p.created_at,
            )
            for p in policies
        ]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/projects/{project_id}/rls-policies", response_model=SupabaseRlsPolicySchema, status_code=status.HTTP_201_CREATED)
async def create_rls_policy(
    project_id: UUID,
    body: CreateRlsPolicyRequest,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SupabaseRlsPolicySchema:
    tenant_id = _require_tenant(context)
    try:
        policy = await CreateSupabaseRlsPolicyHandler(uow=uow, settings=get_settings()).handle(
            CreateSupabaseRlsPolicyCommand(
                tenant_id=tenant_id, project_id=project_id, name=body.name,
                table_name=body.table_name, schema_name=body.schema_name, action=body.action,
                role_name=body.role_name, using_expression=body.using_expression,
                check_expression=body.check_expression,
            )
        )
        return SupabaseRlsPolicySchema(
            id=policy.id, project_id=policy.project_id, name=policy.name,
            table_name=policy.table_name, schema_name=policy.schema_name,
            action=policy.action.value, role_name=policy.role_name,
            using_expression=policy.using_expression, check_expression=policy.check_expression,
            is_enabled=policy.is_enabled, created_at=policy.created_at,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/projects/{project_id}/rls-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rls_policy(
    project_id: UUID,
    policy_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("supabase.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await DeleteSupabaseRlsPolicyHandler(uow=uow, settings=get_settings()).handle(
            DeleteSupabaseRlsPolicyCommand(
                tenant_id=tenant_id, project_id=project_id, policy_id=policy_id
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
