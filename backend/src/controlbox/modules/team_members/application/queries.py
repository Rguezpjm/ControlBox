from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ListTeamMembersQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class ListTeamInvitationsQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class ListTeamRolesQuery:
    pass


@dataclass(frozen=True)
class GetTeamActivityQuery:
    tenant_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetInvitationByTokenQuery:
    token: str


@dataclass(frozen=True)
class TeamMemberResponse:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    email: str
    full_name: str
    team_role_slug: str
    team_role_name: str
    status: str
    invited_by: UUID | None
    joined_at: datetime | None
    last_active_at: datetime | None
    mfa_enabled: bool
    passkey_count: int
    session_count: int
    created_at: datetime


@dataclass(frozen=True)
class TeamInvitationResponse:
    id: UUID
    tenant_id: UUID
    email: str
    team_role_slug: str
    team_role_name: str
    status: str
    invited_by: UUID | None
    expires_at: datetime
    accepted_at: datetime | None
    message: str
    created_at: datetime


@dataclass(frozen=True)
class TeamRoleResponse:
    id: UUID
    slug: str
    name: str
    description: str
    level: int
    permissions: list[str]


@dataclass(frozen=True)
class TeamActivityResponse:
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict
    ip_address: str | None
    created_at: datetime
