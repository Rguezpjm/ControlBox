from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from controlbox.shared.domain.email import PanelEmail


class InviteTeamMemberRequest(BaseModel):
    email: PanelEmail
    team_role_slug: str = Field(min_length=1, max_length=64)
    message: str = ""
    tenant_id: UUID | None = None
    sender_user_id: UUID | None = None


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=1)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UpdateTeamMemberRoleRequest(BaseModel):
    team_role_slug: str = Field(min_length=1, max_length=64)


class TeamMemberResponseSchema(BaseModel):
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


class TeamInvitationResponseSchema(BaseModel):
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


class TeamRoleResponseSchema(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    level: int
    permissions: list[str]


class TeamActivityResponseSchema(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict
    ip_address: str | None
    created_at: datetime


class InviteTeamMemberResponseSchema(BaseModel):
    invitation: TeamInvitationResponseSchema
    invite_url: str
