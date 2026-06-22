from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.security.domain.entities import SecurityEvent, TrustedDevice, UserMfa, WebAuthnCredential
from controlbox.modules.security.infrastructure.mappers import (
    security_event_to_entity,
    security_event_to_model,
    trusted_device_to_entity,
    trusted_device_to_model,
    user_mfa_to_entity,
    user_mfa_to_model,
    webauthn_credential_to_entity,
    webauthn_credential_to_model,
)
from controlbox.modules.security.infrastructure.models import (
    SecurityEventModel,
    TrustedDeviceModel,
    UserMfaModel,
    WebAuthnCredentialModel,
)
from controlbox.shared.domain.base import utc_now


class SqlAlchemyUserMfaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(self, user_id: UUID) -> UserMfa | None:
        result = await self._session.execute(select(UserMfaModel).where(UserMfaModel.user_id == user_id))
        model = result.scalar_one_or_none()
        return user_mfa_to_entity(model) if model else None

    async def save(self, mfa: UserMfa) -> None:
        existing = await self._session.get(UserMfaModel, mfa.user_id)
        if existing:
            existing.totp_secret_encrypted = mfa.totp_secret_encrypted
            existing.is_enabled = mfa.is_enabled
            existing.backup_codes_hash = mfa.backup_codes_hash
            existing.updated_at = mfa.updated_at
        else:
            self._session.add(user_mfa_to_model(mfa))

    async def count_enabled_by_tenant(self, tenant_id: UUID) -> int:
        from controlbox.modules.identity.infrastructure.models import UserModel

        result = await self._session.execute(
            select(func.count())
            .select_from(UserMfaModel)
            .join(UserModel, UserModel.id == UserMfaModel.user_id)
            .where(UserModel.tenant_id == tenant_id, UserMfaModel.is_enabled.is_(True))
        )
        return result.scalar_one() or 0


class SqlAlchemyWebAuthnCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, credential: WebAuthnCredential) -> None:
        self._session.add(webauthn_credential_to_model(credential))

    async def list_by_user(self, user_id: UUID) -> list[WebAuthnCredential]:
        result = await self._session.execute(
            select(WebAuthnCredentialModel).where(WebAuthnCredentialModel.user_id == user_id)
        )
        return [webauthn_credential_to_entity(m) for m in result.scalars().all()]

    async def get_by_credential_id(self, credential_id: str) -> WebAuthnCredential | None:
        result = await self._session.execute(
            select(WebAuthnCredentialModel).where(WebAuthnCredentialModel.credential_id == credential_id)
        )
        model = result.scalar_one_or_none()
        return webauthn_credential_to_entity(model) if model else None

    async def save(self, credential: WebAuthnCredential) -> None:
        model = await self._session.get(WebAuthnCredentialModel, credential.id)
        if model:
            model.sign_count = credential.sign_count
            model.last_used_at = credential.last_used_at
            model.updated_at = credential.updated_at

    async def delete(self, credential_id: UUID, user_id: UUID) -> bool:
        model = await self._session.get(WebAuthnCredentialModel, credential_id)
        if model is None or model.user_id != user_id:
            return False
        await self._session.delete(model)
        return True

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        from controlbox.modules.identity.infrastructure.models import UserModel

        result = await self._session.execute(
            select(func.count())
            .select_from(WebAuthnCredentialModel)
            .join(UserModel, UserModel.id == WebAuthnCredentialModel.user_id)
            .where(UserModel.tenant_id == tenant_id)
        )
        return result.scalar_one() or 0


class SqlAlchemyTrustedDeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_fingerprint(self, user_id: UUID, fingerprint_hash: str) -> TrustedDevice | None:
        result = await self._session.execute(
            select(TrustedDeviceModel).where(
                TrustedDeviceModel.user_id == user_id,
                TrustedDeviceModel.fingerprint_hash == fingerprint_hash,
                TrustedDeviceModel.is_revoked.is_(False),
            )
        )
        model = result.scalar_one_or_none()
        return trusted_device_to_entity(model) if model else None

    async def list_by_user(self, user_id: UUID) -> list[TrustedDevice]:
        result = await self._session.execute(
            select(TrustedDeviceModel)
            .where(TrustedDeviceModel.user_id == user_id, TrustedDeviceModel.is_revoked.is_(False))
            .order_by(TrustedDeviceModel.last_seen_at.desc().nullslast())
        )
        return [trusted_device_to_entity(m) for m in result.scalars().all()]

    async def add(self, device: TrustedDevice) -> None:
        self._session.add(trusted_device_to_model(device))

    async def save(self, device: TrustedDevice) -> None:
        model = await self._session.get(TrustedDeviceModel, device.id)
        if model:
            model.label = device.label
            model.last_seen_at = device.last_seen_at
            model.is_revoked = device.is_revoked
            model.updated_at = device.updated_at

    async def revoke(self, device_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            update(TrustedDeviceModel)
            .where(TrustedDeviceModel.id == device_id, TrustedDeviceModel.user_id == user_id)
            .values(is_revoked=True, updated_at=utc_now())
        )
        return result.rowcount > 0


class SqlAlchemySecurityEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: SecurityEvent) -> None:
        self._session.add(security_event_to_model(event))

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[SecurityEvent]:
        result = await self._session.execute(
            select(SecurityEventModel)
            .where(SecurityEventModel.tenant_id == tenant_id)
            .order_by(SecurityEventModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [security_event_to_entity(m) for m in result.scalars().all()]

    async def count_by_tenant(self, tenant_id: UUID, since_hours: int = 24) -> int:
        from datetime import timedelta

        since = utc_now() - timedelta(hours=since_hours)
        result = await self._session.execute(
            select(SecurityEventModel)
            .where(SecurityEventModel.tenant_id == tenant_id, SecurityEventModel.created_at >= since)
        )
        return len(result.scalars().all())
