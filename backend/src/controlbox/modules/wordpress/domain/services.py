import re
from uuid import UUID

from controlbox.modules.wordpress.domain.entities import PHP_VERSIONS
from controlbox.modules.wordpress.domain.repositories import WordPressSiteRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

DOMAIN_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class WordPressDomainService:
    def __init__(self, repository: WordPressSiteRepository) -> None:
        self._sites = repository

    def validate_domain(self, domain: str) -> str:
        normalized = domain.strip().lower()
        if not DOMAIN_PATTERN.match(normalized):
            raise ValidationError("Invalid domain format")
        return normalized

    def validate_php_version(self, version: str) -> str:
        if version not in PHP_VERSIONS:
            raise ValidationError(f"Unsupported PHP version. Allowed: {', '.join(PHP_VERSIONS)}")
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
        return f"cb-wp-nginx-{short}", f"cb-wp-php-{short}"

    def build_site_url(self, domain: str, ssl: bool = True) -> str:
        scheme = "https" if ssl else "http"
        return f"{scheme}://{domain}"
