import { ApiError, request } from "@/lib/api-client";
import type { SiteMonitoringFields } from "@/lib/site-monitoring";

export interface WordPressSite extends SiteMonitoringFields {
  id: string;
  tenant_id: string;
  name: string;
  domain: string;
  status: string;
  php_version: string;
  wordpress_version: string;
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
  created_at: string;
  updated_at: string;
}

export interface WordPressBackup {
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

export interface WordPressOptions {
  php_versions: string[];
  wordpress_version: string;
}

export interface CreateWordPressPayload {
  name: string;
  domain: string;
  admin_user: string;
  admin_password: string;
  admin_email: string;
  php_version?: string;
  ssl_enabled?: boolean;
  db_name?: string;
  db_user?: string;
  db_password?: string;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export interface WordPressDeployCredentials {
  site_url: string;
  login_url: string;
  admin_user: string;
  db_name: string;
  db_user: string;
  db_password: string;
  db_host?: string;
}

export interface WordPressProvisionStep {
  step: string;
  message: string;
  at: string;
}

export interface WordPressProvisionStatus {
  site_id: string;
  status: string;
  error_message: string | null;
  steps: WordPressProvisionStep[];
  credentials: WordPressDeployCredentials | null;
}

export const wordpressApi = {
  options: () => authRequest<WordPressOptions>("/api/v1/wordpress/options"),
  list: () => authRequest<WordPressSite[]>("/api/v1/wordpress"),
  get: (id: string) => authRequest<WordPressSite>(`/api/v1/wordpress/${id}`),
  provisionStatus: (id: string) =>
    authRequest<WordPressProvisionStatus>(`/api/v1/wordpress/${id}/provision-status`),
  create: (data: CreateWordPressPayload) =>
    authRequest<WordPressSite>("/api/v1/wordpress", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    authRequest<void>(`/api/v1/wordpress/${id}`, { method: "DELETE" }),
  restart: (id: string) =>
    authRequest<WordPressSite>(`/api/v1/wordpress/${id}/restart`, { method: "POST" }),
  changePhp: (id: string, php_version: string) =>
    authRequest<WordPressSite>(`/api/v1/wordpress/${id}/php-version`, {
      method: "POST",
      body: JSON.stringify({ php_version }),
    }),
  maintenance: (id: string, enabled: boolean) =>
    authRequest<WordPressSite>(`/api/v1/wordpress/${id}/maintenance`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  clone: (id: string, new_domain: string, new_name: string) =>
    authRequest<WordPressSite>(`/api/v1/wordpress/${id}/clone`, {
      method: "POST",
      body: JSON.stringify({ new_domain, new_name }),
    }),
  staging: (id: string) =>
    authRequest<WordPressSite>(`/api/v1/wordpress/${id}/staging`, { method: "POST" }),
  listBackups: (id: string) =>
    authRequest<WordPressBackup[]>(`/api/v1/wordpress/${id}/backups`),
  createBackup: (id: string, name?: string) =>
    authRequest<{ backup_id: string; status: string }>(`/api/v1/wordpress/${id}/backups`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  restoreBackup: (siteId: string, backupId: string) =>
    authRequest<{ status: string }>(`/api/v1/wordpress/${siteId}/backups/${backupId}/restore`, {
      method: "POST",
    }),
};

export { ApiError };
