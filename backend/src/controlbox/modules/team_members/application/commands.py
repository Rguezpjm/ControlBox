from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class InviteTeamMemberCommand:
    tenant_id: UUID
    invited_by: UUID
    email: str
    team_role_slug: str
    message: str = ""
    sender_user_id: UUID | None = None


@dataclass(frozen=True)
class AcceptInvitationCommand:
    token: str
    full_name: str
    password: str


@dataclass(frozen=True)
class UpdateTeamMemberRoleCommand:
    tenant_id: UUID
    member_id: UUID
    actor_id: UUID
    team_role_slug: str


@dataclass(frozen=True)
class SuspendTeamMemberCommand:
    tenant_id: UUID
    member_id: UUID
    actor_id: UUID


@dataclass(frozen=True)
class RemoveTeamMemberCommand:
    tenant_id: UUID
    member_id: UUID
    actor_id: UUID


@dataclass(frozen=True)
class RevokeInvitationCommand:
    tenant_id: UUID
    invitation_id: UUID
    actor_id: UUID


@dataclass(frozen=True)
class ResendInvitationCommand:
    tenant_id: UUID
    invitation_id: UUID
    actor_id: UUID
