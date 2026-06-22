from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from controlbox.shared.domain.base import Entity, utc_now


@dataclass
class UserMfa(Entity):
    user_id: UUID = field(default_factory=UUID)
    totp_secret_encrypted: str = ""
    is_enabled: bool = False
    backup_codes_hash: list[str] = field(default_factory=list)


@dataclass
class WebAuthnCredential(Entity):
    user_id: UUID = field(default_factory=UUID)
    credential_id: str = ""
    public_key: bytes = b""
    sign_count: int = 0
    transports: list[str] = field(default_factory=list)
    nickname: str = ""
    last_used_at: datetime | None = None


@dataclass
class TrustedDevice(Entity):
    user_id: UUID = field(default_factory=UUID)
    fingerprint_hash: str = ""
    label: str = ""
    user_agent: str | None = None
    ip_address: str | None = None
    is_revoked: bool = False
    last_seen_at: datetime | None = None


@dataclass
class SecurityEvent(Entity):
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    event_type: str = ""
    severity: str = "low"
    message: str = ""
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict = field(default_factory=dict)

    def touch_seen(self) -> None:
        self.touch()


DEFAULT_SECURITY_SETTINGS = {
    "waf_enabled": True,
    "brute_force_protection": True,
    "enforce_mfa": False,
    "malware_scanner": False,
}
