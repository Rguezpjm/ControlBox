import re
from uuid import UUID

from controlbox.modules.supabase.domain.repositories import SupabaseProjectRepository
from controlbox.shared.domain.base import ConflictError, ValidationError

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,48}$")
SCHEMA_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,62}$")


class SupabaseDomainService:
    def __init__(self, repository: SupabaseProjectRepository) -> None:
        self._projects = repository

    def validate_name(self, name: str) -> str:
        normalized = name.strip().lower().replace(" ", "-")
        if not SLUG_PATTERN.match(normalized):
            raise ValidationError("Project name must be 2-49 chars, lowercase, start with letter")
        return normalized

    def validate_schema_name(self, name: str) -> str:
        normalized = name.strip().lower()
        if normalized in ("public", "auth", "storage", "extensions", "graphql_public"):
            raise ValidationError(f"Schema '{normalized}' is reserved")
        if not SCHEMA_PATTERN.match(normalized):
            raise ValidationError("Schema name must be 2-63 chars, lowercase, start with letter")
        return normalized

    async def ensure_slug_available(self, slug: str, tenant_id: UUID) -> None:
        existing = await self._projects.get_by_slug(slug, tenant_id)
        if existing:
            raise ConflictError(f"Project '{slug}' already exists")

    def build_project_ref(self, tenant_id: UUID, slug: str) -> str:
        short = str(tenant_id).split("-")[0]
        return f"{short}-{slug}"[:32]

    def build_database_name(self, tenant_id: UUID, slug: str) -> str:
        short = str(tenant_id).split("-")[0]
        return f"sp_{short}_{slug}"[:63]

    def build_database_user(self, tenant_id: UUID, slug: str) -> str:
        short = str(tenant_id).split("-")[0]
        return f"spu_{short}_{slug}"[:32]

    def build_bucket_name(self, project_ref: str, name: str) -> str:
        return f"{project_ref}-{name}"[:63].lower()
