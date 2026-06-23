import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from jose import jwt
from passlib.context import CryptContext

from controlbox.config.settings import Settings
from controlbox.modules.identity.domain.entities import Session, User
from controlbox.shared.domain.base import UnauthorizedError, utc_now

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    session_id: UUID


@dataclass(frozen=True)
class AccessTokenClaims:
    sub: str
    tenant_id: str | None
    session_id: str
    roles: list[str]
    permissions: list[str]
    jti: str
    exp: int
    iat: int
    type: str
    is_platform_admin: bool = False


class PasswordService:
    def hash(self, password: str) -> str:
        return password_context.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return password_context.verify(password, password_hash)


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_access_token(
        self,
        user: User,
        session_id: UUID,
        roles: list[str],
        permissions: list[str],
        access_ttl_minutes: int | None = None,
    ) -> tuple[str, datetime]:
        now = utc_now()
        ttl_minutes = access_ttl_minutes or self._settings.jwt_access_token_expire_minutes
        expires_at = now + timedelta(minutes=max(1, ttl_minutes))
        payload = {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "session_id": str(session_id),
            "roles": roles,
            "permissions": permissions,
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "type": "access",
            "is_platform_admin": user.is_platform_admin,
        }
        token = jwt.encode(payload, self._settings.app_secret_key, algorithm=self._settings.jwt_algorithm)
        return token, expires_at

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._settings.app_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except Exception as exc:
            raise UnauthorizedError("Invalid or expired access token") from exc

        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")

        return AccessTokenClaims(
            sub=payload["sub"],
            tenant_id=payload.get("tenant_id"),
            session_id=payload["session_id"],
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            jti=payload["jti"],
            exp=payload["exp"],
            iat=payload["iat"],
            type=payload["type"],
            is_platform_admin=bool(payload.get("is_platform_admin", False)),
        )

    def get_refresh_token_expiry(self) -> datetime:
        return utc_now() + timedelta(days=self._settings.jwt_refresh_token_expire_days)


class SessionService:
    def __init__(self, token_service: TokenService) -> None:
        self._token_service = token_service

    def create_session(
        self,
        user: User,
        user_agent: str | None,
        ip_address: str | None,
        device_fingerprint: str | None,
        rotated_from_id: UUID | None = None,
    ) -> tuple[Session, str]:
        refresh_token = self._token_service.generate_refresh_token()
        refresh_token_hash = self._token_service.hash_token(refresh_token)
        expires_at = self._token_service.get_refresh_token_expiry()
        session = Session(
            user_id=user.id,
            tenant_id=user.tenant_id,
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            expires_at=expires_at,
            rotated_from_id=rotated_from_id,
            last_used_at=utc_now(),
        )
        return session, refresh_token

    def validate_refresh_token(self, session: Session, raw_token: str, now: datetime | None = None) -> None:
        current_time = now or utc_now()
        if not session.is_valid(current_time):
            raise UnauthorizedError("Session expired or revoked")
        token_hash = self._token_service.hash_token(raw_token)
        if token_hash != session.refresh_token_hash:
            raise UnauthorizedError("Invalid refresh token")

    def rotate_session(
        self,
        session: Session,
        user: User,
        raw_refresh_token: str,
        user_agent: str | None,
        ip_address: str | None,
        device_fingerprint: str | None,
    ) -> tuple[Session, Session, str]:
        self.validate_refresh_token(session, raw_refresh_token)
        session.revoke()
        new_session, new_refresh_token = self.create_session(
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            rotated_from_id=session.id,
        )
        return session, new_session, new_refresh_token
