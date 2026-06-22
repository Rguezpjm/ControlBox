from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from controlbox.modules.identity.infrastructure.models import Base, TimestampMixin
from controlbox.modules.platform.domain.entities import DEFAULT_SECRETS_CHECKLIST, ResourceAlert, TenantPlatformSettings


class TenantPlatformSettingsModel(Base, TimestampMixin):
    __tablename__ = "tenant_platform_settings"

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cpu_threshold_percent: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)
    memory_threshold_percent: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)
    disk_threshold_percent: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    telegram_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_bot_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cloudflare_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cloudflare_api_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    cloudflare_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cloudflare_tunnel_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cloudflare_tunnel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cloudflare_tunnel_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    cloudflare_tunnel_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secrets_rotation_status: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    setup_checklist: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    panel_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class TenantResourceAlertModel(Base):
    __tablename__ = "tenant_resource_alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _default_secrets_status() -> dict[str, bool]:
    return {key: False for key in DEFAULT_SECRETS_CHECKLIST}


def settings_to_entity(model: TenantPlatformSettingsModel) -> TenantPlatformSettings:
    secrets = model.secrets_rotation_status or {}
    merged = _default_secrets_status()
    merged.update({k: bool(v) for k, v in secrets.items()})
    return TenantPlatformSettings(
        tenant_id=model.tenant_id,
        cpu_threshold_percent=model.cpu_threshold_percent,
        memory_threshold_percent=model.memory_threshold_percent,
        disk_threshold_percent=model.disk_threshold_percent,
        alerts_enabled=model.alerts_enabled,
        alert_cooldown_minutes=model.alert_cooldown_minutes,
        telegram_alerts_enabled=model.telegram_alerts_enabled,
        telegram_bot_token_enc=model.telegram_bot_token_enc,
        telegram_chat_id=model.telegram_chat_id,
        cloudflare_enabled=model.cloudflare_enabled,
        cloudflare_api_token_enc=model.cloudflare_api_token_enc,
        cloudflare_account_id=model.cloudflare_account_id,
        cloudflare_tunnel_enabled=model.cloudflare_tunnel_enabled,
        cloudflare_tunnel_id=model.cloudflare_tunnel_id,
        cloudflare_tunnel_token_enc=model.cloudflare_tunnel_token_enc,
        cloudflare_tunnel_hostname=model.cloudflare_tunnel_hostname,
        secrets_rotation_status=merged,
        setup_checklist=model.setup_checklist or {},
        panel_settings=model.panel_settings or {},
    )


def settings_to_model(entity: TenantPlatformSettings) -> TenantPlatformSettingsModel:
    return TenantPlatformSettingsModel(
        tenant_id=entity.tenant_id,
        cpu_threshold_percent=entity.cpu_threshold_percent,
        memory_threshold_percent=entity.memory_threshold_percent,
        disk_threshold_percent=entity.disk_threshold_percent,
        alerts_enabled=entity.alerts_enabled,
        alert_cooldown_minutes=entity.alert_cooldown_minutes,
        telegram_alerts_enabled=entity.telegram_alerts_enabled,
        telegram_bot_token_enc=entity.telegram_bot_token_enc,
        telegram_chat_id=entity.telegram_chat_id,
        cloudflare_enabled=entity.cloudflare_enabled,
        cloudflare_api_token_enc=entity.cloudflare_api_token_enc,
        cloudflare_account_id=entity.cloudflare_account_id,
        cloudflare_tunnel_enabled=entity.cloudflare_tunnel_enabled,
        cloudflare_tunnel_id=entity.cloudflare_tunnel_id,
        cloudflare_tunnel_token_enc=entity.cloudflare_tunnel_token_enc,
        cloudflare_tunnel_hostname=entity.cloudflare_tunnel_hostname,
        secrets_rotation_status=entity.secrets_rotation_status,
        setup_checklist=entity.setup_checklist,
        panel_settings=entity.panel_settings,
    )


def alert_to_entity(model: TenantResourceAlertModel) -> ResourceAlert:
    return ResourceAlert(
        id=model.id,
        tenant_id=model.tenant_id,
        metric=model.metric,
        severity=model.severity,
        message=model.message,
        current_value=model.current_value,
        threshold_value=model.threshold_value,
        is_acknowledged=model.is_acknowledged,
        acknowledged_at=model.acknowledged_at,
        created_at=model.created_at,
    )


def alert_to_model(alert: ResourceAlert) -> TenantResourceAlertModel:
    return TenantResourceAlertModel(
        id=alert.id,
        tenant_id=alert.tenant_id,
        metric=alert.metric,
        severity=alert.severity,
        message=alert.message,
        current_value=alert.current_value,
        threshold_value=alert.threshold_value,
        is_acknowledged=alert.is_acknowledged,
        acknowledged_at=alert.acknowledged_at,
        created_at=alert.created_at,
    )
