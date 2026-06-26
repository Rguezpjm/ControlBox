import re
from uuid import UUID

from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.modules.joomla.domain.entities import DEFAULT_PHP_VERSION
from controlbox.modules.joomla.domain.repositories import JoomlaSiteRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

DOMAIN_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class JoomlaDomainService:
    def __init__(
        self,
        repository: JoomlaSiteRepository,
        runtime_catalog: RuntimeCatalogManager | None = None,
    ) -> None:
        self._sites = repository
        self._runtime_catalog = runtime_catalog

    def validate_domain(self, domain: str) -> str:
        normalized = domain.strip().lower()
        if not DOMAIN_PATTERN.match(normalized):
            raise ValidationError("Invalid domain format")
        return normalized

    def validate_php_version(self, version: str) -> str:
        allowed = self._runtime_catalog.get_php_versions() if self._runtime_catalog else ["8.2", "8.3"]
        if version not in allowed:
            raise ValidationError(f"Versión PHP no habilitada. Disponibles: {', '.join(allowed)}")
        return version

    def validate_admin_user(self, username: str) -> str:
        cleaned = username.strip()
        if not cleaned or len(cleaned) < 3 or len(cleaned) > 60:
            raise ValidationError("Admin username must be between 3 and 60 characters")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise ValidationError("Admin username contains invalid characters")
        return cleaned

    async def ensure_domain_available(self, domain: str, tenant_id: UUID) -> None:
        existing = await self._sites.get_by_domain(domain, tenant_id)
        if existing:
            raise ConflictError(f"Domain '{domain}' is already in use")

    def build_container_names(self, site_id: UUID) -> tuple[str, str]:
        short = site_id.hex[:12]
        return f"cb-jm-nginx-{short}", f"cb-jm-php-{short}"

    def build_site_url(self, domain: str, ssl: bool = True) -> str:
        scheme = "https" if ssl else "http"
        return f"{scheme}://{domain}"
