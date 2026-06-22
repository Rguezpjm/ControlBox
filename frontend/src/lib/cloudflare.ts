import { request } from "@/lib/api-client";

export interface CloudflareSettings {
  enabled: boolean;
  configured: boolean;
  account_id: string;
  tunnel_enabled: boolean;
  tunnel_id: string;
  tunnel_hostname: string;
  tunnel_running: boolean;
}

export interface CloudflareZone {
  id: string;
  name: string;
  status: string;
  paused: boolean;
  security_level: string;
  name_servers: string[];
}

export interface CloudflareDnsRecord {
  id: string;
  type: string;
  name: string;
  content: string;
  ttl: number;
  proxied: boolean;
  priority?: number | null;
}

export interface CloudflareActionResult {
  success: boolean;
  message: string;
  account_id?: string | null;
}

export const cloudflareApi = {
  getSettings: () => request<CloudflareSettings>("/api/v1/cloudflare/settings"),

  updateSettings: (data: {
    enabled?: boolean;
    api_token?: string;
    account_id?: string;
    tunnel_enabled?: boolean;
    tunnel_hostname?: string;
  }) =>
    request<CloudflareSettings>("/api/v1/cloudflare/settings", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  testConnection: (data?: { api_token?: string; account_id?: string }) =>
    request<CloudflareActionResult>("/api/v1/cloudflare/settings/test", {
      method: "POST",
      body: JSON.stringify(data ?? {}),
    }),

  startTunnel: () =>
    request<CloudflareActionResult>("/api/v1/cloudflare/tunnel/start", { method: "POST" }),

  stopTunnel: () =>
    request<CloudflareActionResult>("/api/v1/cloudflare/tunnel/stop", { method: "POST" }),

  listZones: () => request<CloudflareZone[]>("/api/v1/cloudflare/zones"),

  createZone: (name: string) =>
    request<CloudflareZone>("/api/v1/cloudflare/zones", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  updateZone: (zoneId: string, data: { paused?: boolean; under_attack?: boolean }) =>
    request<CloudflareZone>(`/api/v1/cloudflare/zones/${zoneId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteZone: (zoneId: string) =>
    request<void>(`/api/v1/cloudflare/zones/${zoneId}`, { method: "DELETE" }),

  listDnsRecords: (zoneId: string) =>
    request<CloudflareDnsRecord[]>(`/api/v1/cloudflare/zones/${zoneId}/dns-records`),

  createDnsRecord: (
    zoneId: string,
    data: {
      type: string;
      name: string;
      content: string;
      ttl?: number;
      proxied?: boolean;
      priority?: number;
    }
  ) =>
    request<CloudflareDnsRecord>(`/api/v1/cloudflare/zones/${zoneId}/dns-records`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateDnsRecord: (
    zoneId: string,
    recordId: string,
    data: {
      type: string;
      name: string;
      content: string;
      ttl?: number;
      proxied?: boolean;
      priority?: number;
    }
  ) =>
    request<CloudflareDnsRecord>(`/api/v1/cloudflare/zones/${zoneId}/dns-records/${recordId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteDnsRecord: (zoneId: string, recordId: string) =>
    request<void>(`/api/v1/cloudflare/zones/${zoneId}/dns-records/${recordId}`, {
      method: "DELETE",
    }),
};
