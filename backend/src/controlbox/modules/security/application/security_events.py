from uuid import UUID

from controlbox.modules.security.domain.entities import SecurityEvent
from controlbox.shared.application.unit_of_work import UnitOfWork


class SecurityEventRecorder:
    async def record(
        self,
        uow: UnitOfWork,
        *,
        tenant_id: UUID | None,
        user_id: UUID | None,
        event_type: str,
        severity: str,
        message: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        await uow.security_events.add(
            SecurityEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type=event_type,
                severity=severity,
                message=message,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata or {},
            )
        )
