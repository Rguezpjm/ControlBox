from controlbox.modules.identity.domain.entities import Permission
from controlbox.shared.application.unit_of_work import UnitOfWork


async def resolve_effective_auth(uow: UnitOfWork, user_id, tenant_id) -> tuple[list[str], list[str]]:
    role_names: list[str] = []
    permission_codes: list[str] = []

    roles = await uow.users.get_roles(user_id)
    role_names.extend(role.name for role in roles)
    perms = await uow.users.get_permissions(user_id)
    permission_codes.extend(p.code for p in perms)

    if tenant_id and hasattr(uow, "team_members"):
        team_roles, team_perms = await uow.team_members.resolve_permission_codes(user_id, tenant_id)
        role_names.extend(team_roles)
        permission_codes.extend(team_perms)

    unique_roles = list(dict.fromkeys(role_names))
    unique_perms = list(dict.fromkeys(permission_codes))
    return unique_roles, unique_perms
