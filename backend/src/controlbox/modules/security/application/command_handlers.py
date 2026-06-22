from uuid import UUID

from controlbox.modules.identity.application.queries import TokenResponse
from controlbox.modules.identity.domain.services import SessionService, TokenService
from controlbox.modules.security.application.commands import (
    DisableMfaCommand,
    EnableMfaCommand,
    RevokeTrustedDeviceCommand,
    SetupMfaCommand,
    UnblockIpCommand,
    UpdateSecuritySettingsCommand,
    VerifyMfaLoginCommand,
)
from controlbox.modules.security.application.queries import (
    MfaChallengeResponse,
    MfaSetupResponse,
    SecurityEventResponse,
    SecurityOverviewResponse,
    TrustedDeviceResponse,
)
from controlbox.modules.security.application.security_events import SecurityEventRecorder
from controlbox.modules.security.domain.entities import DEFAULT_SECURITY_SETTINGS, TrustedDevice, UserMfa
from controlbox.modules.security.domain.services import MfaChallengeStore, MfaService, hash_fingerprint
from controlbox.shared.application.cqrs import CommandHandler
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.domain.base import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError, utc_now
from controlbox.shared.infrastructure.redis.client import SessionCache
from controlbox.modules.team_members.application.auth_resolver import resolve_effective_auth
from controlbox.shared.infrastructure.security.audit import record_audit
from controlbox.shared.infrastructure.security.protection import IpReputation


class SetupMfaHandler(CommandHandler[SetupMfaCommand, MfaSetupResponse]):
    def __init__(self, uow: UnitOfWork, mfa_service: MfaService) -> None:
        self._uow = uow
        self._mfa = mfa_service

    async def handle(self, command: SetupMfaCommand) -> MfaSetupResponse:
        existing = await self._uow.user_mfa.get_by_user(command.user_id)
        if existing and existing.is_enabled:
            raise ValidationError("MFA is already enabled")
        setup = self._mfa.generate_setup(command.email)
        return MfaSetupResponse(
            secret=setup.secret,
            otpauth_url=setup.otpauth_url,
            backup_codes=setup.backup_codes,
        )


class EnableMfaHandler(CommandHandler[EnableMfaCommand, None]):
    def __init__(self, uow: UnitOfWork, mfa_service: MfaService, events: SecurityEventRecorder) -> None:
        self._uow = uow
        self._mfa = mfa_service
        self._events = events

    async def handle(self, command: EnableMfaCommand) -> None:
        if not self._mfa.verify_code(command.secret, command.code):
            raise ValidationError("Invalid verification code")

        backup_hashes = [self._mfa.hash_backup_code(c) for c in command.backup_codes]
        mfa = UserMfa(
            user_id=command.user_id,
            totp_secret_encrypted=self._mfa.encrypt_secret(command.secret),
            is_enabled=True,
            backup_codes_hash=backup_hashes,
        )
        await self._uow.user_mfa.save(mfa)
        await self._events.record(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            event_type="mfa_enabled",
            severity="medium",
            message="Multi-factor authentication enabled",
        )
        await record_audit(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            action="security.mfa_enabled",
            resource_type="user",
            resource_id=str(command.user_id),
        )
        await self._uow.commit()


class DisableMfaHandler(CommandHandler[DisableMfaCommand, None]):
    def __init__(self, uow: UnitOfWork, mfa_service: MfaService, events: SecurityEventRecorder) -> None:
        self._uow = uow
        self._mfa = mfa_service
        self._events = events

    async def handle(self, command: DisableMfaCommand) -> None:
        mfa = await self._uow.user_mfa.get_by_user(command.user_id)
        if mfa is None or not mfa.is_enabled:
            raise NotFoundError("MFA is not enabled")
        secret = self._mfa.decrypt_secret(mfa.totp_secret_encrypted)
        if not self._mfa.verify_code(secret, command.code):
            raise ValidationError("Invalid verification code")
        mfa.is_enabled = False
        mfa.totp_secret_encrypted = ""
        mfa.backup_codes_hash = []
        mfa.touch()
        await self._uow.user_mfa.save(mfa)
        await self._events.record(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            event_type="mfa_disabled",
            severity="high",
            message="Multi-factor authentication disabled",
        )
        await record_audit(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            action="security.mfa_disabled",
            resource_type="user",
            resource_id=str(command.user_id),
        )
        await self._uow.commit()


