from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.joomla.domain.entities import JoomlaBackup, JoomlaSite
from controlbox.modules.joomla.domain.repositories import JoomlaBackupRepository, JoomlaSiteRepository
from controlbox.modules.joomla.infrastructure.mappers import (
    backup_to_entity,
    backup_to_model,
    site_to_entity,
    site_to_model,
)
from controlbox.modules.joomla.infrastructure.models import JoomlaBackupModel, JoomlaSiteModel


class SqlAlchemyJoomlaSiteRepository(JoomlaSiteRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, site: JoomlaSite) -> None:
        self._session.add(site_to_model(site))

    async def save(self, site: JoomlaSite) -> None:
        await self._session.merge(site_to_model(site))

    async def get_by_id(self, site_id: UUID) -> JoomlaSite | None:
        result = await self._session.execute(select(JoomlaSiteModel).where(JoomlaSiteModel.id == site_id))
        model = result.scalar_one_or_none()
        return site_to_entity(model) if model else None

    async def get_by_id_and_tenant(self, site_id: UUID, tenant_id: UUID) -> JoomlaSite | None:
        result = await self._session.execute(
            select(JoomlaSiteModel).where(
                JoomlaSiteModel.id == site_id, JoomlaSiteModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return site_to_entity(model) if model else None

    async def get_by_domain(self, domain: str, tenant_id: UUID) -> JoomlaSite | None:
        result = await self._session.execute(
            select(JoomlaSiteModel).where(
                JoomlaSiteModel.domain == domain.lower(), JoomlaSiteModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return site_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[JoomlaSite]:
        result = await self._session.execute(
            select(JoomlaSiteModel)
            .where(JoomlaSiteModel.tenant_id == tenant_id)
            .order_by(JoomlaSiteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [site_to_entity(m) for m in result.scalars().all()]

    async def delete(self, site_id: UUID) -> None:
        await self._session.execute(delete(JoomlaSiteModel).where(JoomlaSiteModel.id == site_id))


class SqlAlchemyJoomlaBackupRepository(JoomlaBackupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, backup: JoomlaBackup) -> None:
        self._session.add(backup_to_model(backup))

    async def save(self, backup: JoomlaBackup) -> None:
        await self._session.merge(backup_to_model(backup))

    async def get_by_id_and_tenant(self, backup_id: UUID, tenant_id: UUID) -> JoomlaBackup | None:
        result = await self._session.execute(
            select(JoomlaBackupModel).where(
                JoomlaBackupModel.id == backup_id, JoomlaBackupModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return backup_to_entity(model) if model else None

    async def list_by_site(self, site_id: UUID, tenant_id: UUID) -> list[JoomlaBackup]:
        result = await self._session.execute(
            select(JoomlaBackupModel)
            .where(JoomlaBackupModel.site_id == site_id, JoomlaBackupModel.tenant_id == tenant_id)
            .order_by(JoomlaBackupModel.created_at.desc())
        )
        return [backup_to_entity(m) for m in result.scalars().all()]

    async def delete(self, backup_id: UUID) -> None:
        await self._session.execute(delete(JoomlaBackupModel).where(JoomlaBackupModel.id == backup_id))
