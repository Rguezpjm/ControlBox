from uuid import UUID

from controlbox.modules.security.domain.entities import DEFAULT_SECURITY_SETTINGS
from controlbox.shared.application.unit_of_work import UnitOfWork


async def get_tenant_security_settings(uow: UnitOfWork, tenant_id: UUID | None) -> dict:
    if tenant_id is None:
        return dict(DEFAULT_SECURITY_SETTINGS)
    tenant = await uow.tenants.get_by_id(tenant_id)
    if tenant is None:
        return dict(DEFAULT_SECURITY_SETTINGS)
    settings = dict(tenant.settings or {})
    return dict(settings.get("security", DEFAULT_SECURITY_SETTINGS))
