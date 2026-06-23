from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListDatabasesQuery:
    tenant_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False
    engine: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetDatabaseQuery:
    tenant_id: UUID
    database_id: UUID
    requester_user_id: UUID | None = None
    can_manage_all: bool = False


@dataclass(frozen=True)
class GetDatabaseOptionsQuery:
    pass


@dataclass(frozen=True)
class ListDatabaseUsersQuery:
    tenant_id: UUID
    database_id: UUID


@dataclass(frozen=True)
class ListDatabaseBackupsQuery:
    tenant_id: UUID
    database_id: UUID
    limit: int = 20
