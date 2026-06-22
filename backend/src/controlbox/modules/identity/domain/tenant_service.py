from uuid import UUID

from controlbox.modules.identity.domain.entities import Tenant, TenantStatus, User
from controlbox.modules.identity.domain.repositories import TenantRepository, UserRepository
from controlbox.modules.identity.domain.services import PasswordService
from controlbox.shared.domain.base import ConflictError, ForbiddenError, NotFoundError, ValidationError


class TenantDomainService:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self._tenants = tenant_repository

    async def ensure_slug_available(self, slug: str) -> None:
        if await self._tenants.exists_by_slug(slug):
            raise ConflictError(f"Tenant slug '{slug}' is already taken")

    def ensure_tenant_active(self, tenant: Tenant) -> None:
        if not tenant.is_active():
            raise ForbiddenError("Tenant is not active")


class UserDomainService:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self._users = user_repository
        self._passwords = password_service

    async def ensure_email_available(self, email: str, tenant_id: UUID | None) -> None:
        existing = await self._users.get_by_email(email, tenant_id)
        if existing:
            raise ConflictError("Email is already registered")

    def validate_password_strength(self, password: str) -> None:
        if len(password) < 12:
            raise ValidationError("Password must be at least 12 characters")

    async def authenticate(
        self,
        email: str,
        password: str,
        tenant_id: UUID | None,
    ) -> User:
        if tenant_id is None:
            count = await self._users.count_by_email(email)
            if count > 1:
                raise ValidationError("tenant_slug is required for this email")
        user = await self._users.get_by_email(email, tenant_id)
        if user is None:
            raise NotFoundError("Invalid credentials")
        if not user.is_active:
            raise ForbiddenError("User account is deactivated")
        if not self._passwords.verify(password, user.password_hash):
            raise NotFoundError("Invalid credentials")
        return user

    async def resolve_user_in_tenant(self, user_id: UUID, tenant_id: UUID) -> User:
        user = await self._users.get_by_id_and_tenant(user_id, tenant_id)
        if user is None:
            raise NotFoundError("User not found in tenant")
        return user
