import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from uuid import UUID

import pyotp
from cryptography.fernet import Fernet

from controlbox.config.settings import Settings
from controlbox.shared.infrastructure.redis.client import RedisClient


@dataclass(frozen=True)
class MfaSetupResult:
    secret: str
    otpauth_url: str
    backup_codes: list[str]


class MfaService:
    def __init__(self, settings: Settings) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.app_secret_key.encode()).digest())
        self._fernet = Fernet(key)

    def generate_setup(self, email: str, issuer: str = "ControlBox") -> MfaSetupResult:
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        backup_codes = [secrets.token_hex(4) for _ in range(8)]
        return MfaSetupResult(
            secret=secret,
            otpauth_url=totp.provisioning_uri(name=email, issuer_name=issuer),
            backup_codes=backup_codes,
        )

    def encrypt_secret(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode()).decode()

    def decrypt_secret(self, encrypted: str) -> str:
        return self._fernet.decrypt(encrypted.encode()).decode()

    def verify_code(self, secret: str, code: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

    def hash_backup_code(self, code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    def verify_backup_code(self, code: str, hashes: list[str]) -> tuple[bool, list[str]]:
        code_hash = self.hash_backup_code(code.replace("-", ""))
        if code_hash not in hashes:
            return False, hashes
        return True, [h for h in hashes if h != code_hash]


class MfaChallengeStore:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client.client

    async def create(self, user_id: UUID, payload: dict, ttl: int = 300) -> str:
        token = secrets.token_urlsafe(32)
        data = {"user_id": str(user_id), **payload}
        await self._redis.setex(f"mfa_challenge:{token}", ttl, json.dumps(data))
        return token

    async def consume(self, token: str) -> dict | None:
        key = f"mfa_challenge:{token}"
        raw = await self._redis.get(key)
        if not raw:
            return None
        await self._redis.delete(key)
        return json.loads(raw)


class WebAuthnChallengeStore:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client.client

    async def store(self, challenge: str, payload: dict, ttl: int = 300) -> None:
        await self._redis.setex(f"webauthn_challenge:{challenge}", ttl, json.dumps(payload))

    async def consume(self, challenge: str) -> dict | None:
        key = f"webauthn_challenge:{challenge}"
        raw = await self._redis.get(key)
        if not raw:
            return None
        await self._redis.delete(key)
        return json.loads(raw)


def hash_fingerprint(fingerprint: str) -> str:
    return hashlib.sha256(fingerprint.encode()).hexdigest()
