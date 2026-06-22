import hashlib
import secrets

from passlib.context import CryptContext

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    full_key = f"cbdns_{prefix}_{raw[8:]}"
    key_hash = password_context.hash(full_key)
    return full_key, prefix, key_hash


def verify_api_key(full_key: str, key_hash: str) -> bool:
    return password_context.verify(full_key, key_hash)
