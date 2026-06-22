from abc import ABC, abstractmethod
from uuid import UUID

from controlbox.modules.team_members.domain.entities import TeamInvitation, TeamMember, TeamPermission, TeamRole


class TeamRoleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, role_id: UUID) -> TeamRole | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_slug(self, slug: str) -> TeamRole | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[TeamRole]:
        raise NotImplementedError

    @abstractmethod
    async def get_permission_codes(self, role_id: UUID) -> list[str]:
        raise NotImplementedError


class TeamMemberRepository(ABC):
    @abstractmethod
    async def add(self, member: TeamMember) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, member: TeamMember) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, member_id: UUID, tenant_id: UUID) -> TeamMember | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_user_and_tenant(self, user_id: UUID, tenant_id: UUID) -> TeamMember | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[TeamMember]:
        raise NotImplementedError

    @abstractmethod
    async def resolve_permission_codes(self, user_id: UUID, tenant_id: UUID) -> tuple[list[str], list[str]]:
        raise NotImplementedError


class TeamInvitationRepository(ABC):
    @abstractmethod
    async def add(self, invitation: TeamInvitation) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, invitation: TeamInvitation) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id_and_tenant(self, invitation_id: UUID, tenant_id: UUID) -> TeamInvitation | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> TeamInvitation | None:
        raise NotImplementedError

    @abstractmethod
    async def get_pending_by_email(self, tenant_id: UUID, email: str) -> TeamInvitation | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[TeamInvitation]:
        raise NotImplementedError
