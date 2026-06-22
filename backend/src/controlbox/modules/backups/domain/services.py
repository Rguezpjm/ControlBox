import re
from uuid import UUID

from controlbox.modules.backups.domain.entities import BackupDestinationType, BackupSourceType
from controlbox.modules.backups.domain.repositories import BackupDestinationRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-]{1,62}$")
CRON_PATTERN = re.compile(r"^(\S+\s+){4}\S+$")


class BackupDomainService:
    def __init__(self, destinations: BackupDestinationRepository) -> None:
        self._destinations = destinations

    def validate_name(self, name: str) -> str:
        normalized = name.strip()
        if not NAME_PATTERN.match(normalized):
            raise ValidationError("Name must be 2-63 chars, start with letter")
        return normalized

    def validate_source_type(self, source_type: str) -> BackupSourceType:
        try:
            return BackupSourceType(source_type)
        except ValueError as exc:
            raise ValidationError(f"Unsupported source type: {source_type}") from exc

    def validate_destination_type(self, destination_type: str) -> BackupDestinationType:
        try:
            return BackupDestinationType(destination_type)
        except ValueError as exc:
            raise ValidationError(f"Unsupported destination type: {destination_type}") from exc

    def validate_cron(self, expression: str) -> str:
        normalized = expression.strip()
        if not CRON_PATTERN.match(normalized):
            raise ValidationError("Invalid cron expression (use 5-field cron)")
        return normalized

    def validate_max_versions(self, max_versions: int) -> int:
        if max_versions < 1 or max_versions > 100:
            raise ValidationError("Max versions must be between 1 and 100")
        return max_versions

    def validate_retention_days(self, retention_days: int) -> int:
        if retention_days < 1 or retention_days > 365:
            raise ValidationError("Retention days must be between 1 and 365")
        return retention_days

    async def ensure_destination_name_available(self, name: str, tenant_id: UUID) -> None:
        existing = await self._destinations.list_by_tenant(tenant_id)
        if any(d.name == name for d in existing):
            raise ConflictError(f"Destination '{name}' already exists")

    def build_resource_key(self, source_type: BackupSourceType, resource_id: UUID | None) -> str:
        if resource_id:
            return f"{source_type.value}:{resource_id}"
        return f"{source_type.value}:all"
