from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GetSecurityOverviewQuery:
    tenant_id: UUID


@dataclass(frozen=True)
class ListSecurityEventsQuery:
    tenant_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class ListTrustedDevicesQuery:
    user_id: UUID


@dataclass(frozen=True)
class ListPasskeysQuery:
    user_id: UUID


@dataclass(frozen=True)
class GetSecuritySettingsQuery:
    tenant_id: UUID


@dataclass
class SecurityOverviewResponse:
    blocked_ips: int
    threats_blocked_24h: int
    active_sessions: int
    mfa_enabled_users: int
    passkeys_count: int
    security_events_24h: int


@dataclass
class SecurityEventResponse:
    id: UUID
    event_type: str
    severity: str
    message: str
    ip_address: str | None
    user_agent: str | None
    metadata: dict
    created_at: datetime


@dataclass
class TrustedDeviceResponse:
    id: UUID
    label: str
    fingerprint_hash: str
    user_agent: str | None
    ip_address: str | None
    last_seen_at: datetime | None
    created_at: datetime


@dataclass
class PasskeyResponse:
    id: UUID
    nickname: str
    transports: list[str]
    last_used_at: datetime | None
    created_at: datetime


@dataclass
class MfaSetupResponse:
    secret: str
    otpauth_url: str
    backup_codes: list[str]


@dataclass
class MfaChallengeResponse:
    mfa_required: bool
    challenge_token: str
    methods: list[str]
