import re
import secrets
from uuid import UUID

from controlbox.modules.staging_sites.domain.entities import StagingDomainMode, StagingSourceType
from controlbox.modules.staging_sites.domain.repositories import StagingSiteRepository
from controlbox.shared.domain.base import ConflictError, NotFoundError, ValidationError

DOMAIN_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class StagingDomainService:
    def __init__(self, repository: StagingSiteRepository) -> None:
        self._staging = repository

    def validate_domain(self, domain: str) -> str:
        normalized = domain.strip().lower()
        if not DOMAIN_PATTERN.match(normalized):
            raise ValidationError("Invalid domain format")
        return normalized

    def build_staging_domain(self, production_domain: str, mode: StagingDomainMode) -> str:
        production_domain = production_domain.strip().lower()
        if mode == StagingDomainMode.SUBDOMAIN:
            return f"staging.{production_domain}"
        token = secrets.token_hex(4)
        return f"{token}.staging.{production_domain}"

    async def ensure_domain_available(self, domain: str, tenant_id: UUID) -> None:
        existing = await self._staging.get_by_domain(domain, tenant_id)
        if existing:
            raise ConflictError(f"Domain '{domain}' is already in use")

    async def ensure_source_available(self, source_type: StagingSourceType, source_id: UUID, tenant_id: UUID) -> None:
        existing = await self._staging.get_by_source(source_type, source_id, tenant_id)
        if existing and existing.status not in ("error", "deleting"):
            raise ConflictError("An active staging environment already exists for this site")

    def build_container_names(self, staging_id: UUID, stack_type: str) -> tuple[str, str | None, str | None]:
        short = staging_id.hex[:12]
        if stack_type in ("wordpress", "joomla"):
            prefix = "wp" if stack_type == "wordpress" else "jm"
            return (
                f"cb-stg-{prefix}-{short}",
                f"cb-stg-{prefix}-nginx-{short}",
                f"cb-stg-{prefix}-php-{short}",
            )
        return f"cb-stg-{short}", None, None

    def build_traefik_router(self, staging_id: UUID) -> str:
        return f"stg-{str(staging_id).split('-')[0]}"

    def build_site_path(self, base_path: str, tenant_id: UUID, staging_id: UUID) -> str:
        return f"{base_path}/{tenant_id}/staging/{staging_id}"

    def resolve_stack_from_website_runtime(self, runtime: str) -> str:
        mapping = {
            "html": "html",
            "php": "php",
            "nodejs": "nodejs",
            "python": "python",
            "flutter": "html",
        }
        return mapping.get(runtime, "php")

    async def get_source_domain(self, uow, source_type: StagingSourceType, source_id: UUID, tenant_id: UUID) -> str:
        if source_type == StagingSourceType.WEBSITE:
            site = await uow.websites.get_by_id_and_tenant(source_id, tenant_id)
            if site is None:
                raise NotFoundError("Source website not found")
            return site.domain
        elif source_type == StagingSourceType.JOOMLA:
            site = await uow.joomla_sites.get_by_id_and_tenant(source_id, tenant_id)
            if site is None:
                raise NotFoundError("Source Joomla site not found")
            return site.domain
        site = await uow.wordpress_sites.get_by_id_and_tenant(source_id, tenant_id)
        if site is None:
            raise NotFoundError("Source WordPress site not found")
        return site.domain

