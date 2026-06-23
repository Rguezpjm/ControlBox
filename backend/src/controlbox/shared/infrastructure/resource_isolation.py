from typing import Protocol
from uuid import UUID

class HasAccessContext(Protocol):
    is_platform_admin: bool
    permissions: list[str]
    roles: list[str]
    user_id: UUID


OWNER_KEY = "owner_user_id"


def can_manage_all_resources(context: HasAccessContext) -> bool:
    if context.is_platform_admin:
        return True
    if "team_members.manage" in context.permissions:
        return True
    roles = {role.lower() for role in context.roles}
    return "owner" in roles or "administrator" in roles or "admin" in roles


def owner_id_from_settings(settings: dict | None) -> UUID | None:
    if not settings:
        return None
    raw = settings.get(OWNER_KEY)
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        return None


def set_owner_in_settings(settings: dict | None, user_id: UUID) -> dict:
    next_settings = dict(settings or {})
    next_settings[OWNER_KEY] = str(user_id)
    return next_settings


def is_owner_visible(context: HasAccessContext, owner_user_id: UUID | None) -> bool:
    if can_manage_all_resources(context):
        return True
    return owner_user_id is not None and owner_user_id == context.user_id
