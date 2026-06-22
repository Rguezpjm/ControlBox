import re
from uuid import UUID

from controlbox.modules.platform.infrastructure.runtime_catalog import RuntimeCatalogManager
from controlbox.modules.websites.domain.entities import (
    DEFAULT_RUNTIME_VERSIONS,
    RUNTIME_VERSIONS,
    DatabaseEngine,
    WebsiteRuntime,
)
from controlbox.modules.websites.domain.repositories import WebsiteRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


class WebsiteDomainService:
    def __init__(
        self,
        repository: WebsiteRepository,
        runtime_catalog: RuntimeCatalogManager | None = None,
    ) -> None:
        self._websites = repository
        self._runtime_catalog = runtime_catalog

    def validate_domain(self, domain: str) -> str:
        normalized = domain.strip().lower()
        if not DOMAIN_PATTERN.match(normalized):
            raise ValidationError("Invalid domain format")
        return normalized

    def validate_runtime_version(self, runtime: WebsiteRuntime, version: str | None) -> str:
        if runtime == WebsiteRuntime.HTML:
            return ""
        if self._runtime_catalog:
            allowed = self._runtime_catalog.get_enabled_by_runtime().get(runtime.value, [])
            default = self._runtime_catalog.get_default_version(runtime.value) or DEFAULT_RUNTIME_VERSIONS[runtime]
        else:
            allowed = RUNTIME_VERSIONS.get(runtime, [])
            default = DEFAULT_RUNTIME_VERSIONS[runtime]
        resolved = version or default
        if resolved not in allowed:
            raise ValidationError(
                f"Versión '{resolved}' no habilitada para {runtime.value}. "
                f"Disponibles: {', '.join(allowed) or 'ninguna'}"
            )
        return resolved

    def validate_database_engine(self, engine: DatabaseEngine) -> DatabaseEngine:
        if engine not in DatabaseEngine:
            raise ValidationError("Invalid database engine")
        return engine

    async def ensure_domain_available(self, domain: str, tenant_id: UUID) -> None:
        existing = await self._websites.get_by_domain(domain, tenant_id)
        if existing:
            raise ConflictError(f"Domain '{domain}' is already in use")

    def build_container_name(self, tenant_id: UUID, website_id: UUID) -> str:
        short_tenant = str(tenant_id).split("-")[0]
        short_site = str(website_id).split("-")[0]
        return f"cb-site-{short_tenant}-{short_site}"
