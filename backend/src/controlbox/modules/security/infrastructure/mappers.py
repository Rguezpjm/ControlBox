from controlbox.modules.security.domain.entities import SecurityEvent, TrustedDevice, UserMfa, WebAuthnCredential
from controlbox.modules.security.infrastructure.models import (
    SecurityEventModel,
    TrustedDeviceModel,
    UserMfaModel,
    WebAuthnCredentialModel,
)


def user_mfa_to_entity(model: UserMfaModel) -> UserMfa:
    return UserMfa(
        user_id=model.user_id,
        totp_secret_encrypted=model.totp_secret_encrypted,
        is_enabled=model.is_enabled,
        backup_codes_hash=list(model.backup_codes_hash or []),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_mfa_to_model(entity: UserMfa) -> UserMfaModel:
    return UserMfaModel(
        user_id=entity.user_id,
        totp_secret_encrypted=entity.totp_secret_encrypted,
        is_enabled=entity.is_enabled,
        backup_codes_hash=entity.backup_codes_hash,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def webauthn_credential_to_entity(model: WebAuthnCredentialModel) -> WebAuthnCredential:
    return WebAuthnCredential(
        id=model.id,
        user_id=model.user_id,
        credential_id=model.credential_id,
        public_key=model.public_key,
        sign_count=model.sign_count,
        transports=list(model.transports or []),
        nickname=model.nickname,
        last_used_at=model.last_used_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def webauthn_credential_to_model(entity: WebAuthnCredential) -> WebAuthnCredentialModel:
    return WebAuthnCredentialModel(
        id=entity.id,
        user_id=entity.user_id,
        credential_id=entity.credential_id,
        public_key=entity.public_key,
        sign_count=entity.sign_count,
        transports=entity.transports,
        nickname=entity.nickname,
        last_used_at=entity.last_used_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def trusted_device_to_entity(model: TrustedDeviceModel) -> TrustedDevice:
    return TrustedDevice(
        id=model.id,
        user_id=model.user_id,
        fingerprint_hash=model.fingerprint_hash,
        label=model.label,
        user_agent=model.user_agent,
        ip_address=model.ip_address,
        is_revoked=model.is_revoked,
        last_seen_at=model.last_seen_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def trusted_device_to_model(entity: TrustedDevice) -> TrustedDeviceModel:
    return TrustedDeviceModel(
        id=entity.id,
        user_id=entity.user_id,
        fingerprint_hash=entity.fingerprint_hash,
        label=entity.label,
        user_agent=entity.user_agent,
        ip_address=entity.ip_address,
        is_revoked=entity.is_revoked,
        last_seen_at=entity.last_seen_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def security_event_to_entity(model: SecurityEventModel) -> SecurityEvent:
    return SecurityEvent(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        event_type=model.event_type,
        severity=model.severity,
        message=model.message,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        metadata=dict(model.metadata_ or {}),
        created_at=model.created_at,
        updated_at=model.created_at,
    )


def security_event_to_model(entity: SecurityEvent) -> SecurityEventModel:
    return SecurityEventModel(
        id=entity.id,
        tenant_id=entity.tenant_id,
        user_id=entity.user_id,
        event_type=entity.event_type,
        severity=entity.severity,
        message=entity.message,
        ip_address=entity.ip_address,
        user_agent=entity.user_agent,
        metadata_=entity.metadata,
        created_at=entity.created_at,
    )
