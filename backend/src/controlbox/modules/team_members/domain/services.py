from uuid import UUID

from controlbox.modules.team_members.domain.repositories import (
    TeamInvitationRepository,
    TeamMemberRepository,
    TeamRoleRepository,
)
from controlbox.shared.domain.base import ConflictError, ForbiddenError, NotFoundError, ValidationError


class TeamDomainService:
    def __init__(
        self,
        roles: TeamRoleRepository,
        members: TeamMemberRepository,
        invitations: TeamInvitationRepository,
    ) -> None:
        self._roles = roles
        self._members = members
        self._invitations = invitations

    def validate_email(self, email: str) -> str:
        cleaned = email.strip().lower()
        if "@" not in cleaned or len(cleaned) < 5:
            raise ValidationError("Invalid email address")
        return cleaned

    async def resolve_role(self, slug: str) -> object:
        role = await self._roles.get_by_slug(slug)
        if role is None:
            raise NotFoundError(f"Team role '{slug}' not found")
        if role.slug == "owner":
            raise ForbiddenError("Cannot assign owner role via invitation")
        return role

    async def ensure_can_invite(self, tenant_id: UUID, actor_id: UUID, role) -> None:
        actor = await self._members.get_by_user_and_tenant(actor_id, tenant_id)
        if actor is None:
            return
        actor_role = await self._roles.get_by_id(actor.team_role_id)
        if actor_role and actor_role.slug in ("owner", "administrator"):
            return
        raise ForbiddenError("Insufficient permissions to invite team members")

    async def ensure_can_manage_member(self, tenant_id: UUID, actor_id: UUID, member, new_role) -> None:
        if member.user_id == actor_id:
            raise ForbiddenError("Cannot change your own role")
        actor = await self._members.get_by_user_and_tenant(actor_id, tenant_id)
        if actor is None:
            return
        actor_role = await self._roles.get_by_id(actor.team_role_id)
        target_role = await self._roles.get_by_id(member.team_role_id)
        if target_role and target_role.slug == "owner":
            raise ForbiddenError("Cannot modify owner")
        if new_role.slug == "owner":
            raise ForbiddenError("Cannot promote to owner")
        if actor_role and actor_role.slug in ("owner", "administrator"):
            return
        raise ForbiddenError("Insufficient permissions")
