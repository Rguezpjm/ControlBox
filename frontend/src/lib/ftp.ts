import { request } from "@/lib/api-client";

export interface FtpAccount {
  id: string;
  tenant_id: string;
  username: string;
  system_username: string;
  home_directory: string;
  status: string;
  quota_mb: number;
  max_files: number;
  upload_bandwidth_kbps: number;
  download_bandwidth_kbps: number;
  last_login_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface FtpAccountCreated extends FtpAccount {
  password: string;
}

export interface FtpLogEntry {
  timestamp: string;
  username: string;
  action: string;
  path: string | null;
  bytes_transferred: number;
  ip_address: string | null;
  status: string;
}

export interface FtpServiceStatus {
  enabled: boolean;
  status: string;
  host: string;
  port: number | null;
}

export interface CreateFtpAccountPayload {
  username: string;
  password?: string;
  home_directory?: string;
  quota_mb?: number;
  max_files?: number;
  upload_bandwidth_kbps?: number;
  download_bandwidth_kbps?: number;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const ftpApi = {
  status: () => authRequest<FtpServiceStatus>("/api/v1/ftp/status"),
  list: () => authRequest<FtpAccount[]>("/api/v1/ftp/accounts"),
  get: (id: string) => authRequest<FtpAccount>(`/api/v1/ftp/accounts/${id}`),
  create: (payload: CreateFtpAccountPayload) =>
    authRequest<FtpAccountCreated>("/api/v1/ftp/accounts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: Partial<CreateFtpAccountPayload>) =>
    authRequest<FtpAccount>(`/api/v1/ftp/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    authRequest<void>(`/api/v1/ftp/accounts/${id}`, { method: "DELETE" }),
  changePassword: (id: string, password?: string) =>
    authRequest<{ account: FtpAccount; password: string }>(
      `/api/v1/ftp/accounts/${id}/password`,
      { method: "PUT", body: JSON.stringify({ password }) }
    ),
  setQuota: (id: string, quota_mb: number, max_files = 0) =>
    authRequest<FtpAccount>(`/api/v1/ftp/accounts/${id}/quota`, {
      method: "PUT",
      body: JSON.stringify({ quota_mb, max_files }),
    }),
  setDirectory: (id: string, home_directory: string) =>
    authRequest<FtpAccount>(`/api/v1/ftp/accounts/${id}/directory`, {
      method: "PUT",
      body: JSON.stringify({ home_directory }),
    }),
  setStatus: (id: string, status: "active" | "suspended") =>
    authRequest<{ account: FtpAccount; password: string | null }>(
      `/api/v1/ftp/accounts/${id}/status`,
      { method: "PUT", body: JSON.stringify({ status }) }
    ),
  logs: (limit = 100) =>
    authRequest<FtpLogEntry[]>(`/api/v1/ftp/logs?limit=${limit}`),
  accountLogs: (id: string, limit = 100) =>
    authRequest<FtpLogEntry[]>(`/api/v1/ftp/accounts/${id}/logs?limit=${limit}`),
};
