import re
from uuid import UUID

from controlbox.modules.dns.domain.entities import DnsRecordType
from controlbox.modules.dns.domain.repositories import DnsZoneRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

ZONE_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class DnsDomainService:
    def __init__(self, repository: DnsZoneRepository) -> None:
        self._zones = repository

    def normalize_zone_name(self, name: str) -> str:
        normalized = name.strip().lower().rstrip(".")
        if not ZONE_PATTERN.match(normalized):
            raise ValidationError("Invalid zone name format")
        return normalized

    def normalize_record_name(self, name: str, zone_name: str) -> str:
        normalized = name.strip().lower().rstrip(".")
        if normalized in ("@", ""):
            return zone_name
        if normalized.endswith(f".{zone_name}"):
            return normalized
        if "." not in normalized:
            return f"{normalized}.{zone_name}"
        return normalized

    def validate_record_type(self, record_type: str) -> DnsRecordType:
        try:
            return DnsRecordType(record_type.upper())
        except ValueError as exc:
            raise ValidationError(f"Unsupported record type: {record_type}") from exc

    async def ensure_zone_available(self, name: str, tenant_id: UUID) -> None:
        existing = await self._zones.get_by_name_global(name)
        if existing:
            raise ConflictError(f"Zone '{name}' is already registered on the platform")

    def fqdn(self, name: str) -> str:
        if not name.endswith("."):
            return f"{name}."
        return name
