import { request } from "@/lib/api-client";

export interface BackupDestination {
  id: string;
  tenant_id: string;
  name: string;
  destination_type: "local" | "minio" | "s3" | "r2";
  bucket: string;
  endpoint: string;
  region: string;
  prefix: string;
  local_path: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BackupSchedule {
  id: string;
  tenant_id: string;
  name: string;
  source_type: "websites" | "databases" | "dns" | "configurations";
  resource_id: string | null;
  destination_id: string;
  cron_expression: string;
  max_versions: number;
  retention_days: number;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackupJob {
  id: string;
  tenant_id: string;
  schedule_id: string | null;
  destination_id: string;
  name: string;
  source_type: string;
  resource_id: string | null;
  resource_name: string;
  resource_key: string;
  trigger_type: string;
  status: string;
  version_number: number;
  storage_path: string;
  size_bytes: number;
  checksum: string;
  metadata: Record<string, unknown>;
  retention_days: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackupStats {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_size_bytes: number;
  active_schedules: number;
  next_scheduled_at: string | null;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const backupsApi = {
  stats: () => authRequest<BackupStats>("/api/v1/backups/stats"),

  listDestinations: () => authRequest<BackupDestination[]>("/api/v1/backups/destinations"),
  createDestination: (payload: {
    name: string;
    destination_type: string;
    bucket?: string;
    endpoint?: string;
    region?: string;
    prefix?: string;
    local_path?: string;
    access_key?: string;
    secret_key?: string;
    is_default?: boolean;
  }) =>
    authRequest<BackupDestination>("/api/v1/backups/destinations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  testDestination: (id: string) =>
    authRequest<{ success: boolean }>(`/api/v1/backups/destinations/${id}/test`, { method: "POST" }),
  deleteDestination: (id: string) =>
    authRequest<void>(`/api/v1/backups/destinations/${id}`, { method: "DELETE" }),

  listSchedules: () => authRequest<BackupSchedule[]>("/api/v1/backups/schedules"),
  createSchedule: (payload: {
    name: string;
    source_type: string;
    resource_id?: string;
    destination_id: string;
    cron_expression?: string;
    max_versions?: number;
    retention_days?: number;
  }) =>
    authRequest<BackupSchedule>("/api/v1/backups/schedules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  pauseSchedule: (id: string) =>
    authRequest<BackupSchedule>(`/api/v1/backups/schedules/${id}/pause`, { method: "PUT" }),
  resumeSchedule: (id: string) =>
    authRequest<BackupSchedule>(`/api/v1/backups/schedules/${id}/resume`, { method: "PUT" }),
  runSchedule: (id: string) =>
    authRequest<BackupJob>(`/api/v1/backups/schedules/${id}/run`, { method: "POST" }),
  deleteSchedule: (id: string) =>
    authRequest<void>(`/api/v1/backups/schedules/${id}`, { method: "DELETE" }),

  listJobs: (sourceType?: string) =>
    authRequest<BackupJob[]>(
      `/api/v1/backups/jobs${sourceType ? `?source_type=${sourceType}` : ""}`
    ),
  createJob: (payload: {
    name?: string;
    source_type: string;
    resource_id?: string;
    destination_id: string;
    max_versions?: number;
    retention_days?: number;
  }) =>
    authRequest<BackupJob>("/api/v1/backups/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  restoreJob: (id: string) =>
    authRequest<BackupJob>(`/api/v1/backups/jobs/${id}/restore`, { method: "POST" }),
  deleteJob: (id: string) =>
    authRequest<void>(`/api/v1/backups/jobs/${id}`, { method: "DELETE" }),
  listVersions: (id: string) =>
    authRequest<BackupJob[]>(`/api/v1/backups/jobs/${id}/versions`),
  download: (id: string) =>
    authRequest<{ download_url: string | null; storage_path: string }>(
      `/api/v1/backups/jobs/${id}/download`
    ),
  browseLocal: (path?: string) =>
    authRequest<LocalDirectoryBrowseResult>(
      `/api/v1/backups/browse-local${path ? `?path=${encodeURIComponent(path)}` : ""}`
    ),
};

export interface LocalDirectoryBrowseResult {
  current_path: string;
  parent_path: string;
  directories: string[];
}

