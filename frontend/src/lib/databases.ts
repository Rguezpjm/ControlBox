import { ApiError, request } from "@/lib/api-client";

export interface ManagedDatabase {
  id: string;
  tenant_id: string;
  name: string;
  engine: string;
  status: string;
  host: string;
  port: number;
  database_name: string;
  charset: string;
  max_connections: number;
  size_mb: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatabaseUser {
  id: string;
  database_id: string;
  username: string;
  host: string;
  max_connections: number;
  is_active: boolean;
  grants: string[];
  created_at: string;
  updated_at: string;
}

export interface DatabaseUserCreated extends DatabaseUser {
  password: string;
}

export interface DatabaseBackup {
  id: string;
  database_id: string;
  name: string;
  backup_type: string;
  status: string;
  size_mb: number;
  retention_days: number;
  error_message: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineOption {
  engine: string;
  label: string;
  default_port: number;
  supports_connection_limit: boolean;
}

export interface DatabaseOptions {
  engines: EngineOption[];
}

export interface CreateDatabasePayload {
  name: string;
  engine: string;
  charset?: string;
  max_connections?: number;
}

export interface CreateUserPayload {
  username: string;
  password?: string;
  host?: string;
  max_connections?: number;
  grants?: string[];
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const databasesApi = {
  list: (engine?: string) =>
    authRequest<ManagedDatabase[]>(`/api/v1/databases${engine ? `?engine=${engine}` : ""}`),
  get: (id: string) => authRequest<ManagedDatabase>(`/api/v1/databases/${id}`),
  options: () => authRequest<DatabaseOptions>("/api/v1/databases/options"),
  create: (data: CreateDatabasePayload) =>
    authRequest<ManagedDatabase>("/api/v1/databases", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    authRequest<void>(`/api/v1/databases/${id}`, { method: "DELETE" }),
  setConnectionLimit: (id: string, max_connections: number) =>
    authRequest<ManagedDatabase>(`/api/v1/databases/${id}/connection-limit`, {
      method: "PUT",
      body: JSON.stringify({ max_connections }),
    }),
  listUsers: (id: string) =>
    authRequest<DatabaseUser[]>(`/api/v1/databases/${id}/users`),
  createUser: (id: string, data: CreateUserPayload) =>
    authRequest<DatabaseUserCreated>(`/api/v1/databases/${id}/users`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  changePassword: (id: string, userId: string, password?: string) =>
    authRequest<DatabaseUserCreated>(`/api/v1/databases/${id}/users/${userId}/password`, {
      method: "PUT",
      body: JSON.stringify({ password }),
    }),
  setUserConnectionLimit: (id: string, userId: string, max_connections: number) =>
    authRequest<DatabaseUser>(`/api/v1/databases/${id}/users/${userId}/connection-limit`, {
      method: "PUT",
      body: JSON.stringify({ max_connections }),
    }),
  deleteUser: (id: string, userId: string) =>
    authRequest<void>(`/api/v1/databases/${id}/users/${userId}`, { method: "DELETE" }),
  listBackups: (id: string) =>
    authRequest<DatabaseBackup[]>(`/api/v1/databases/${id}/backups`),
  createBackup: (id: string, name?: string, retention_days?: number) =>
    authRequest<DatabaseBackup>(`/api/v1/databases/${id}/backups`, {
      method: "POST",
      body: JSON.stringify({ name, retention_days }),
    }),
  restoreBackup: (id: string, backupId: string) =>
    authRequest<DatabaseBackup>(`/api/v1/databases/${id}/backups/${backupId}/restore`, {
      method: "POST",
    }),
  deleteBackup: (id: string, backupId: string) =>
    authRequest<void>(`/api/v1/databases/${id}/backups/${backupId}`, { method: "DELETE" }),
};

export { ApiError };
