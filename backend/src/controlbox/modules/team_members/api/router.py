from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import (
    RequestContext,
    get_unit_of_work,
    map_domain_exception,
    require_permission,
)
from controlbox.modules.identity.domain.services import PasswordService
from controlbox.modules.team_members.api.schemas import (
    AcceptInvitationRequest,
    InviteTeamMemberRequest,
    InviteTeamMemberResponseSchema,
    TeamActivityResponseSchema,
    TeamInvitationResponseSchema,
    TeamMemberResponseSchema,
    TeamRoleResponseSchema,
    UpdateTeamMemberRoleRequest,
)
from controlbox.modules.team_members.application.command_handlers import (
    AcceptInvitationHandler,
    GetInvitationByTokenHandler,
    GetTeamActivityHandler,
    InviteTeamMemberHandler,
    ListTeamInvitationsHandler,
    ListTeamMembersHandler,
    ListTeamRolesHandler,
    RemoveTeamMemberHandler,
    ResendInvitationHandler,
    RevokeInvitationHandler,
    SuspendTeamMemberHandler,
    UpdateTeamMemberRoleHandler,
)
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
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import DomainException, ForbiddenError


router = APIRouter(prefix="/team", tags=["team"])


def _require_tenant(context: RequestContext) -> UUID:
    if not context.tenant_id:
        raise map_domain_exception(ForbiddenError("Tenant context required"))
    return context.tenant_id


@router.get("/members", response_model=list[TeamMemberResponseSchema])
async def list_members(
    context: Annotated[RequestContext, Depends(require_permission("team_members.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[TeamMemberResponseSchema]:
    tenant_id = _require_tenant(context)
    try:
        members = await ListTeamMembersHandler(uow).handle(ListTeamMembersQuery(tenant_id=tenant_id))
        return [TeamMemberResponseSchema(**m.__dict__) for m in members]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/invitations", response_model=list[TeamInvitationResponseSchema])
async def list_invitations(
    context: Annotated[RequestContext, Depends(require_permission("team_members.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[TeamInvitationResponseSchema]:
    tenant_id = _require_tenant(context)
    try:
        invitations = await ListTeamInvitationsHandler(uow).handle(ListTeamInvitationsQuery(tenant_id=tenant_id))
        return [TeamInvitationResponseSchema(**i.__dict__) for i in invitations]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/roles", response_model=list[TeamRoleResponseSchema])
async def list_roles(
    context: Annotated[RequestContext, Depends(require_permission("team_members.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> list[TeamRoleResponseSchema]:
    try:
        roles = await ListTeamRolesHandler(uow).handle(ListTeamRolesQuery())
        return [TeamRoleResponseSchema(**r.__dict__) for r in roles]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/activity", response_model=list[TeamActivityResponseSchema])
async def list_activity(
    context: Annotated[RequestContext, Depends(require_permission("team_members.read"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limit: int = 50,
    offset: int = 0,
) -> list[TeamActivityResponseSchema]:
    tenant_id = _require_tenant(context)
    try:
        activity = await GetTeamActivityHandler(uow).handle(
            GetTeamActivityQuery(tenant_id=tenant_id, limit=min(limit, 100), offset=offset)
        )
        return [TeamActivityResponseSchema(**a.__dict__) for a in activity]
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/invitations", response_model=InviteTeamMemberResponseSchema, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: InviteTeamMemberRequest,
    context: Annotated[RequestContext, Depends(require_permission("team_members.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InviteTeamMemberResponseSchema:
    tenant_id = payload.tenant_id or _require_tenant(context)
    settings = get_settings()
    try:
        invitation, raw_token = await InviteTeamMemberHandler(uow, settings).handle(
            InviteTeamMemberCommand(
                tenant_id=tenant_id,
                invited_by=context.user_id,
                email=str(payload.email),
                team_role_slug=payload.team_role_slug,
                message=payload.message,
                sender_user_id=payload.sender_user_id,
            )
        )
        invite_url = f"{settings.webauthn_origin}/accept-invite?token={raw_token}"
        return InviteTeamMemberResponseSchema(
            invitation=TeamInvitationResponseSchema(**invitation.__dict__),
            invite_url=invite_url,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.get("/invitations/preview", response_model=TeamInvitationResponseSchema)
async def preview_invitation(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TeamInvitationResponseSchema:
    try:
        invitation = await GetInvitationByTokenHandler(uow).handle(GetInvitationByTokenQuery(token=token))
        return TeamInvitationResponseSchema(**invitation.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/invitations/accept", response_model=TeamMemberResponseSchema, status_code=status.HTTP_201_CREATED)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TeamMemberResponseSchema:
    try:
        member = await AcceptInvitationHandler(uow, PasswordService()).handle(
            AcceptInvitationCommand(
                token=payload.token,
                full_name=payload.full_name,
                password=payload.password,
            )
        )
        return TeamMemberResponseSchema(**member.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/invitations/{invitation_id}/resend", response_model=InviteTeamMemberResponseSchema)
async def resend_invitation(
    invitation_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("team_members.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InviteTeamMemberResponseSchema:
    tenant_id = _require_tenant(context)
    settings = get_settings()
    try:
        invitation, raw_token = await ResendInvitationHandler(uow, settings).handle(
            ResendInvitationCommand(
                tenant_id=tenant_id,
                invitation_id=invitation_id,
                actor_id=context.user_id,
            )
        )
        invite_url = f"{settings.webauthn_origin}/accept-invite?token={raw_token}"
        return InviteTeamMemberResponseSchema(
            invitation=TeamInvitationResponseSchema(**invitation.__dict__),
            invite_url=invite_url,
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("team_members.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await RevokeInvitationHandler(uow).handle(
            RevokeInvitationCommand(
                tenant_id=tenant_id,
                invitation_id=invitation_id,
                actor_id=context.user_id,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.patch("/members/{member_id}/role", response_model=TeamMemberResponseSchema)
async def update_member_role(
    member_id: UUID,
    payload: UpdateTeamMemberRoleRequest,
    context: Annotated[RequestContext, Depends(require_permission("team_members.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TeamMemberResponseSchema:
    tenant_id = _require_tenant(context)
    try:
        member = await UpdateTeamMemberRoleHandler(uow).handle(
            UpdateTeamMemberRoleCommand(
                tenant_id=tenant_id,
                member_id=member_id,
                actor_id=context.user_id,
                team_role_slug=payload.team_role_slug,
            )
        )
        return TeamMemberResponseSchema(**member.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.post("/members/{member_id}/suspend", response_model=TeamMemberResponseSchema)
async def suspend_member(
    member_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("team_members.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TeamMemberResponseSchema:
    tenant_id = _require_tenant(context)
    try:
        member = await SuspendTeamMemberHandler(uow).handle(
            SuspendTeamMemberCommand(
                tenant_id=tenant_id,
                member_id=member_id,
                actor_id=context.user_id,
            )
        )
        return TeamMemberResponseSchema(**member.__dict__)
    except DomainException as exc:
        raise map_domain_exception(exc) from exc


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: UUID,
    context: Annotated[RequestContext, Depends(require_permission("team_members.manage"))],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    tenant_id = _require_tenant(context)
    try:
        await RemoveTeamMemberHandler(uow).handle(
            RemoveTeamMemberCommand(
                tenant_id=tenant_id,
                member_id=member_id,
                actor_id=context.user_id,
            )
        )
    except DomainException as exc:
        raise map_domain_exception(exc) from exc
