import re
from uuid import UUID

from controlbox.modules.ftp.domain.repositories import FtpAccountRepository
from controlbox.shared.domain.base import ConflictError, ForbiddenError, ValidationError

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
DIRECTORY_PATTERN = re.compile(r"^[a-zA-Z0-9_./-]*$")


class FtpDomainService:
    def __init__(self, repository: FtpAccountRepository) -> None:
        self._accounts = repository

    def validate_username(self, username: str) -> str:
        normalized = username.strip().lower()
        if not USERNAME_PATTERN.match(normalized):
            raise ValidationError("Username must be 2-31 chars, lowercase, start with letter")
        return normalized

    def validate_directory(self, directory: str) -> str:
        normalized = directory.replace("\\", "/").strip("/")
        if ".." in normalized.split("/"):
            raise ForbiddenError("Path traversal not allowed")
        if normalized and not DIRECTORY_PATTERN.match(normalized):
            raise ValidationError("Directory contains invalid characters")
        return normalized

    def validate_quota(self, quota_mb: int) -> int:
        if quota_mb < 0 or quota_mb > 102400:
            raise ValidationError("Quota must be between 0 and 102400 MB")
        return quota_mb

    def validate_max_files(self, max_files: int) -> int:
        if max_files < 0 or max_files > 1_000_000:
            raise ValidationError("Max files must be between 0 and 1000000")
        return max_files

    async def ensure_username_available(self, username: str, tenant_id: UUID) -> None:
        existing = await self._accounts.get_by_username(username, tenant_id)
        if existing:
            raise ConflictError(f"FTP account '{username}' already exists")

    def build_system_username(self, tenant_id: UUID, username: str) -> str:
        short = str(tenant_id).split("-")[0]
        return f"ftp_{short}_{username}"[:48]
