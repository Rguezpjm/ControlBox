import re
from uuid import UUID

from controlbox.modules.databases.domain.entities import DatabaseEngineType
from controlbox.modules.databases.domain.repositories import ManagedDatabaseRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


class DatabaseDomainService:
    def __init__(self, repository: ManagedDatabaseRepository) -> None:
        self._databases = repository

    def validate_name(self, name: str) -> str:
        normalized = name.strip().lower()
        if not NAME_PATTERN.match(normalized):
            raise ValidationError("Database name must be 2-63 chars, lowercase, start with letter")
        return normalized

    def validate_username(self, username: str) -> str:
        normalized = username.strip().lower()
        if not USERNAME_PATTERN.match(normalized):
            raise ValidationError("Username must be 2-31 chars, lowercase, start with letter")
        return normalized

    def validate_engine(self, engine: str) -> DatabaseEngineType:
        try:
            return DatabaseEngineType(engine)
        except ValueError as exc:
            raise ValidationError(f"Unsupported engine: {engine}") from exc

    async def ensure_name_available(self, name: str, tenant_id: UUID) -> None:
        existing = await self._databases.get_by_name(name, tenant_id)
        if existing:
            raise ConflictError(f"Database '{name}' already exists")

    def build_database_name(self, tenant_id: UUID, name: str) -> str:
        short = str(tenant_id).split("-")[0]
        return f"db_{short}_{name}"[:63]

    def build_username(self, tenant_id: UUID, username: str) -> str:
        short = str(tenant_id).split("-")[0]
        return f"u_{short}_{username}"[:32]
