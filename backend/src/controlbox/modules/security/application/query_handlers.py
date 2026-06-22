from controlbox.modules.security.application.commands import SetupMfaCommand
from controlbox.modules.security.application.queries import (
    GetSecurityOverviewQuery,
    GetSecuritySettingsQuery,
    ListPasskeysQuery,
    ListSecurityEventsQuery,
    ListTrustedDevicesQuery,
    PasskeyResponse,
    SecurityEventResponse,
    SecurityOverviewResponse,
    TrustedDeviceResponse,
)
from controlbox.modules.security.domain.entities import DEFAULT_SECURITY_SETTINGS
from controlbox.shared.application.cqrs import QueryHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import NotFoundError
from controlbox.shared.infrastructure.security.protection import IpReputation


class GetSecurityOverviewHandler(QueryHandler[GetSecurityOverviewQuery, SecurityOverviewResponse]):
    def __init__(self, uow: UnitOfWork, ip_reputation: IpReputation) -> None:
        self._uow = uow
        self._ip = ip_reputation

    async def handle(self, query: GetSecurityOverviewQuery) -> SecurityOverviewResponse:
        blocked = await self._ip.list_blocked_ips(limit=500)
        events_24h = await self._uow.security_events.count_by_tenant(query.tenant_id, since_hours=24)
        sessions = await self._uow.sessions.list_active_by_tenant(query.tenant_id)
        mfa_count = await self._uow.user_mfa.count_enabled_by_tenant(query.tenant_id)
        passkeys_count = await self._uow.webauthn_credentials.count_by_tenant(query.tenant_id)
        return SecurityOverviewResponse(
            blocked_ips=len(blocked),
            threats_blocked_24h=events_24h,
            active_sessions=len(sessions),
            mfa_enabled_users=mfa_count,
            passkeys_count=passkeys_count,
            security_events_24h=events_24h,
        )


class ListSecurityEventsHandler(QueryHandler[ListSecurityEventsQuery, list[SecurityEventResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListSecurityEventsQuery) -> list[SecurityEventResponse]:
        events = await self._uow.security_events.list_by_tenant(query.tenant_id, query.limit, query.offset)
        return [
            SecurityEventResponse(
                id=e.id,
                event_type=e.event_type,
                severity=e.severity,
                message=e.message,
                ip_address=e.ip_address,
                user_agent=e.user_agent,
                metadata=e.metadata,
                created_at=e.created_at,
            )
            for e in events
        ]


class ListTrustedDevicesHandler(QueryHandler[ListTrustedDevicesQuery, list[TrustedDeviceResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListTrustedDevicesQuery) -> list[TrustedDeviceResponse]:
        devices = await self._uow.trusted_devices.list_by_user(query.user_id)
        return [
            TrustedDeviceResponse(
                id=d.id,
                label=d.label,
                fingerprint_hash=d.fingerprint_hash[:12] + "...",
                user_agent=d.user_agent,
                ip_address=d.ip_address,
                last_seen_at=d.last_seen_at,
                created_at=d.created_at,
            )
            for d in devices
        ]


class ListPasskeysHandler(QueryHandler[ListPasskeysQuery, list[PasskeyResponse]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: ListPasskeysQuery) -> list[PasskeyResponse]:
        creds = await self._uow.webauthn_credentials.list_by_user(query.user_id)
        return [
            PasskeyResponse(
                id=c.id,
                nickname=c.nickname,
                transports=c.transports,
                last_used_at=c.last_used_at,
                created_at=c.created_at,
            )
            for c in creds
        ]


class GetSecuritySettingsHandler(QueryHandler[GetSecuritySettingsQuery, dict]):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, query: GetSecuritySettingsQuery) -> dict:
        tenant = await self._uow.tenants.get_by_id(query.tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found")
        settings = dict(tenant.settings or {})
        return dict(settings.get("security", DEFAULT_SECURITY_SETTINGS))
