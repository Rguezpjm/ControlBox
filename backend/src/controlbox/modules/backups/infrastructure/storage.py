import asyncio
import hashlib
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.modules.backups.domain.entities import BackupDestination, BackupDestinationType
from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor


class StorageAdapter(ABC):
    @abstractmethod
    async def upload(self, local_path: Path, remote_key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def download(self, remote_key: str, local_path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, remote_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def test_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_download_url(self, remote_key: str, expires_seconds: int = 3600) -> str | None:
        raise NotImplementedError


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, destination: BackupDestination, settings: Settings) -> None:
        base = destination.local_path or settings.backups_base_path
        self._root = Path(base)

    async def upload(self, local_path: Path, remote_key: str) -> str:
        target = self._root / remote_key
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, local_path, target)
        return remote_key

    async def download(self, remote_key: str, local_path: Path) -> None:
        source = self._root / remote_key
        if not source.exists():
            raise FileNotFoundError(f"Backup file not found: {remote_key}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, source, local_path)

    async def delete(self, remote_key: str) -> None:
        target = self._root / remote_key
        if target.exists():
            await asyncio.to_thread(target.unlink)

    async def test_connection(self) -> bool:
        self._root.mkdir(parents=True, exist_ok=True)
        test_file = self._root / ".connection_test"
        await asyncio.to_thread(test_file.write_text, "ok", encoding="utf-8")
        await asyncio.to_thread(test_file.unlink)
        return True

    async def get_download_url(self, remote_key: str, expires_seconds: int = 3600) -> str | None:
        return None


class S3CompatibleStorageAdapter(StorageAdapter):
    def __init__(self, destination: BackupDestination, settings: Settings) -> None:
        self._destination = destination
        self._encryptor = SecretEncryptor(settings)
        self._bucket = destination.bucket
        self._prefix = destination.prefix.strip("/")

    def _client(self):
        import boto3
        from botocore.config import Config

        access_key = self._encryptor.decrypt(self._destination.access_key_encrypted) if self._destination.access_key_encrypted else ""
        secret_key = self._encryptor.decrypt(self._destination.secret_key_encrypted) if self._destination.secret_key_encrypted else ""

        kwargs: dict = {
            "service_name": "s3",
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": self._destination.region or "us-east-1",
            "config": Config(signature_version="s3v4"),
        }
        if self._destination.endpoint:
            kwargs["endpoint_url"] = self._destination.endpoint
        return boto3.client(**kwargs)

    def _full_key(self, remote_key: str) -> str:
        if self._prefix:
            return f"{self._prefix}/{remote_key.lstrip('/')}"
        return remote_key.lstrip("/")

    async def upload(self, local_path: Path, remote_key: str) -> str:
        key = self._full_key(remote_key)

        def _upload() -> None:
            self._client().upload_file(str(local_path), self._bucket, key)

        await asyncio.to_thread(_upload)
        return key

    async def download(self, remote_key: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)

        def _download() -> None:
            self._client().download_file(self._bucket, remote_key, str(local_path))

        await asyncio.to_thread(_download)

    async def delete(self, remote_key: str) -> None:
        def _delete() -> None:
            self._client().delete_object(Bucket=self._bucket, Key=remote_key)

        await asyncio.to_thread(_delete)

    async def test_connection(self) -> bool:
        def _test() -> bool:
            client = self._client()
            client.head_bucket(Bucket=self._bucket)
            return True

        return await asyncio.to_thread(_test)

    async def get_download_url(self, remote_key: str, expires_seconds: int = 3600) -> str | None:
        def _url() -> str:
            return self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": remote_key},
                ExpiresIn=expires_seconds,
            )

        return await asyncio.to_thread(_url)


class StorageAdapterFactory:
    @staticmethod
    def create(destination: BackupDestination, settings: Settings) -> StorageAdapter:
        if destination.destination_type == BackupDestinationType.LOCAL:
            return LocalStorageAdapter(destination, settings)
        return S3CompatibleStorageAdapter(destination, settings)


def compute_file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
