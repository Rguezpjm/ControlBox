import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from controlbox.config.settings import Settings
from controlbox.modules.identity.domain.entities import AuditLog, User
from controlbox.modules.identity.domain.tenant_service import UserDomainService
from controlbox.modules.identity.domain.services import PasswordService
from controlbox.modules.team_members.application.commands import (
    AcceptInvitationCommand,
    InviteTeamMemberCommand,
    RemoveTeamMemberCommand,
    ResendInvitationCommand,
    RevokeInvitationCommand,
    SuspendTeamMemberCommand,
    UpdateTeamMemberRoleCommand,
)
from controlbox.modules.team_members.application.queries import (
    GetInvitationByTokenQuery,
    GetTeamActivityQuery,
    ListTeamInvitationsQuery,
    ListTeamMembersQuery,
    ListTeamRolesQuery,
    TeamActivityResponse,
    TeamInvitationResponse,
    TeamMemberResponse,
    TeamRoleResponse,
)
from controlbox.modules.team_members.domain.entities import (
    TeamInvitation,
    TeamInvitationStatus,
    TeamMember,
    TeamMemberStatus,
)
from controlbox.modules.team_members.domain.services import TeamDomainService
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ConflictError, ForbiddenError, NotFoundError, ValidationError, utc_now

logger = logging.getLogger("controlbox.team")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InviteTeamMemberHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, command: InviteTeamMemberCommand) -> tuple[TeamInvitationResponse, str]:
        domain = TeamDomainService(self._uow.team_roles, self._uow.team_members, self._uow.team_invitations)
        email = domain.validate_email(command.email)
        role = await domain.resolve_role(command.team_role_slug)
        await domain.ensure_can_invite(command.tenant_id, command.invited_by, role)

        existing_user = await self._uow.users.get_by_email(email, command.tenant_id)
        if existing_user:
            member = await self._uow.team_members.get_by_user_and_tenant(existing_user.id, command.tenant_id)
            if member:
                raise ConflictError("User is already a team member")

        pending = await self._uow.team_invitations.get_pending_by_email(command.tenant_id, email)
        if pending:
            raise ConflictError("Pending invitation already exists for this email")

        raw_token = secrets.token_urlsafe(32)
        invitation = TeamInvitation(
            tenant_id=command.tenant_id,
            email=email,
            token_hash=_hash_token(raw_token),
            team_role_id=role.id,
            invited_by=command.invited_by,
            status=TeamInvitationStatus.PENDING,
            expires_at=utc_now() + timedelta(days=7),
            message=command.message,
        )
        await self._uow.team_invitations.add(invitation)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.invited_by,
                action="team_member.invited",
                resource_type="team_invitation",
                resource_id=str(invitation.id),
                metadata={"email": email, "role": role.slug},
            )
        )
        await self._uow.commit()

        invite_url = f"{self._settings.webauthn_origin}/accept-invite?token={raw_token}"
        logger.info("Team invitation created for %s: %s", email, invite_url)

        return (
            TeamInvitationResponse(
                id=invitation.id,
                tenant_id=invitation.tenant_id,
                email=invitation.email,
                team_role_slug=role.slug,
                team_role_name=role.name,
                status=invitation.status.value,
                invited_by=invitation.invited_by,
                expires_at=invitation.expires_at,
                accepted_at=None,
                message=invitation.message,
                created_at=invitation.created_at,
            ),
            raw_token,
        )


class AcceptInvitationHandler:
    def __init__(self, uow: UnitOfWork, password_service: PasswordService) -> None:
        self._uow = uow
        self._passwords = password_service

    async def handle(self, command: AcceptInvitationCommand) -> TeamMemberResponse:
        token_hash = _hash_token(command.token)
        invitation = await self._uow.team_invitations.get_by_token_hash(token_hash)
        if invitation is None or invitation.status != TeamInvitationStatus.PENDING:
            raise NotFoundError("Invalid or expired invitation")
        if invitation.expires_at < utc_now():
            invitation.expire()
            await self._uow.team_invitations.save(invitation)
            await self._uow.commit()
            raise ValidationError("Invitation has expired")

        user_service = UserDomainService(self._uow.users, self._passwords)
        user_service.validate_password_strength(command.password)

        existing = await self._uow.users.get_by_email(invitation.email, invitation.tenant_id)
        if existing:
            user = existing
            if not user.is_active:
                user.is_active = True
        else:
            user = User(
                tenant_id=invitation.tenant_id,
                email=invitation.email,
                password_hash=self._passwords.hash(command.password),
                full_name=command.full_name.strip(),
                is_active=True,
            )
            await self._uow.users.add(user)

        member_role = await self._uow.roles.get_by_name("member", invitation.tenant_id)
        if member_role:
            existing_roles = await self._uow.users.get_roles(user.id)
            if not any(r.id == member_role.id for r in existing_roles):
                await self._uow.users.assign_role(user.id, member_role.id)
        if existing and not existing.is_active:
            await self._uow.users.save(user)

        member = TeamMember(
            tenant_id=invitation.tenant_id,
            user_id=user.id,
            team_role_id=invitation.team_role_id,
            status=TeamMemberStatus.ACTIVE,
            invited_by=invitation.invited_by,
            joined_at=utc_now(),
        )
        await self._uow.team_members.add(member)
        invitation.accept()
        await self._uow.team_invitations.save(invitation)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=invitation.tenant_id,
                user_id=user.id,
                action="team_member.activated",
                resource_type="team_member",
                resource_id=str(member.id),
                metadata={"email": user.email},
            )
        )
        await self._uow.commit()

        role = await self._uow.team_roles.get_by_id(invitation.team_role_id)
        return TeamMemberResponse(
            id=member.id,
            tenant_id=member.tenant_id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            team_role_slug=role.slug if role else "",
            team_role_name=role.name if role else "",
            status=member.status.value,
            invited_by=member.invited_by,
            joined_at=member.joined_at,
            last_active_at=member.last_active_at,
            mfa_enabled=False,
            passkey_count=0,
            session_count=0,
            created_at=member.created_at,
        )


class UpdateTeamMemberRoleHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: UpdateTeamMemberRoleCommand) -> TeamMemberResponse:
        domain = TeamDomainService(self._uow.team_roles, self._uow.team_members, self._uow.team_invitations)
        member = await self._uow.team_members.get_by_id_and_tenant(command.member_id, command.tenant_id)
        if member is None:
            raise NotFoundError("Team member not found")
        new_role = await domain.resolve_role(command.team_role_slug)
        await domain.ensure_can_manage_member(command.tenant_id, command.actor_id, member, new_role)
        member.team_role_id = new_role.id
        await self._uow.team_members.save(member)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.actor_id,
                action="team_member.role_updated",
                resource_type="team_member",
                resource_id=str(member.id),
                metadata={"role": new_role.slug},
            )
        )
        await self._uow.commit()
        return await _member_response(self._uow, member)


class SuspendTeamMemberHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: SuspendTeamMemberCommand) -> TeamMemberResponse:
        member = await self._uow.team_members.get_by_id_and_tenant(command.member_id, command.tenant_id)
        if member is None:
            raise NotFoundError("Team member not found")
        if member.user_id == command.actor_id:
            raise ForbiddenError("Cannot suspend yourself")
        member.suspend()
        user = await self._uow.users.get_by_id(member.user_id)
        if user:
            user.is_active = False
            await self._uow.users.save(user)
        await self._uow.team_members.save(member)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.actor_id,
                action="team_member.suspended",
                resource_type="team_member",
                resource_id=str(member.id),
            )
        )
        await self._uow.commit()
        return await _member_response(self._uow, member)


class RemoveTeamMemberHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: RemoveTeamMemberCommand) -> None:
        member = await self._uow.team_members.get_by_id_and_tenant(command.member_id, command.tenant_id)
        if member is None:
            raise NotFoundError("Team member not found")
        if member.user_id == command.actor_id:
            raise ForbiddenError("Cannot remove yourself")
        member.remove()
        await self._uow.team_members.save(member)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.actor_id,
                action="team_member.removed",
                resource_type="team_member",
                resource_id=str(member.id),
            )
        )
        await self._uow.commit()


class RevokeInvitationHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: RevokeInvitationCommand) -> None:
        invitation = await self._uow.team_invitations.get_by_id_and_tenant(command.invitation_id, command.tenant_id)
        if invitation is None:
            raise NotFoundError("Invitation not found")
        invitation.revoke()
        await self._uow.team_invitations.save(invitation)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.actor_id,
                action="team_member.invitation_revoked",
                resource_type="team_invitation",
                resource_id=str(invitation.id),
            )
        )
        await self._uow.commit()


class ResendInvitationHandler:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def handle(self, command: ResendInvitationCommand) -> tuple[TeamInvitationResponse, str]:
        invitation = await self._uow.team_invitations.get_by_id_and_tenant(command.invitation_id, command.tenant_id)
        if invitation is None:
            raise NotFoundError("Invitation not found")
        if invitation.status != TeamInvitationStatus.PENDING:
            raise ValidationError("Only pending invitations can be resent")

        raw_token = secrets.token_urlsafe(32)
        invitation.token_hash = _hash_token(raw_token)
        invitation.expires_at = utc_now() + timedelta(days=7)
        await self._uow.team_invitations.save(invitation)
        await self._uow.audit_logs.add(
            AuditLog(
                tenant_id=command.tenant_id,
                user_id=command.actor_id,
                action="team_member.invitation_resent",
                resource_type="team_invitation",
                resource_id=str(invitation.id),
            )
        )
        await self._uow.commit()

        role = await self._uow.team_roles.get_by_id(invitation.team_role_id)
        invite_url = f"{self._settings.webauthn_origin}/accept-invite?token={raw_token}"
        logger.info("Team invitation resent for %s: %s", invitation.email, invite_url)

        return (
            TeamInvitationResponse(
                id=invitation.id,
                tenant_id=invitation.tenant_id,
                email=invitation.email,
                team_role_slug=role.slug if role else "",
                team_role_name=role.name if role else "",
                status=invitation.status.value,
                invited_by=invitation.invited_by,
                expires_at=invitation.expires_at,
                accepted_at=invitation.accepted_at,
                message=invitation.message,
                created_at=invitation.created_at,
            ),
            raw_token,
        )


class ListTeamMembersHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListTeamMembersQuery) -> list[TeamMemberResponse]:
        members = await self._uow.team_members.list_by_tenant(query.tenant_id)
        return [await _member_response(self._uow, m) for m in members]


class ListTeamInvitationsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListTeamInvitationsQuery) -> list[TeamInvitationResponse]:
        invitations = await self._uow.team_invitations.list_by_tenant(query.tenant_id)
        results = []
        for inv in invitations:
            role = await self._uow.team_roles.get_by_id(inv.team_role_id)
            results.append(
                TeamInvitationResponse(
                    id=inv.id,
                    tenant_id=inv.tenant_id,
                    email=inv.email,
                    team_role_slug=role.slug if role else "",
                    team_role_name=role.name if role else "",
                    status=inv.status.value,
                    invited_by=inv.invited_by,
                    expires_at=inv.expires_at,
                    accepted_at=inv.accepted_at,
                    message=inv.message,
                    created_at=inv.created_at,
                )
            )
        return results


class ListTeamRolesHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListTeamRolesQuery) -> list[TeamRoleResponse]:
        roles = await self._uow.team_roles.list_all()
        results = []
        for role in roles:
            perms = await self._uow.team_roles.get_permission_codes(role.id)
            if "*" in perms:
                all_perms = await self._uow.permissions.list_all()
                perms = [p.code for p in all_perms]
            results.append(
                TeamRoleResponse(
                    id=role.id,
                    slug=role.slug,
                    name=role.name,
                    description=role.description,
                    level=role.level,
                    permissions=perms,
                )
            )
        return results


class GetTeamActivityHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetTeamActivityQuery) -> list[TeamActivityResponse]:
        logs = await self._uow.audit_logs.list_by_tenant(query.tenant_id, query.limit, query.offset)
        filtered = [
            l for l in logs
            if l.action.startswith("team_member.") or l.resource_type in ("team_member", "team_invitation")
        ]
        return [
            TeamActivityResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                metadata=log.metadata,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in filtered
        ]


class GetInvitationByTokenHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetInvitationByTokenQuery) -> TeamInvitationResponse:
        invitation = await self._uow.team_invitations.get_by_token_hash(_hash_token(query.token))
        if invitation is None:
            raise NotFoundError("Invitation not found")
        role = await self._uow.team_roles.get_by_id(invitation.team_role_id)
        return TeamInvitationResponse(
            id=invitation.id,
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            team_role_slug=role.slug if role else "",
            team_role_name=role.name if role else "",
            status=invitation.status.value,
            invited_by=invitation.invited_by,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            message=invitation.message,
            created_at=invitation.created_at,
        )


async def _member_response(uow: UnitOfWork, member: TeamMember) -> TeamMemberResponse:
    user = await uow.users.get_by_id(member.user_id)
    role = await uow.team_roles.get_by_id(member.team_role_id)
    mfa_enabled = False
    passkey_count = 0
    session_count = 0
    if hasattr(uow, "user_mfa"):
        mfa = await uow.user_mfa.get_by_user(member.user_id)
        mfa_enabled = bool(mfa and mfa.is_enabled)
    if hasattr(uow, "webauthn_credentials"):
        passkeys = await uow.webauthn_credentials.list_by_user(member.user_id)
        passkey_count = len(passkeys)
    sessions = await uow.sessions.list_active_by_user(member.user_id)
    session_count = len([s for s in sessions if not s.is_revoked])
    return TeamMemberResponse(
        id=member.id,
        tenant_id=member.tenant_id,
        user_id=member.user_id,
        email=user.email if user else "",
        full_name=user.full_name if user else "",
        team_role_slug=role.slug if role else "",
        team_role_name=role.name if role else "",
        status=member.status.value,
        invited_by=member.invited_by,
        joined_at=member.joined_at,
        last_active_at=member.last_active_at,
        mfa_enabled=mfa_enabled,
        passkey_count=passkey_count,
        session_count=session_count,
        created_at=member.created_at,
    )
