from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MfaChallengeResponseSchema(BaseModel):
    mfa_required: bool = True
    challenge_token: str
    methods: list[str]


class LoginResponseSchema(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    access_token_expires_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None
    session_id: UUID | None = None
    mfa_required: bool = False
    challenge_token: str | None = None
    methods: list[str] = Field(default_factory=list)
    csrf_token: str | None = None


class MfaVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=32)
    code: str = Field(min_length=6, max_length=16)
    device_fingerprint: str | None = Field(default=None, max_length=128)


class MfaSetupResponseSchema(BaseModel):
    secret: str
    otpauth_url: str
    backup_codes: list[str]


class EnableMfaRequest(BaseModel):
    secret: str
    code: str = Field(min_length=6, max_length=6)
    backup_codes: list[str]


class DisableMfaRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class SecurityOverviewSchema(BaseModel):
    blocked_ips: int
    threats_blocked_24h: int
    active_sessions: int
    mfa_enabled_users: int
    passkeys_count: int
    security_events_24h: int


class SecurityEventSchema(BaseModel):
    id: UUID
    event_type: str
    severity: str
    message: str
    ip_address: str | None
    user_agent: str | None
    metadata: dict
    created_at: datetime


class TrustedDeviceSchema(BaseModel):
    id: UUID
    label: str
    fingerprint_hash: str
    user_agent: str | None
    ip_address: str | None
    last_seen_at: datetime | None
    created_at: datetime


class PasskeySchema(BaseModel):
    id: UUID
    nickname: str
    transports: list[str]
    last_used_at: datetime | None
    created_at: datetime


class SecuritySettingsSchema(BaseModel):
    waf_enabled: bool = True
    brute_force_protection: bool = True
    enforce_mfa: bool = False
    malware_scanner: bool = False
    web_vuln_scan: bool = False


class UpdateSecuritySettingsRequest(BaseModel):
    waf_enabled: bool | None = None
    brute_force_protection: bool | None = None
    enforce_mfa: bool | None = None
    malware_scanner: bool | None = None
    web_vuln_scan: bool | None = None


class VulnerabilityFindingSchema(BaseModel):
    id: str
    category: str
    title: str
    severity: str
    status: str
    target: str
    detail: str
    recommendation: str


class VulnerabilityAssessmentSchema(BaseModel):
    score: int
    score_label: str
    total: int
    high: int
    medium: int
    low: int
    web_scan_enabled: bool
    findings: list[VulnerabilityFindingSchema] = []


class ScanToolSchema(BaseModel):
    id: str
    label: str
    description: str
    bruteforce: bool
    available: bool


class StartScanRequest(BaseModel):
    target: str
    tools: list[str] | None = None
    bruteforce: bool = False


class ScanSchema(BaseModel):
    id: str
    target: str
    tools: list[str] = []
    status: str
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    score: int | None = None
    high: int | None = None
    medium: int | None = None
    low: int | None = None
    error: str | None = None
    findings: list[dict] = []
    tools_result: list[dict] = []


class BlockedIpSchema(BaseModel):
    ip: str
    reason: str
    ttl_seconds: int


class WebAuthnRegisterRequest(BaseModel):
    credential: dict
    nickname: str = Field(default="Passkey", max_length=128)


class WebAuthnLoginBeginRequest(BaseModel):
    email: str
    tenant_slug: str | None = None


class WebAuthnLoginVerifyRequest(BaseModel):
    email: str
    credential: dict
    tenant_slug: str | None = None
    device_fingerprint: str | None = None


class CsrfTokenResponseSchema(BaseModel):
    csrf_token: str
