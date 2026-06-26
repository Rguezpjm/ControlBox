import { ApiError, request } from "@/lib/api-client";
import type { SiteMonitoringFields } from "@/lib/site-monitoring";

export interface JoomlaSite extends SiteMonitoringFields {
  id: string;
  tenant_id: string;
  name: string;
  domain: string;
  status: string;
  php_version: string;
  joomla_version: string;
  url: string;
  admin_user: string;
  admin_email: string;
  ssl_enabled: boolean;
  ssl_status: string;
  maintenance_mode: boolean;
  disk_used_mb: number;
  db_size_mb: number;
  is_staging: boolean;
  parent_site_id: string | null;
  error_message: string | null;
  ssl_days_remaining?: number | null;
  task_id: string | null;
  access_info?: JoomlaSiteAccessInfo | null;
  created_at: string;
  updated_at: string;
}

export interface JoomlaSiteAccessInfo {
  site_url: string;
  login_url: string;
  admin_user: string;
  admin_email: string;
  db_name?: string | null;
  db_user?: string | null;
  db_host?: string | null;
  db_password?: string | null;
  ftp_username?: string | null;
  ftp_password?: string | null;
  ftp_home?: string | null;
}

export interface JoomlaBackup {
  id: string;
  site_id: string;
  name: string;
  status: string;
  size_mb: number;
  checksum: string | null;
  includes_database: boolean;
  includes_files: boolean;
  error_message: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JoomlaOptions {
  php_versions: string[];
  joomla_version: string;
}

export interface CreateJoomlaPayload {
  name: string;
  domain: string;
  admin_user: string;
  admin_password: string;
  admin_email: string;
  php_version?: string;
  ssl_enabled?: boolean;
  create_ftp_account?: boolean;
  db_name?: string;
  db_user?: string;
  db_password?: string;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export interface JoomlaDeployCredentials {
  site_url: string;
  login_url: string;
  admin_user: string;
  db_name: string;
  db_user: string;
  db_password: string;
  db_host?: string;
  ftp_username?: string | null;
  ftp_password?: string | null;
  ftp_home?: string | null;
}

export interface JoomlaProvisionStep {
  step: string;
  message: string;
  at: string;
}

export interface JoomlaProvisionStatus {
  site_id: string;
  status: string;
  error_message: string | null;
  steps: JoomlaProvisionStep[];
  credentials: JoomlaDeployCredentials | null;
}

export const joomlaApi = {
  options: () => authRequest<JoomlaOptions>("/api/v1/joomla/options"),
  list: () => authRequest<JoomlaSite[]>("/api/v1/joomla"),
  get: (id: string) => authRequest<JoomlaSite>(`/api/v1/joomla/${id}`),
  provisionStatus: (id: string) =>
    authRequest<JoomlaProvisionStatus>(`/api/v1/joomla/${id}/provision-status`),
  create: (data: CreateJoomlaPayload) =>
    authRequest<JoomlaSite>("/api/v1/joomla", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    authRequest<void>(`/api/v1/joomla/${id}`, { method: "DELETE" }),
  restart: (id: string) =>
    authRequest<JoomlaSite>(`/api/v1/joomla/${id}/restart`, { method: "POST" }),
  changePhp: (id: string, php_version: string) =>
    authRequest<JoomlaSite>(`/api/v1/joomla/${id}/php-version`, {
      method: "POST",
      body: JSON.stringify({ php_version }),
    }),
  changeAdminPassword: (id: string, new_password: string) =>
    authRequest<JoomlaSite>(`/api/v1/joomla/${id}/admin-password`, {
      method: "POST",
      body: JSON.stringify({ new_password }),
    }),
  maintenance: (id: string, enabled: boolean) =>
    authRequest<JoomlaSite>(`/api/v1/joomla/${id}/maintenance`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  clone: (id: string, new_domain: string, new_name: string) =>
    authRequest<JoomlaSite>(`/api/v1/joomla/${id}/clone`, {
      method: "POST",
      body: JSON.stringify({ new_domain, new_name }),
    }),
  staging: (id: string) =>
    authRequest<JoomlaSite>(`/api/v1/joomla/${id}/staging`, { method: "POST" }),
  listBackups: (id: string) =>
    authRequest<JoomlaBackup[]>(`/api/v1/joomla/${id}/backups`),
  createBackup: (id: string, name?: string) =>
    authRequest<{ backup_id: string; status: string }>(`/api/v1/joomla/${id}/backups`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  restoreBackup: (siteId: string, backupId: string) =>
    authRequest<{ status: string }>(`/api/v1/joomla/${siteId}/backups/${backupId}/restore`, {
      method: "POST",
    }),
  publish: (id: string) =>
    authRequest<{ success: boolean; message: string; url: string }>(`/api/v1/joomla/${id}/publish`, {
      method: "POST",
    }),
};

export { ApiError };
