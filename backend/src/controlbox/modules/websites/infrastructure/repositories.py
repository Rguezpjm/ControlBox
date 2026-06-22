from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.websites.domain.entities import Website
from controlbox.modules.websites.domain.repositories import WebsiteRepository
from controlbox.modules.websites.infrastructure.mappers import website_to_entity, website_to_model
from controlbox.modules.websites.infrastructure.models import WebsiteModel


class SqlAlchemyWebsiteRepository(WebsiteRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, website: Website) -> None:
        self._session.add(website_to_model(website))

    async def save(self, website: Website) -> None:
        await self._session.merge(website_to_model(website))

    async def get_by_id(self, website_id: UUID) -> Website | None:
        result = await self._session.execute(select(WebsiteModel).where(WebsiteModel.id == website_id))
        model = result.scalar_one_or_none()
        return website_to_entity(model) if model else None

    async def get_by_id_and_tenant(self, website_id: UUID, tenant_id: UUID) -> Website | None:
        result = await self._session.execute(
            select(WebsiteModel).where(WebsiteModel.id == website_id, WebsiteModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return website_to_entity(model) if model else None

    async def get_by_domain(self, domain: str, tenant_id: UUID) -> Website | None:
        result = await self._session.execute(
            select(WebsiteModel).where(WebsiteModel.domain == domain.lower(), WebsiteModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return website_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[Website]:
        result = await self._session.execute(
            select(WebsiteModel)
            .where(WebsiteModel.tenant_id == tenant_id)
            .order_by(WebsiteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [website_to_entity(m) for m in result.scalars().all()]

    async def delete(self, website_id: UUID) -> None:
        await self._session.execute(delete(WebsiteModel).where(WebsiteModel.id == website_id))

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(WebsiteModel).where(WebsiteModel.tenant_id == tenant_id)
        )
        return result.scalar_one() or 0
