import { ApiError, request } from "@/lib/api-client";
import { API_BASE } from "@/lib/api-base";

export interface DnsZone {
  id: string;
  tenant_id: string;
  name: string;
  status: string;
  serial: number;
  soa_email: string;
  default_ttl: number;
  record_count: number;
  nameservers: string[];
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DnsRecord {
  id: string;
  name: string;
  record_type: string;
  content: string;
  ttl: number;
  priority?: number | null;
}

export interface DnsApiKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  scopes: string[];
  last_used_at: string | null;
  created_at: string;
}

export interface DnsApiKeyCreated extends DnsApiKey {
  api_key: string;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const dnsApi = {
  recordTypes: () => authRequest<{ types: string[] }>("/api/v1/dns/record-types"),
  listZones: () => authRequest<DnsZone[]>("/api/v1/dns/zones"),
  getZone: (id: string) => authRequest<DnsZone>(`/api/v1/dns/zones/${id}`),
  createZone: (name: string, soa_email?: string) =>
    authRequest<DnsZone>("/api/v1/dns/zones", {
      method: "POST",
      body: JSON.stringify({ name, soa_email }),
    }),
  updateZone: (id: string, data: { soa_email?: string; default_ttl?: number; nameservers?: string[] }) =>
    authRequest<DnsZone>(`/api/v1/dns/zones/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteZone: (id: string) =>
    authRequest<void>(`/api/v1/dns/zones/${id}`, { method: "DELETE" }),
  importZone: (id: string, content: string) =>
    authRequest<DnsZone>(`/api/v1/dns/zones/${id}/import`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  exportZone: async (id: string) => {
    const res = await fetch(`${API_BASE}/api/v1/dns/zones/${id}/export`, {
      credentials: "include",
    });
    if (!res.ok) throw new ApiError("Export failed", res.status);
    return res.text();
  },
  listRecords: (zoneId: string) =>
    authRequest<DnsRecord[]>(`/api/v1/dns/zones/${zoneId}/records`),
  createRecord: (zoneId: string, data: {
    name: string;
    record_type: string;
    content: string;
    ttl?: number;
    priority?: number;
  }) =>
    authRequest<DnsRecord>(`/api/v1/dns/zones/${zoneId}/records`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateRecord: (zoneId: string, name: string, type: string, data: {
    content: string;
    ttl?: number;
    priority?: number;
  }) =>
    authRequest<DnsRecord>(`/api/v1/dns/zones/${zoneId}/records/${encodeURIComponent(name)}/${type}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteRecord: (zoneId: string, name: string, type: string) =>
    authRequest<void>(
      `/api/v1/dns/zones/${zoneId}/records/${encodeURIComponent(name)}/${type}`,
      { method: "DELETE" }
    ),
  listApiKeys: () => authRequest<DnsApiKey[]>("/api/v1/dns/api-keys"),
  createApiKey: (name: string) =>
    authRequest<DnsApiKeyCreated>("/api/v1/dns/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  revokeApiKey: (id: string) =>
    authRequest<void>(`/api/v1/dns/api-keys/${id}`, { method: "DELETE" }),
};

export { ApiError };
