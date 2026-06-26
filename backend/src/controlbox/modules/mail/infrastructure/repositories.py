from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.mail.domain.entities import MailAccount, TenantMailService
from controlbox.modules.mail.infrastructure.mappers import account_to_entity, account_to_model, service_to_entity, service_to_model
from controlbox.modules.mail.infrastructure.models import MailAccountModel, TenantMailServiceModel


class TenantMailServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, service: TenantMailService) -> None:
        self._session.add(service_to_model(service))

    async def save(self, service: TenantMailService) -> None:
        await self._session.merge(service_to_model(service))

    async def get_by_tenant(self, tenant_id: UUID) -> TenantMailService | None:
        result = await self._session.execute(
            select(TenantMailServiceModel).where(TenantMailServiceModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return service_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> list[TenantMailService]:
        result = await self._session.execute(
            select(TenantMailServiceModel)
            .where(TenantMailServiceModel.tenant_id == tenant_id)
            .order_by(TenantMailServiceModel.created_at.desc())
        )
        return [service_to_entity(m) for m in result.scalars().all()]

    async def get_by_id_and_tenant(self, service_id: UUID, tenant_id: UUID) -> TenantMailService | None:
        result = await self._session.execute(
            select(TenantMailServiceModel).where(
                TenantMailServiceModel.id == service_id,
                TenantMailServiceModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return service_to_entity(model) if model else None

    async def get_by_tenant_and_domain(self, tenant_id: UUID, domain: str) -> TenantMailService | None:
        result = await self._session.execute(
            select(TenantMailServiceModel).where(
                TenantMailServiceModel.tenant_id == tenant_id,
                TenantMailServiceModel.mail_domain == domain.lower(),
            )
        )
        model = result.scalar_one_or_none()
        return service_to_entity(model) if model else None

    async def delete(self, service_id: UUID) -> None:
        await self._session.execute(delete(TenantMailServiceModel).where(TenantMailServiceModel.id == service_id))


class MailAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: MailAccount) -> None:
        self._session.add(account_to_model(account))

    async def save(self, account: MailAccount) -> None:
        await self._session.merge(account_to_model(account))

    async def get_by_id(self, account_id: UUID, tenant_id: UUID) -> MailAccount | None:
        result = await self._session.execute(
            select(MailAccountModel).where(
                MailAccountModel.id == account_id,
                MailAccountModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return account_to_entity(model) if model else None

    async def get_by_local_part(self, mail_service_id: UUID, local_part: str) -> MailAccount | None:
        result = await self._session.execute(
            select(MailAccountModel).where(
                MailAccountModel.mail_service_id == mail_service_id,
                MailAccountModel.local_part == local_part.lower(),
            )
        )
        model = result.scalar_one_or_none()
        return account_to_entity(model) if model else None

    async def list_by_service(self, mail_service_id: UUID, tenant_id: UUID) -> list[MailAccount]:
        result = await self._session.execute(
            select(MailAccountModel)
            .where(
                MailAccountModel.mail_service_id == mail_service_id,
                MailAccountModel.tenant_id == tenant_id,
            )
            .order_by(MailAccountModel.created_at.desc())
        )
        return [account_to_entity(m) for m in result.scalars().all()]

    async def delete(self, account_id: UUID) -> None:
        await self._session.execute(delete(MailAccountModel).where(MailAccountModel.id == account_id))

    async def sum_quota_and_usage(self, mail_service_id: UUID) -> tuple[int, int, int]:
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(MailAccountModel.quota_mb), 0),
                func.coalesce(func.sum(MailAccountModel.used_mb), 0),
                func.count(MailAccountModel.id),
            ).where(MailAccountModel.mail_service_id == mail_service_id)
        )
        row = result.one()
        return int(row[0]), int(row[1]), int(row[2])
