from uuid import UUID

from controlbox.modules.identity.domain.entities import AuditLog
from controlbox.shared.application.unit_of_work import UnitOfWork


async def record_audit(
    uow: UnitOfWork,
    *,
    tenant_id: UUID | None,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    await uow.audit_logs.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
