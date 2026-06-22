import logging

from datetime import datetime, timezone
from uuid import uuid4

from controlbox.config.settings import Settings
from controlbox.modules.monitoring.domain.entities import MonitoringSnapshot
from controlbox.modules.monitoring.infrastructure.broadcaster import MonitoringBroadcaster
from controlbox.modules.platform.domain.entities import ResourceAlert
from controlbox.modules.platform.infrastructure.panel_settings import PanelSettingsService
from controlbox.shared.application.unit_of_work import UnitOfWork

logger = logging.getLogger("controlbox.alerts")


METRIC_LABELS = {
    "cpu": "CPU",
    "memory": "RAM",
    "disk": "Almacenamiento",
}


class ResourceAlertEvaluator:
    def __init__(
        self,
        broadcaster: MonitoringBroadcaster | None = None,
        app_settings: Settings | None = None,
    ) -> None:
        self._broadcaster = broadcaster
        self._panel_settings = PanelSettingsService(app_settings) if app_settings else None

    async def evaluate(self, uow: UnitOfWork, tenant_id, snapshot: MonitoringSnapshot) -> list[ResourceAlert]:
        platform_settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
        if not platform_settings.alerts_enabled:
            return []

        created: list[ResourceAlert] = []
        checks = [
            ("cpu", snapshot.host.cpu_percent, platform_settings.cpu_threshold_percent),
            ("memory", snapshot.host.memory_percent, platform_settings.memory_threshold_percent),
            ("disk", snapshot.host.disk_percent, platform_settings.disk_threshold_percent),
        ]

        for metric, value, threshold in checks:
            if value < threshold:
                continue
            if await uow.resource_alerts.has_recent_alert(
                tenant_id, metric, platform_settings.alert_cooldown_minutes
            ):
                continue

            label = METRIC_LABELS.get(metric, metric.upper())
            severity = "critical" if value >= 99 else "warning"
            alert = ResourceAlert(
                id=uuid4(),
                tenant_id=tenant_id,
                metric=metric,
                severity=severity,
                message=f"{label} al {value:.1f}% (umbral: {threshold:.0f}%)",
                current_value=round(value, 2),
                threshold_value=threshold,
                created_at=datetime.now(timezone.utc),
            )
            await uow.resource_alerts.add(alert)
            created.append(alert)

            if self._broadcaster:
                await self._broadcaster.broadcast_alert(
                    tenant_id,
                    {
                        "id": str(alert.id),
                        "metric": alert.metric,
                        "severity": alert.severity,
                        "message": alert.message,
                        "current_value": alert.current_value,
                        "threshold_value": alert.threshold_value,
                    },
                )

            if self._panel_settings:
                try:
                    await self._panel_settings.notify_telegram_alert(
                        platform_settings,
                        message=alert.message,
                        severity=alert.severity,
                    )
                except Exception as exc:
                    logger.warning("Telegram alert delivery failed: %s", exc)

        return created
