import { request } from "@/lib/api-client";

export interface PanelConfig {
  panel_port: number;
  panel_base_path: string;
  panel_url_hint: string;
  can_apply_changes: boolean;
}

export interface AlertThresholds {
  cpu_threshold_percent: number;
  memory_threshold_percent: number;
  disk_threshold_percent: number;
  alerts_enabled: boolean;
  alert_cooldown_minutes: number;
}

export interface SecretRotationItem {
  key: string;
  label: string;
  rotated: boolean;
  required: boolean;
}

export interface SetupChecklistItem {
  key: string;
  label: string;
  completed: boolean;
}

export interface ResourceAlert {
  id: string;
  metric: string;
  severity: string;
  message: string;
  current_value: number;
  threshold_value: number;
  is_acknowledged: boolean;
  created_at: string | null;
}

export interface PlatformOverview {
  panel: PanelConfig;
  alert_thresholds: AlertThresholds;
  secrets_rotation: {
    items: SecretRotationItem[];
    all_rotated: boolean;
    production_ready: boolean;
  };
  setup_checklist: {
    items: SetupChecklistItem[];
    completed_count: number;
    total_count: number;
    production_ready: boolean;
  };
  active_alerts_count: number;
  is_production_ready: boolean;
}

export interface SystemInfo {
  version: string;
  os_label: string;
  profile: string;
  edition: string;
}

export function getSystemInfo() {
  return request<SystemInfo>("/api/v1/platform/sysinfo");
}

export function getPlatformOverview() {
  return request<PlatformOverview>("/api/v1/platform/overview");
}

export function updatePanelConfig(data: { panel_port?: number; panel_base_path?: string }) {
  return request<{ applied: boolean; message: string; requires_panel_rebuild?: boolean }>(
    "/api/v1/platform/panel",
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export function updateAlertThresholds(data: AlertThresholds) {
  return request<AlertThresholds>("/api/v1/platform/alert-thresholds", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function listResourceAlerts(activeOnly = true) {
  return request<ResourceAlert[]>(`/api/v1/platform/alerts?active_only=${activeOnly}`);
}

export function acknowledgeAlert(alertId: string) {
  return request<ResourceAlert>(`/api/v1/platform/alerts/${alertId}/acknowledge`, {
    method: "POST",
  });
}

export function acknowledgeSecretRotation(secretKey: string) {
  return request<PlatformOverview["secrets_rotation"]>("/api/v1/platform/secrets/acknowledge", {
    method: "POST",
    body: JSON.stringify({ secret_key: secretKey }),
  });
}

export function updateSetupChecklist(key: string, completed: boolean) {
  return request<PlatformOverview["setup_checklist"]>("/api/v1/platform/setup-checklist", {
    method: "PATCH",
    body: JSON.stringify({ key, completed }),
  });
}

export interface ServiceProfile {
  id: string;
  profile: string;
  name: string;
  category: string;
  description: string;
  enabled: boolean;
  running: boolean;
  requires: string[];
}

export interface ServicesOverview {
  can_manage: boolean;
  enabled_profiles: string[];
  services: ServiceProfile[];
  message: string;
}

export function getServiceProfiles() {
  return request<ServicesOverview>("/api/v1/platform/services");
}

export function applyServiceProfiles(profiles: string[]) {
  return request<{ success: boolean; message: string; enabled_profiles: string[] }>(
    "/api/v1/platform/services/apply",
    { method: "POST", body: JSON.stringify({ profiles }) }
  );
}

export function confirmSecretsReviewed() {
  return request<PlatformOverview["secrets_rotation"]>("/api/v1/platform/secrets/confirm-reviewed", {
    method: "POST",
  });
}

export interface ServerTime {
  iso: string;
  display: string;
  timezone: string;
}

export interface PanelSettings {
  panel_alias: string;
  session_timeout_hours: number;
  panel_port: number;
  panel_base_path: string;
  panel_url_hint: string;
  can_apply_host_changes: boolean;
  default_site_folder: string;
  default_backup_folder: string;
  server_ip: string;
  server_time: ServerTime;
  ipv6_enabled: boolean;
  offline_mode: boolean;
  cdn_proxy: boolean;
  site_monitor_enabled: boolean;
  auto_fetch_favicon: boolean;
  auto_backup_panel: boolean;
  auto_backup_retention: number;
  auto_backup_count: number;
  auto_backup_used_mb: number;
  cpu_threshold_percent: number;
  memory_threshold_percent: number;
  disk_threshold_percent: number;
  alert_cooldown_minutes: number;
  telegram_alerts_enabled: boolean;
  telegram_chat_id: string;
  telegram_bot_configured: boolean;
  controlbox_version: string;
  controlbox_profile: string;
  os_label: string;
  sidebar_hidden_items: string[];
}

export type UpdatePanelSettingsPayload = Partial<
  Pick<
    PanelSettings,
    | "panel_alias"
    | "session_timeout_hours"
    | "panel_port"
    | "panel_base_path"
    | "default_site_folder"
    | "default_backup_folder"
    | "server_ip"
    | "ipv6_enabled"
    | "offline_mode"
    | "cdn_proxy"
    | "site_monitor_enabled"
    | "auto_fetch_favicon"
    | "auto_backup_panel"
    | "auto_backup_retention"
    | "cpu_threshold_percent"
    | "memory_threshold_percent"
    | "disk_threshold_percent"
    | "alert_cooldown_minutes"
    | "telegram_alerts_enabled"
    | "telegram_chat_id"
    | "sidebar_hidden_items"
  > & {
    telegram_bot_token?: string;
  }
>;

export function getPanelSettings() {
  return request<PanelSettings>("/api/v1/platform/panel-settings");
}

export function updatePanelSettings(data: UpdatePanelSettingsPayload) {
  return request<PanelSettings>("/api/v1/platform/panel-settings", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function syncPanelServerTime() {
  return request<{ success: boolean; message: string; server_time?: ServerTime }>(
    "/api/v1/platform/panel-settings/sync-time",
    { method: "POST" }
  );
}

export function shutdownPanelService() {
  return request<{ success: boolean; message: string }>(
    "/api/v1/platform/panel-settings/shutdown-panel",
    { method: "POST" }
  );
}

export function testTelegramAlerts(data: {
  telegram_bot_token?: string;
  telegram_chat_id?: string;
}) {
  return request<{ success: boolean; message: string }>(
    "/api/v1/platform/panel-settings/test-telegram",
    { method: "POST", body: JSON.stringify(data) }
  );
}

export interface OperationResult {
  success: boolean;
  message: string;
  detail?: string | null;
}

export interface UpdateCheck {
  current_version: string;
  latest_version: string | null;
  update_available: boolean;
  source: string;
  release_url?: string | null;
  tarball_url?: string | null;
}

export const platformOperations = {
  restartPanel: () =>
    request<OperationResult>("/api/v1/platform/operations/restart-panel", { method: "POST" }),
  fixStack: () => request<OperationResult>("/api/v1/platform/operations/fix", { method: "POST" }),
  checkUpdate: () => request<UpdateCheck>("/api/v1/platform/operations/update-check"),
  applyUpdate: () => request<OperationResult>("/api/v1/platform/operations/update", { method: "POST" }),
};
