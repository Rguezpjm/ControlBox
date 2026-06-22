from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


DEFAULT_SECRETS_CHECKLIST = [
    "REDIS_PASSWORD",
    "REGISTRATION_INVITE_TOKEN",
    "MYSQL_ADMIN_PASSWORD",
    "MARIADB_ADMIN_PASSWORD",
    "MSSQL_ADMIN_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
    "SUPABASE_JWT_SECRET",
    "POWERDNS_API_KEY",
]


@dataclass
class TenantPlatformSettings:
    tenant_id: UUID
    cpu_threshold_percent: float = 90.0
    memory_threshold_percent: float = 90.0
    disk_threshold_percent: float = 90.0
    alerts_enabled: bool = True
    alert_cooldown_minutes: int = 15
    telegram_alerts_enabled: bool = False
    telegram_bot_token_enc: str | None = None
    telegram_chat_id: str | None = None
    cloudflare_enabled: bool = False
    cloudflare_api_token_enc: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_tunnel_enabled: bool = False
    cloudflare_tunnel_id: str | None = None
    cloudflare_tunnel_token_enc: str | None = None
    cloudflare_tunnel_hostname: str | None = None
    secrets_rotation_status: dict[str, bool] = field(default_factory=dict)
    setup_checklist: dict[str, bool] = field(default_factory=dict)
    panel_settings: dict[str, object] = field(default_factory=dict)


@dataclass
class ResourceAlert:
    id: UUID
    tenant_id: UUID
    metric: str
    severity: str
    message: str
    current_value: float
    threshold_value: float
    is_acknowledged: bool = False
    acknowledged_at: datetime | None = None
    created_at: datetime | None = None
