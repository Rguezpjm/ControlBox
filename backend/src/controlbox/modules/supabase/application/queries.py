from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListSupabaseProjectsQuery:
    tenant_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetSupabaseProjectQuery:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class GetSupabaseCredentialsQuery:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class GetSupabaseUsageQuery:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class ListSupabaseSchemasQuery:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class ListSupabaseBucketsQuery:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class ListSupabaseRealtimeChannelsQuery:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class ListSupabaseRlsPoliciesQuery:
    tenant_id: UUID
    project_id: UUID
