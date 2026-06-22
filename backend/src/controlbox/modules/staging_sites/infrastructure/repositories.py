from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from controlbox.modules.staging_sites.domain.entities import StagingSite, StagingSourceType
from controlbox.modules.staging_sites.domain.repositories import StagingSiteRepository
from controlbox.modules.staging_sites.infrastructure.mappers import staging_to_entity, staging_to_model
from controlbox.modules.staging_sites.infrastructure.models import StagingSiteModel


class SqlAlchemyStagingSiteRepository(StagingSiteRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, staging: StagingSite) -> None:
        self._session.add(staging_to_model(staging))

    async def save(self, staging: StagingSite) -> None:
        await self._session.merge(staging_to_model(staging))

    async def delete(self, staging_id: UUID) -> None:
        await self._session.execute(delete(StagingSiteModel).where(StagingSiteModel.id == staging_id))

    async def get_by_id(self, staging_id: UUID) -> StagingSite | None:
        result = await self._session.execute(select(StagingSiteModel).where(StagingSiteModel.id == staging_id))
        model = result.scalar_one_or_none()
        return staging_to_entity(model) if model else None

    async def get_by_id_and_tenant(self, staging_id: UUID, tenant_id: UUID) -> StagingSite | None:
        result = await self._session.execute(
            select(StagingSiteModel).where(
                StagingSiteModel.id == staging_id,
                StagingSiteModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return staging_to_entity(model) if model else None

    async def get_by_domain(self, domain: str, tenant_id: UUID) -> StagingSite | None:
        result = await self._session.execute(
            select(StagingSiteModel).where(
                StagingSiteModel.domain == domain.lower(),
                StagingSiteModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return staging_to_entity(model) if model else None

    async def get_by_source(
        self, source_type: StagingSourceType, source_id: UUID, tenant_id: UUID
    ) -> StagingSite | None:
        result = await self._session.execute(
            select(StagingSiteModel).where(
                StagingSiteModel.source_type == source_type.value,
                StagingSiteModel.source_id == source_id,
                StagingSiteModel.tenant_id == tenant_id,
                StagingSiteModel.status.notin_(["deleting", "error"]),
            )
        )
        model = result.scalar_one_or_none()
        return staging_to_entity(model) if model else None

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[StagingSite]:
        result = await self._session.execute(
            select(StagingSiteModel)
            .where(StagingSiteModel.tenant_id == tenant_id)
            .order_by(StagingSiteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [staging_to_entity(m) for m in result.scalars().all()]

    async def list_by_source(
        self, source_type: StagingSourceType, source_id: UUID, tenant_id: UUID
    ) -> list[StagingSite]:
        result = await self._session.execute(
            select(StagingSiteModel).where(
                StagingSiteModel.source_type == source_type.value,
                StagingSiteModel.source_id == source_id,
                StagingSiteModel.tenant_id == tenant_id,
            )
        )
        return [staging_to_entity(m) for m in result.scalars().all()]
