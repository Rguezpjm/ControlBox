import { ApiError, request } from "@/lib/api-client";

export interface Website {
  id: string;
  tenant_id: string;
  name: string;
  domain: string;
  runtime: string;
  runtime_version: string;
  status: string;
  container_id: string | null;
  container_name: string | null;
  document_root: string;
  ssl_enabled: boolean;
  ssl_status: string;
  database_engine: string;
  database_config: Record<string, unknown>;
  monitoring_enabled: boolean;
  logs_enabled: boolean;
  logs_path: string | null;
  port: number;
  disk_used_mb: number;
  disk_limit_mb: number;
  error_message: string | null;
  ssl_days_remaining?: number | null;
  requests_count?: number;
  requests_sparkline?: number[];
  created_at: string;
  updated_at: string;
}

export interface RuntimeOption {
  runtime: string;
  label: string;
  versions: string[];
  default_version: string;
}

export interface DatabaseOption {
  engine: string;
  label: string;
}

export interface WebsiteOptions {
  runtimes: RuntimeOption[];
  databases: DatabaseOption[];
}

export interface CreateWebsitePayload {
  name: string;
  domain: string;
  runtime: string;
  runtime_version?: string | null;
  database_engine: string;
  ssl_enabled?: boolean;
  disk_limit_mb?: number;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const websitesApi = {
  list: () => authRequest<Website[]>("/api/v1/websites"),
  get: (id: string) => authRequest<Website>(`/api/v1/websites/${id}`),
  options: () => authRequest<WebsiteOptions>("/api/v1/websites/options"),
  create: (data: CreateWebsitePayload) =>
    authRequest<Website>("/api/v1/websites", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    authRequest<void>(`/api/v1/websites/${id}`, { method: "DELETE" }),
  start: (id: string) =>
    authRequest<Website>(`/api/v1/websites/${id}/start`, { method: "POST" }),
  stop: (id: string) =>
    authRequest<Website>(`/api/v1/websites/${id}/stop`, { method: "POST" }),
};

export { ApiError };
