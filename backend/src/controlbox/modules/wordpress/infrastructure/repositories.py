from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.wordpress.domain.entities import WordPressBackup, WordPressSite
from controlbox.modules.wordpress.domain.repositories import WordPressBackupRepository, WordPressSiteRepository
from controlbox.modules.wordpress.infrastructure.mappers import (
    backup_to_entity,
    backup_to_model,
    site_to_entity,
    site_to_model,
)
from controlbox.modules.wordpress.infrastructure.models import WordPressBackupModel, WordPressSiteModel


class SqlAlchemyWordPressSiteRepository(WordPressSiteRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, site: WordPressSite) -> None:
        self._session.add(site_to_model(site))

    async def save(self, site: WordPressSite) -> None:
        await self._session.merge(site_to_model(site))

    async def get_by_id(self, site_id: UUID) -> WordPressSite | None:
        result = await self._session.execute(select(WordPressSiteModel).where(WordPressSiteModel.id == site_id))
        model = result.scalar_one_or_none()
        return site_to_entity(model) if model else None

    async def get_by_id_and_tenant(self, site_id: UUID, tenant_id: UUID) -> WordPressSite | None:
        result = await self._session.execute(
            select(WordPressSiteModel).where(
                WordPressSiteModel.id == site_id, WordPressSiteModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return site_to_entity(model) if model else None

    async def get_by_domain(self, domain: str, tenant_id: UUID) -> WordPressSite | None:
        result = await self._session.execute(
            select(WordPressSiteModel).where(
                WordPressSiteModel.domain == domain.lower(), WordPressSiteModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return site_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[WordPressSite]:
        result = await self._session.execute(
            select(WordPressSiteModel)
            .where(WordPressSiteModel.tenant_id == tenant_id)
            .order_by(WordPressSiteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [site_to_entity(m) for m in result.scalars().all()]

    async def delete(self, site_id: UUID) -> None:
        await self._session.execute(delete(WordPressSiteModel).where(WordPressSiteModel.id == site_id))


class SqlAlchemyWordPressBackupRepository(WordPressBackupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, backup: WordPressBackup) -> None:
        self._session.add(backup_to_model(backup))

    async def save(self, backup: WordPressBackup) -> None:
        await self._session.merge(backup_to_model(backup))

    async def get_by_id_and_tenant(self, backup_id: UUID, tenant_id: UUID) -> WordPressBackup | None:
        result = await self._session.execute(
            select(WordPressBackupModel).where(
                WordPressBackupModel.id == backup_id, WordPressBackupModel.tenant_id == tenant_id
            )
        )
        model = result.scalar_one_or_none()
        return backup_to_entity(model) if model else None

    async def list_by_site(self, site_id: UUID, tenant_id: UUID) -> list[WordPressBackup]:
        result = await self._session.execute(
            select(WordPressBackupModel)
            .where(WordPressBackupModel.site_id == site_id, WordPressBackupModel.tenant_id == tenant_id)
            .order_by(WordPressBackupModel.created_at.desc())
        )
        return [backup_to_entity(m) for m in result.scalars().all()]

    async def delete(self, backup_id: UUID) -> None:
        await self._session.execute(delete(WordPressBackupModel).where(WordPressBackupModel.id == backup_id))
