import base64
import hashlib

from cryptography.fernet import Fernet

from controlbox.config.settings import Settings


class SecretEncryptor:
    def __init__(self, settings: Settings) -> None:
        key_material = hashlib.sha256(settings.app_secret_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(key_material))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()
