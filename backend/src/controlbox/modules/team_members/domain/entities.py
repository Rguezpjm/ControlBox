from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from controlbox.shared.domain.base import Entity


class TeamMemberStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class TeamInvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


TEAM_ROLE_SLUGS = [
    "owner",
    "administrator",
    "website_manager",
    "dns_manager",
    "database_manager",
    "ftp_manager",
    "billing_manager",
    "read_only",
]


@dataclass
class TeamRole(Entity):
    slug: str = ""
    name: str = ""
    description: str = ""
    is_system: bool = True
    level: int = 0


@dataclass
class TeamPermission(Entity):
    team_role_id: UUID | None = None
    permission_code: str = ""


@dataclass
class TeamMember(Entity):
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    team_role_id: UUID | None = None
    status: TeamMemberStatus = TeamMemberStatus.ACTIVE
    invited_by: UUID | None = None
    joined_at: datetime | None = None
    last_active_at: datetime | None = None

    def suspend(self) -> None:
        self.status = TeamMemberStatus.SUSPENDED
        self.touch()

    def activate(self) -> None:
        self.status = TeamMemberStatus.ACTIVE
        self.touch()

    def remove(self) -> None:
        self.status = TeamMemberStatus.REMOVED
        self.touch()


@dataclass
class TeamInvitation(Entity):
    tenant_id: UUID | None = None
    email: str = ""
    token_hash: str = ""
    team_role_id: UUID | None = None
    invited_by: UUID | None = None
    status: TeamInvitationStatus = TeamInvitationStatus.PENDING
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    message: str = ""

    def revoke(self) -> None:
        self.status = TeamInvitationStatus.REVOKED
        self.touch()

    def accept(self) -> None:
        self.status = TeamInvitationStatus.ACCEPTED
        self.accepted_at = datetime.utcnow()
        self.touch()

    def expire(self) -> None:
        self.status = TeamInvitationStatus.EXPIRED
        self.touch()
