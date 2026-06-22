from controlbox.modules.team_members.domain.entities import (
    TeamInvitation,
    TeamInvitationStatus,
    TeamMember,
    TeamMemberStatus,
    TeamPermission,
    TeamRole,
)
from controlbox.modules.team_members.infrastructure.models import (
    TeamInvitationModel,
    TeamMemberModel,
    TeamPermissionModel,
    TeamRoleModel,
)


def role_to_entity(model: TeamRoleModel) -> TeamRole:
    return TeamRole(
        id=model.id,
        slug=model.slug,
        name=model.name,
        description=model.description,
        is_system=model.is_system,
        level=model.level,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def role_to_model(entity: TeamRole) -> TeamRoleModel:
    return TeamRoleModel(
        id=entity.id,
        slug=entity.slug,
        name=entity.name,
        description=entity.description,
        is_system=entity.is_system,
        level=entity.level,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def permission_to_entity(model: TeamPermissionModel) -> TeamPermission:
    return TeamPermission(
        id=model.id,
        team_role_id=model.team_role_id,
        permission_code=model.permission_code,
    )


def permission_to_model(entity: TeamPermission) -> TeamPermissionModel:
    return TeamPermissionModel(
        id=entity.id,
        team_role_id=entity.team_role_id,
        permission_code=entity.permission_code,
    )


def member_to_entity(model: TeamMemberModel) -> TeamMember:
    return TeamMember(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        team_role_id=model.team_role_id,
        status=TeamMemberStatus(model.status),
        invited_by=model.invited_by,
        joined_at=model.joined_at,
        last_active_at=model.last_active_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def member_to_model(entity: TeamMember) -> TeamMemberModel:
    return TeamMemberModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        user_id=entity.user_id,
        team_role_id=entity.team_role_id,
        status=entity.status.value,
        invited_by=entity.invited_by,
        joined_at=entity.joined_at,
        last_active_at=entity.last_active_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def invitation_to_entity(model: TeamInvitationModel) -> TeamInvitation:
    return TeamInvitation(
        id=model.id,
        tenant_id=model.tenant_id,
        email=model.email,
        token_hash=model.token_hash,
        team_role_id=model.team_role_id,
        invited_by=model.invited_by,
        status=TeamInvitationStatus(model.status),
        expires_at=model.expires_at,
        accepted_at=model.accepted_at,
        message=model.message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def invitation_to_model(entity: TeamInvitation) -> TeamInvitationModel:
    return TeamInvitationModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        email=entity.email,
        token_hash=entity.token_hash,
        team_role_id=entity.team_role_id,
        invited_by=entity.invited_by,
        status=entity.status.value,
        expires_at=entity.expires_at,
        accepted_at=entity.accepted_at,
        message=entity.message,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )
