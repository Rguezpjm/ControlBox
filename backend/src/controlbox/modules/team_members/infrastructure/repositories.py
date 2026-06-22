from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.team_members.domain.entities import TeamInvitation, TeamMember, TeamRole
from controlbox.modules.team_members.domain.repositories import (
    TeamInvitationRepository,
    TeamMemberRepository,
    TeamRoleRepository,
)
from controlbox.modules.team_members.infrastructure.mappers import (
    invitation_to_entity,
    invitation_to_model,
    member_to_entity,
    member_to_model,
    role_to_entity,
)
from controlbox.modules.team_members.infrastructure.models import (
    TeamInvitationModel,
    TeamMemberModel,
    TeamPermissionModel,
    TeamRoleModel,
)


class SqlAlchemyTeamRoleRepository(TeamRoleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, role_id: UUID) -> TeamRole | None:
        result = await self._session.execute(select(TeamRoleModel).where(TeamRoleModel.id == role_id))
        model = result.scalar_one_or_none()
        return role_to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> TeamRole | None:
        result = await self._session.execute(select(TeamRoleModel).where(TeamRoleModel.slug == slug))
        model = result.scalar_one_or_none()
        return role_to_entity(model) if model else None

    async def list_all(self) -> list[TeamRole]:
        result = await self._session.execute(select(TeamRoleModel).order_by(TeamRoleModel.level.desc()))
        return [role_to_entity(m) for m in result.scalars().all()]

    async def get_permission_codes(self, role_id: UUID) -> list[str]:
        result = await self._session.execute(
            select(TeamPermissionModel.permission_code).where(TeamPermissionModel.team_role_id == role_id)
        )
        return [row[0] for row in result.all()]


class SqlAlchemyTeamMemberRepository(TeamMemberRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, member: TeamMember) -> None:
        self._session.add(member_to_model(member))

    async def save(self, member: TeamMember) -> None:
        await self._session.merge(member_to_model(member))

    async def get_by_id_and_tenant(self, member_id: UUID, tenant_id: UUID) -> TeamMember | None:
        result = await self._session.execute(
            select(TeamMemberModel).where(
                TeamMemberModel.id == member_id, TeamMemberModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return member_to_entity(model) if model else None

    async def get_by_user_and_tenant(self, user_id: UUID, tenant_id: UUID) -> TeamMember | None:
        result = await self._session.execute(
            select(TeamMemberModel).where(
                TeamMemberModel.user_id == user_id,
                TeamMemberModel.tenant_id == tenant_id,
                TeamMemberModel.status != "removed",
            )
        )
        model = result.scalar_one_or_none()
        return member_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[TeamMember]:
        result = await self._session.execute(
            select(TeamMemberModel)
            .where(TeamMemberModel.tenant_id == tenant_id, TeamMemberModel.status != "removed")
            .order_by(TeamMemberModel.created_at.asc())
        )
        return [member_to_entity(m) for m in result.scalars().all()]

    async def resolve_permission_codes(self, user_id: UUID, tenant_id: UUID) -> tuple[list[str], list[str]]:
        result = await self._session.execute(
            select(TeamRoleModel.slug, TeamRoleModel.id)
            .join(TeamMemberModel, TeamMemberModel.team_role_id == TeamRoleModel.id)
            .where(
                TeamMemberModel.user_id == user_id,
                TeamMemberModel.tenant_id == tenant_id,
                TeamMemberModel.status == "active",
            )
        )
        row = result.first()
        if not row:
            return [], []
        slug, role_id = row[0], row[1]
        perm_result = await self._session.execute(
            select(TeamPermissionModel.permission_code).where(TeamPermissionModel.team_role_id == role_id)
        )
        codes = [r[0] for r in perm_result.all()]
        if "*" in codes:
            from controlbox.modules.identity.infrastructure.models import PermissionModel
            all_result = await self._session.execute(select(PermissionModel.code))
            codes = [r[0] for r in all_result.all()]
        return [slug], codes


class SqlAlchemyTeamInvitationRepository(TeamInvitationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invitation: TeamInvitation) -> None:
        self._session.add(invitation_to_model(invitation))

    async def save(self, invitation: TeamInvitation) -> None:
        await self._session.merge(invitation_to_model(invitation))

    async def get_by_id_and_tenant(self, invitation_id: UUID, tenant_id: UUID) -> TeamInvitation | None:
        result = await self._session.execute(
            select(TeamInvitationModel).where(
                TeamInvitationModel.id == invitation_id,
                TeamInvitationModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return invitation_to_entity(model) if model else None

    async def get_by_token_hash(self, token_hash: str) -> TeamInvitation | None:
        result = await self._session.execute(
            select(TeamInvitationModel).where(TeamInvitationModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return invitation_to_entity(model) if model else None

    async def get_pending_by_email(self, tenant_id: UUID, email: str) -> TeamInvitation | None:
        result = await self._session.execute(
            select(TeamInvitationModel).where(
                TeamInvitationModel.tenant_id == tenant_id,
                TeamInvitationModel.email == email.lower(),
                TeamInvitationModel.status == "pending",
            )
        )
        model = result.scalar_one_or_none()
        return invitation_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[TeamInvitation]:
        result = await self._session.execute(
            select(TeamInvitationModel)
            .where(TeamInvitationModel.tenant_id == tenant_id)
            .order_by(TeamInvitationModel.created_at.desc())
        )
        return [invitation_to_entity(m) for m in result.scalars().all()]
