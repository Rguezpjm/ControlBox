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
from controlbox.modules.supabase.infrastructure.models import (
    SupabaseBucketModel,
    SupabaseProjectModel,
    SupabaseRealtimeChannelModel,
    SupabaseRlsPolicyModel,
    SupabaseSchemaModel,
)


def to_supabase_project(model: SupabaseProjectModel) -> SupabaseProject:
    return SupabaseProject(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        slug=model.slug,
        status=SupabaseProjectStatus(model.status),
        project_ref=model.project_ref,
        database_name=model.database_name,
        database_user=model.database_user,
        database_password_encrypted=model.database_password_encrypted,
        anon_key=model.anon_key,
        service_role_key=model.service_role_key,
        api_url=model.api_url,
        studio_url=model.studio_url,
        storage_used_mb=model.storage_used_mb,
        database_size_mb=model.database_size_mb,
        requests_count=model.requests_count,
        settings=model.settings or {},
        error_message=model.error_message,
        suspended_at=model.suspended_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_supabase_schema(model: SupabaseSchemaModel) -> SupabaseSchema:
    return SupabaseSchema(
        id=model.id,
        project_id=model.project_id,
        tenant_id=model.tenant_id,
        name=model.name,
        is_default=model.is_default,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_supabase_bucket(model: SupabaseBucketModel) -> SupabaseBucket:
    return SupabaseBucket(
        id=model.id,
        project_id=model.project_id,
        tenant_id=model.tenant_id,
        name=model.name,
        public=model.public,
        file_size_limit_mb=model.file_size_limit_mb,
        status=BucketStatus(model.status),
        objects_count=model.objects_count,
        size_mb=model.size_mb,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_supabase_realtime_channel(model: SupabaseRealtimeChannelModel) -> SupabaseRealtimeChannel:
    return SupabaseRealtimeChannel(
        id=model.id,
        project_id=model.project_id,
        tenant_id=model.tenant_id,
        name=model.name,
        table_name=model.table_name,
        schema_name=model.schema_name,
        events=model.events or [],
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_supabase_rls_policy(model: SupabaseRlsPolicyModel) -> SupabaseRlsPolicy:
    return SupabaseRlsPolicy(
        id=model.id,
        project_id=model.project_id,
        tenant_id=model.tenant_id,
        name=model.name,
        table_name=model.table_name,
        schema_name=model.schema_name,
        action=RlsPolicyAction(model.action),
        role_name=model.role_name,
        using_expression=model.using_expression,
        check_expression=model.check_expression,
        is_enabled=model.is_enabled,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