class VerifyMfaLoginHandler(CommandHandler[VerifyMfaLoginCommand, TokenResponse]):
    def __init__(
        self,
        uow: UnitOfWork,
        mfa_service: MfaService,
        challenge_store: MfaChallengeStore,
        token_service: TokenService,
        session_service: SessionService,
        session_cache: SessionCache,
        events: SecurityEventRecorder,
    ) -> None:
        self._uow = uow
        self._mfa = mfa_service
        self._challenges = challenge_store
        self._tokens = token_service
        self._sessions = session_service
        self._session_cache = session_cache
        self._events = events

    async def handle(self, command: VerifyMfaLoginCommand) -> TokenResponse:
        payload = await self._challenges.consume(command.challenge_token)
        if payload is None:
            raise UnauthorizedError("Invalid or expired MFA challenge")

        user_id = UUID(payload["user_id"])
        user = await self._uow.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found")

        mfa = await self._uow.user_mfa.get_by_user(user_id)
        if mfa is None or not mfa.is_enabled:
            raise UnauthorizedError("MFA not configured")

        secret = self._mfa.decrypt_secret(mfa.totp_secret_encrypted)
        valid = self._mfa.verify_code(secret, command.code)
        if not valid:
            valid, updated_hashes = self._mfa.verify_backup_code(command.code, mfa.backup_codes_hash)
            if valid:
                mfa.backup_codes_hash = updated_hashes
                mfa.touch()
                await self._uow.user_mfa.save(mfa)
        if not valid:
            await self._events.record(
                self._uow,
                tenant_id=user.tenant_id,
                user_id=user.id,
                event_type="mfa_failed",
                severity="high",
                message="Invalid MFA code during login",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
            await record_audit(
                self._uow,
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="auth.mfa_failed",
                resource_type="user",
                resource_id=str(user.id),
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
            await self._uow.commit()
            raise UnauthorizedError("Invalid MFA code")

        session, refresh_token = self._sessions.create_session(
            user=user,
            user_agent=command.user_agent,
            ip_address=command.ip_address,
            device_fingerprint=command.device_fingerprint,
        )
        await self._uow.sessions.add(session)

        if command.device_fingerprint:
            await _upsert_trusted_device(
                self._uow,
                user.id,
                command.device_fingerprint,
                command.user_agent,
                command.ip_address,
            )

        role_names, permission_codes = await resolve_effective_auth(self._uow, user.id, user.tenant_id)

        access_token, access_expires = self._tokens.create_access_token(
            user=user,
            session_id=session.id,
            roles=role_names,
            permissions=permission_codes,
        )

        await self._session_cache.store_session(
            session_id=session.id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            ttl_seconds=self._session_cache.refresh_ttl_seconds(),
        )

        await record_audit(
            self._uow,
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="auth.login",
            resource_type="session",
            resource_id=str(session.id),
            metadata={"mfa": True},
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        await self._events.record(
            self._uow,
            tenant_id=user.tenant_id,
            user_id=user.id,
            event_type="login_success",
            severity="low",
            message="Successful login with MFA",
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        await self._uow.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            access_token_expires_at=access_expires,
            refresh_token_expires_at=session.expires_at,
            session_id=session.id,
        )


class RevokeTrustedDeviceHandler(CommandHandler[RevokeTrustedDeviceCommand, None]):
    def __init__(self, uow: UnitOfWork, events: SecurityEventRecorder) -> None:
        self._uow = uow
        self._events = events

    async def handle(self, command: RevokeTrustedDeviceCommand) -> None:
        revoked = await self._uow.trusted_devices.revoke(command.device_id, command.user_id)
        if not revoked:
            raise NotFoundError("Device not found")
        await self._events.record(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            event_type="device_revoked",
            severity="medium",
            message="Trusted device revoked",
            metadata={"device_id": str(command.device_id)},
        )
        await record_audit(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            action="security.device_revoked",
            resource_type="device",
            resource_id=str(command.device_id),
        )
        await self._uow.commit()


class UpdateSecuritySettingsHandler(CommandHandler[UpdateSecuritySettingsCommand, dict]):
    def __init__(self, uow: UnitOfWork, events: SecurityEventRecorder) -> None:
        self._uow = uow
        self._events = events

    async def handle(self, command: UpdateSecuritySettingsCommand) -> dict:
        tenant = await self._uow.tenants.get_by_id(command.tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found")
        settings = dict(tenant.settings or {})
        security = dict(settings.get("security", DEFAULT_SECURITY_SETTINGS))
        security.update(command.settings)
        settings["security"] = security
        tenant.settings = settings
        tenant.touch()
        await self._uow.tenants.save(tenant)
        await record_audit(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=None,
            action="security.settings_updated",
            resource_type="tenant",
            resource_id=str(command.tenant_id),
            metadata=command.settings,
        )
        await self._uow.commit()
        return security


class UnblockIpHandler(CommandHandler[UnblockIpCommand, None]):
    def __init__(self, ip_reputation: IpReputation, uow: UnitOfWork, events: SecurityEventRecorder) -> None:
        self._ip = ip_reputation
        self._uow = uow
        self._events = events

    async def handle(self, command: UnblockIpCommand) -> None:
        await self._ip.unblock(command.ip)
        await self._events.record(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=None,
            event_type="ip_unblocked",
            severity="low",
            message=f"IP {command.ip} unblocked",
            metadata={"ip": command.ip},
        )
        await record_audit(
            self._uow,
            tenant_id=command.tenant_id,
            user_id=None,
            action="security.ip_unblocked",
            resource_type="ip",
            resource_id=command.ip,
        )
        await self._uow.commit()


async def _upsert_trusted_device(
    uow: UnitOfWork,
    user_id: UUID,
    fingerprint: str,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    fp_hash = hash_fingerprint(fingerprint)
    existing = await uow.trusted_devices.get_by_fingerprint(user_id, fp_hash)
    now = utc_now()
    if existing:
        existing.last_seen_at = now
        existing.user_agent = user_agent
        existing.ip_address = ip_address
        existing.touch()
        await uow.trusted_devices.save(existing)
    else:
        label = (user_agent or "Unknown device")[:128]
        await uow.trusted_devices.add(
            TrustedDevice(
                user_id=user_id,
                fingerprint_hash=fp_hash,
                label=label,
                user_agent=user_agent,
                ip_address=ip_address,
                last_seen_at=now,
            )
        )


async def create_mfa_challenge_if_needed(
    uow: UnitOfWork,
    user_id: UUID,
    mfa_service: MfaService,
    challenge_store: MfaChallengeStore,
    payload: dict,
) -> MfaChallengeResponse | None:
    from controlbox.modules.security.application.tenant_security import get_tenant_security_settings

    user = await uow.users.get_by_id(user_id)
    if user is None:
        return None

    tenant_settings = await get_tenant_security_settings(uow, user.tenant_id)
    mfa = await uow.user_mfa.get_by_user(user_id)

    if tenant_settings.get("enforce_mfa") and (mfa is None or not mfa.is_enabled):
        raise ForbiddenError("MFA is required for this tenant")

    fingerprint = payload.get("device_fingerprint")
    if fingerprint:
        fp_hash = hash_fingerprint(fingerprint)
        trusted = await uow.trusted_devices.get_by_fingerprint(user_id, fp_hash)
        if trusted:
            return None

    if mfa is None or not mfa.is_enabled:
        return None

    methods = ["totp"]
    credentials = await uow.webauthn_credentials.list_by_user(user_id)
    if credentials:
        methods.append("webauthn")
    token = await challenge_store.create(user_id, payload)
    return MfaChallengeResponse(mfa_required=True, challenge_token=token, methods=methods)
