import { request } from "@/lib/api-client";

export interface StreamingSource {
  id: string;
  name: string;
  type: string;
  url: string;
  username?: string | null;
  status: string;
  last_sync_at?: string | null;
  created_at: string;
}

export interface StreamingCategory {
  id: string;
  name: string;
}

export interface StreamingChannel {
  id: string;
  source_id: string;
  category_id?: string | null;
  name: string;
  stream_url: string;
  logo_url?: string | null;
  epg_id?: string | null;
  is_active: boolean;
  status: string;
}

export interface StreamingClient {
  id: string;
  username: string;
  password: string;
  max_connections: number;
  is_active: boolean;
  expires_at?: string | null;
  allowed_categories: string[];
  created_at: string;
}

export interface ImportChannelItem {
  name: string;
  stream_url: string;
  logo_url?: string | null;
  epg_id?: string | null;
  category_name: string;
  stream_id?: number | null;
}

export interface ActiveConnection {
  id: string;
  client_username: string;
  channel_name: string;
  ip_address: string;
  user_agent?: string | null;
  bytes_transferred: number;
  connected_at: string;
}

export interface StreamingStats {
  connected_users: number;
  bandwidth_mbps: number;
  active_streams: number;
  total_channels: number;
}

export const streamingApi = {
  listSources: () => request<StreamingSource[]>("/api/v1/streaming/sources"),
  createSource: (data: {
    name: string;
    type: string;
    url: string;
    username?: string;
    password?: string;
  }) =>
    request<StreamingSource>("/api/v1/streaming/sources", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteSource: (id: string) =>
    request<void>(`/api/v1/streaming/sources/${id}`, { method: "DELETE" }),
  getCatalog: (id: string) =>
    request<ImportChannelItem[]>(`/api/v1/streaming/sources/${id}/catalog`),
  importChannels: (sourceId: string, channels: ImportChannelItem[]) =>
    request<{ status: string; imported: number }>("/api/v1/streaming/import", {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId, channels }),
    }),
  listChannels: () => request<StreamingChannel[]>("/api/v1/streaming/channels"),
  listCategories: () => request<StreamingCategory[]>("/api/v1/streaming/categories"),
  listClients: () => request<StreamingClient[]>("/api/v1/streaming/clients"),
  createClient: (data: {
    username: string;
    password: string;
    max_connections: number;
    is_active: boolean;
    expires_at?: string | null;
    allowed_categories: string[];
  }) =>
    request<StreamingClient>("/api/v1/streaming/clients", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteClient: (id: string) =>
    request<void>(`/api/v1/streaming/clients/${id}`, { method: "DELETE" }),
  listActiveConnections: () =>
    request<ActiveConnection[]>("/api/v1/streaming/active-connections"),
  syncEpg: (url: string) =>
    request<{ status: string }>(
      `/api/v1/streaming/sync-epg-trigger?url=${encodeURIComponent(url)}`,
      { method: "POST" }
    ),
  getStats: () => request<StreamingStats>("/api/v1/streaming/stats"),
};
