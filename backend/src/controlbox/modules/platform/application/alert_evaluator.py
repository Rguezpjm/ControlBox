from datetime import datetime, timezone
from uuid import uuid4

from controlbox.modules.monitoring.domain.entities import MonitoringSnapshot
from controlbox.modules.monitoring.infrastructure.broadcaster import MonitoringBroadcaster
from controlbox.modules.platform.domain.entities import ResourceAlert, TenantPlatformSettings
from controlbox.shared.application.unit_of_work import UnitOfWork


METRIC_LABELS = {
    "cpu": "CPU",
    "memory": "RAM",
    "disk": "Almacenamiento",
}


class ResourceAlertEvaluator:
    def __init__(self, broadcaster: MonitoringBroadcaster | None = None) -> None:
        self._broadcaster = broadcaster

    async def evaluate(self, uow: UnitOfWork, tenant_id, snapshot: MonitoringSnapshot) -> list[ResourceAlert]:
        settings = await uow.tenant_platform_settings.get_or_create(tenant_id)
        if not settings.alerts_enabled:
            return []

        created: list[ResourceAlert] = []
        checks = [
            ("cpu", snapshot.host.cpu_percent, settings.cpu_threshold_percent),
            ("memory", snapshot.host.memory_percent, settings.memory_threshold_percent),
            ("disk", snapshot.host.disk_percent, settings.disk_threshold_percent),
        ]

        for metric, value, threshold in checks:
            if value < threshold:
                continue
            if await uow.resource_alerts.has_recent_alert(
                tenant_id, metric, settings.alert_cooldown_minutes
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

        return created
