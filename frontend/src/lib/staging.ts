import { request } from "@/lib/api-client";

export interface StagingSite {
  id: string;
  tenant_id: string;
  source_type: string;
  source_id: string;
  source_domain: string;
  name: string;
  domain: string;
  domain_mode: string;
  stack_type: string;
  runtime_version: string;
  status: string;
  ssl_enabled: boolean;
  ssl_status: string;
  container_name: string | null;
  nginx_container_name: string | null;
  php_container_name: string | null;
  site_path: string;
  traefik_router: string | null;
  public_access_blocked: boolean;
  last_sync_at: string | null;
  last_sync_type: string | null;
  last_sync_direction: string | null;
  cpu_usage_percent: number;
  memory_used_mb: number;
  disk_used_mb: number;
  security: {
    password_protection: { enabled: boolean; username: string };
    ip_restriction: { enabled: boolean; allowed_ips: string[] };
    temp_access: { enabled: boolean; expires_at: string | null };
  };
  error_message: string | null;
  task_id: string | null;
  created_at: string;
  updated_at: string;
  cms_version: string | null;
  migration_progress: number | null;
  migration_status: string | null;
}

export type SyncType = "files" | "database" | "full";

export interface CreateStagingPayload {
  source_type: "website" | "wordpress" | "joomla";
  source_id: string;
  domain_mode?: "subdomain" | "random";
  name?: string;
}

export interface UpdateStagingSecurityPayload {
  password_protection_enabled?: boolean;
  password_protection_username?: string;
  password_protection_password?: string;
  ip_restriction_enabled?: boolean;
  allowed_ips?: string[];
  temp_access_enabled?: boolean;
  temp_access_hours?: number;
}

import { ensureCsrfToken, getAuthHeaders } from "@/lib/auth";
import { API_BASE } from "@/lib/api-base";
import { ApiError } from "@/lib/api-client";

export const stagingApi = {
  list: (sourceType?: string, sourceId?: string) => {
    const params = new URLSearchParams();
    if (sourceType) params.set("source_type", sourceType);
    if (sourceId) params.set("source_id", sourceId);
    const qs = params.toString();
    return request<StagingSite[]>(`/api/v1/staging${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => request<StagingSite>(`/api/v1/staging/${id}`),
  create: (data: CreateStagingPayload) =>
    request<StagingSite>("/api/v1/staging", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  syncFromProduction: (id: string, sync_type: SyncType) =>
    request<StagingSite>(`/api/v1/staging/${id}/sync-from-production`, {
      method: "POST",
      body: JSON.stringify({ sync_type }),
    }),
  syncToProduction: (id: string, sync_type: SyncType) =>
    request<StagingSite>(`/api/v1/staging/${id}/sync-to-production`, {
      method: "POST",
      body: JSON.stringify({ sync_type }),
    }),
  delete: (id: string) =>
    request<void>(`/api/v1/staging/${id}`, { method: "DELETE" }),
  restart: (id: string) =>
    request<StagingSite>(`/api/v1/staging/${id}/restart`, { method: "POST" }),
  blockAccess: (id: string, blocked: boolean) =>
    request<StagingSite>(`/api/v1/staging/${id}/block-access`, {
      method: "POST",
      body: JSON.stringify({ blocked }),
    }),
  updateSecurity: (id: string, data: UpdateStagingSecurityPayload) =>
    request<StagingSite>(`/api/v1/staging/${id}/security`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  changeVersion: (id: string, cms_version: string, php_version: string) =>
    request<StagingSite>(`/api/v1/staging/${id}/change-version`, {
      method: "POST",
      body: JSON.stringify({ cms_version, php_version }),
    }),
  importBlogger: async (id: string, file: File) => {
    await ensureCsrfToken();
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/v1/staging/${id}/import-blogger`, {
      method: "POST",
      credentials: "include",
      headers: getAuthHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.error || "Blogger import failed", res.status);
    }
    return res.json() as Promise<StagingSite>;
  },
  migrateJoomlaToWp: (id: string) =>
    request<StagingSite>(`/api/v1/staging/${id}/migrate-joomla-to-wp`, {
      method: "POST",
    }),
};

