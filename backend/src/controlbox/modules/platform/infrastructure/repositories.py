from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from controlbox.modules.platform.domain.entities import ResourceAlert, TenantPlatformSettings
from controlbox.modules.platform.domain.repositories import ResourceAlertRepository, TenantPlatformSettingsRepository
from controlbox.modules.platform.infrastructure.models import (
    TenantPlatformSettingsModel,
    TenantResourceAlertModel,
    alert_to_entity,
    alert_to_model,
    settings_to_entity,
    settings_to_model,
    _default_secrets_status,
)
from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyTenantPlatformSettingsRepository(TenantPlatformSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, tenant_id: UUID) -> TenantPlatformSettings:
        result = await self._session.execute(
            select(TenantPlatformSettingsModel).where(TenantPlatformSettingsModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        if model:
            return settings_to_entity(model)
        entity = TenantPlatformSettings(
            tenant_id=tenant_id,
            secrets_rotation_status=_default_secrets_status(),
        )
        self._session.add(settings_to_model(entity))
        return entity

    async def save(self, settings: TenantPlatformSettings) -> None:
        await self._session.merge(settings_to_model(settings))


class SqlAlchemyResourceAlertRepository(ResourceAlertRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, alert: ResourceAlert) -> None:
        self._session.add(alert_to_model(alert))

    async def get_by_id(self, alert_id: UUID, tenant_id: UUID) -> ResourceAlert | None:
        result = await self._session.execute(
            select(TenantResourceAlertModel).where(
                TenantResourceAlertModel.id == alert_id,
                TenantResourceAlertModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return alert_to_entity(model) if model else None

    async def list_active(self, tenant_id: UUID, limit: int = 50) -> list[ResourceAlert]:
        result = await self._session.execute(
            select(TenantResourceAlertModel)
            .where(
                TenantResourceAlertModel.tenant_id == tenant_id,
                TenantResourceAlertModel.is_acknowledged.is_(False),
            )
            .order_by(TenantResourceAlertModel.created_at.desc())
            .limit(limit)
        )
        return [alert_to_entity(m) for m in result.scalars().all()]

    async def list_recent(self, tenant_id: UUID, limit: int = 50) -> list[ResourceAlert]:
        result = await self._session.execute(
            select(TenantResourceAlertModel)
            .where(TenantResourceAlertModel.tenant_id == tenant_id)
            .order_by(TenantResourceAlertModel.created_at.desc())
            .limit(limit)
        )
        return [alert_to_entity(m) for m in result.scalars().all()]

    async def count_active(self, tenant_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(TenantResourceAlertModel)
            .where(
                TenantResourceAlertModel.tenant_id == tenant_id,
                TenantResourceAlertModel.is_acknowledged.is_(False),
            )
        )
        return int(result.scalar_one() or 0)

    async def save(self, alert: ResourceAlert) -> None:
        await self._session.merge(alert_to_model(alert))

    async def has_recent_alert(self, tenant_id: UUID, metric: str, within_minutes: int) -> bool:
        since = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        result = await self._session.execute(
            select(func.count())
            .select_from(TenantResourceAlertModel)
            .where(
                TenantResourceAlertModel.tenant_id == tenant_id,
                TenantResourceAlertModel.metric == metric,
                TenantResourceAlertModel.created_at >= since,
            )
        )
        return int(result.scalar_one() or 0) > 0
