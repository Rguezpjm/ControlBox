from pydantic import BaseModel, Field


class PanelConfigSchema(BaseModel):
    panel_port: int
    panel_base_path: str
    panel_url_hint: str
    can_apply_changes: bool


class UpdatePanelConfigRequest(BaseModel):
    panel_port: int | None = Field(default=None, ge=1024, le=65535)
    panel_base_path: str | None = Field(default=None, min_length=1, max_length=128)


class UpdatePanelConfigResponse(BaseModel):
    applied: bool
    requires_panel_rebuild: bool = False
    requires_restart: bool = False
    requires_manual_step: bool = False
    message: str


class AlertThresholdsSchema(BaseModel):
    cpu_threshold_percent: float = Field(ge=50, le=100)
    memory_threshold_percent: float = Field(ge=50, le=100)
    disk_threshold_percent: float = Field(ge=50, le=100)
    alerts_enabled: bool
    alert_cooldown_minutes: int = Field(ge=5, le=1440)


class SecretRotationItemSchema(BaseModel):
    key: str
    label: str
    rotated: bool
    required: bool = True


class SecretsRotationSchema(BaseModel):
    items: list[SecretRotationItemSchema]
    all_rotated: bool
    production_ready: bool


class AcknowledgeSecretRequest(BaseModel):
    secret_key: str


class SetupChecklistItemSchema(BaseModel):
    key: str
    label: str
    completed: bool


class SetupChecklistSchema(BaseModel):
    items: list[SetupChecklistItemSchema]
    completed_count: int
    total_count: int
    production_ready: bool


class UpdateSetupChecklistRequest(BaseModel):
    key: str
    completed: bool


class ServiceProfileSchema(BaseModel):
    id: str
    profile: str
    name: str
    category: str
    description: str
    enabled: bool
    running: bool
    requires: list[str] = Field(default_factory=list)


class ServicesOverviewSchema(BaseModel):
    can_manage: bool
    enabled_profiles: list[str]
    services: list[ServiceProfileSchema]
    message: str = ""


class ApplyServicesRequest(BaseModel):
    profiles: list[str] = Field(min_length=1)


class ApplyServicesResponse(BaseModel):
    success: bool
    message: str
    enabled_profiles: list[str] = Field(default_factory=list)


class ResourceAlertSchema(BaseModel):
    id: str
    metric: str
    severity: str
    message: str
    current_value: float
    threshold_value: float
    is_acknowledged: bool
    created_at: str | None


class PlatformOverviewSchema(BaseModel):
    panel: PanelConfigSchema
    alert_thresholds: AlertThresholdsSchema
    secrets_rotation: SecretsRotationSchema
    setup_checklist: SetupChecklistSchema
    active_alerts_count: int
    is_production_ready: bool


class SystemInfoSchema(BaseModel):
    version: str
    os_label: str
    profile: str
    edition: str = "PRO"


class OperationResultSchema(BaseModel):
    success: bool
    message: str
    detail: str | None = None


class UpdateCheckSchema(BaseModel):
    current_version: str
    latest_version: str | None
    update_available: bool
    source: str
    release_url: str | None = None
    tarball_url: str | None = None


class ServerTimeSchema(BaseModel):
    iso: str
    display: str
    timezone: str


class PanelSettingsSchema(BaseModel):
    panel_alias: str = ""
    session_timeout_hours: int = Field(default=24, ge=1, le=168)
    panel_port: int
    panel_base_path: str
    panel_url_hint: str
    can_apply_host_changes: bool
    default_site_folder: str
    default_backup_folder: str
    server_ip: str = ""
    server_time: ServerTimeSchema
    ipv6_enabled: bool = False
    offline_mode: bool = False
    cdn_proxy: bool = False
    site_monitor_enabled: bool = True
    auto_fetch_favicon: bool = True
    auto_backup_panel: bool = True
    auto_backup_retention: int = 30
    auto_backup_count: int = 0
    auto_backup_used_mb: float = 0.0
    cpu_threshold_percent: float = 90.0
    memory_threshold_percent: float = 90.0
    disk_threshold_percent: float = 90.0
    alert_cooldown_minutes: int = 15
    telegram_alerts_enabled: bool = False
    telegram_chat_id: str = ""
    telegram_bot_configured: bool = False
    controlbox_version: str = ""
    controlbox_profile: str = ""
    os_label: str = ""
    sidebar_hidden_items: list[str] = Field(default_factory=list)


class UpdatePanelSettingsRequest(BaseModel):
    panel_alias: str | None = None
    session_timeout_hours: int | None = Field(default=None, ge=1, le=168)
    panel_port: int | None = Field(default=None, ge=1024, le=65535)
    panel_base_path: str | None = Field(default=None, min_length=0, max_length=128)
    default_site_folder: str | None = None
    default_backup_folder: str | None = None
    server_ip: str | None = None
    ipv6_enabled: bool | None = None
    offline_mode: bool | None = None
    cdn_proxy: bool | None = None
    site_monitor_enabled: bool | None = None
    auto_fetch_favicon: bool | None = None
    auto_backup_panel: bool | None = None
    auto_backup_retention: int | None = Field(default=None, ge=1, le=365)
    cpu_threshold_percent: float | None = Field(default=None, ge=50, le=100)
    memory_threshold_percent: float | None = Field(default=None, ge=50, le=100)
    disk_threshold_percent: float | None = Field(default=None, ge=50, le=100)
    alert_cooldown_minutes: int | None = Field(default=None, ge=5, le=1440)
    telegram_alerts_enabled: bool | None = None
    telegram_bot_token: str | None = Field(default=None, min_length=10, max_length=128)
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    sidebar_hidden_items: list[str] | None = None


class TestTelegramRequest(BaseModel):
    telegram_bot_token: str | None = Field(default=None, min_length=10, max_length=128)
    telegram_chat_id: str | None = Field(default=None, max_length=64)


class TestTelegramResponse(BaseModel):
    success: bool
    message: str


class PanelActionResponse(BaseModel):
    success: bool
    message: str
    server_time: ServerTimeSchema | None = None
