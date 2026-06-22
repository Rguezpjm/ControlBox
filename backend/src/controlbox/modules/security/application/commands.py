from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SetupMfaCommand:
    user_id: UUID
    email: str


@dataclass(frozen=True)
class EnableMfaCommand:
    user_id: UUID
    tenant_id: UUID | None
    code: str
    secret: str
    backup_codes: list[str]


@dataclass(frozen=True)
class DisableMfaCommand:
    user_id: UUID
    tenant_id: UUID | None
    code: str


@dataclass(frozen=True)
class VerifyMfaLoginCommand:
    challenge_token: str
    code: str
    user_agent: str | None
    ip_address: str | None
    device_fingerprint: str | None


@dataclass(frozen=True)
class RevokeTrustedDeviceCommand:
    user_id: UUID
    tenant_id: UUID | None
    device_id: UUID


@dataclass(frozen=True)
class UpdateSecuritySettingsCommand:
    tenant_id: UUID
    settings: dict


@dataclass(frozen=True)
class UnblockIpCommand:
    ip: str
    tenant_id: UUID | None
