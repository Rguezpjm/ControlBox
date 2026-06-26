import { request } from "@/lib/api-client";

export interface TenantMailService {
  id: string;
  tenant_id: string;
  name: string;
  mail_domain: string;
  status: "pending" | "configuring" | "active" | "error";
  imap_host: string;
  imap_port: number;
  imap_use_ssl: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_use_ssl: boolean;
  smtp_use_tls: boolean;
  admin_username: string;
  has_admin_password: boolean;
  default_quota_mb: number;
  total_quota_mb: number;
  webmail_url: string | null;
  connection_verified_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface MailAccount {
  id: string;
  tenant_id: string;
  mail_service_id: string;
  local_part: string;
  email_address: string;
  display_name: string;
  status: string;
  quota_mb: number;
  used_mb: number;
  forwarding_to: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface MailOverview {
  configured: boolean;
  accounts_count: number;
  total_quota_mb: number;
  total_used_mb: number;
}

export interface DnsRecordHint {
  type: string;
  name: string;
  value: string;
  purpose: string;
}

export interface CreateTenantMailPayload {
  name: string;
  mail_domain: string;
}

export interface UpdateTenantMailPayload {
  name?: string;
  imap_host?: string;
  imap_port?: number;
  imap_use_ssl?: boolean;
  smtp_host?: string;
  smtp_port?: number;
  smtp_use_ssl?: boolean;
  smtp_use_tls?: boolean;
  admin_username?: string;
  admin_password?: string;
  default_quota_mb?: number;
  total_quota_mb?: number;
  webmail_url?: string;
}

export interface CreateMailAccountPayload {
  local_part: string;
  display_name?: string;
  password?: string;
  quota_mb?: number;
}

export const mailApi = {
  overview: () => request<MailOverview>("/api/v1/mail/overview"),
  getService: () => request<TenantMailService | null>("/api/v1/mail/service"),
  createService: (data: CreateTenantMailPayload) =>
    request<TenantMailService>("/api/v1/mail/service", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateService: (data: UpdateTenantMailPayload) =>
    request<TenantMailService>("/api/v1/mail/service", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  verifyService: (admin_password?: string, force?: boolean) =>
    request<TenantMailService>("/api/v1/mail/service/verify", {
      method: "POST",
      body: JSON.stringify({ admin_password: admin_password || undefined, force: force || false }),
    }),
  deleteService: () => request<void>("/api/v1/mail/service", { method: "DELETE" }),
  dnsHints: () => request<DnsRecordHint[]>("/api/v1/mail/service/dns-hints"),
  listAccounts: () => request<MailAccount[]>("/api/v1/mail/accounts"),
  createAccount: (data: CreateMailAccountPayload) =>
    request<MailAccount & { password: string }>("/api/v1/mail/accounts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateAccount: (id: string, data: { display_name?: string; quota_mb?: number; status?: string }) =>
    request<MailAccount>(`/api/v1/mail/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteAccount: (id: string) =>
    request<void>(`/api/v1/mail/accounts/${id}`, { method: "DELETE" }),

  // Multi-domain / Multi-service API endpoints
  listServices: () => request<TenantMailService[]>("/api/v1/mail/services"),
  getServiceById: (serviceId: string) => request<TenantMailService | null>(`/api/v1/mail/services/${serviceId}`),
  createServiceById: (data: CreateTenantMailPayload) =>
    request<TenantMailService>("/api/v1/mail/services", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateServiceById: (serviceId: string, data: UpdateTenantMailPayload) =>
    request<TenantMailService>(`/api/v1/mail/services/${serviceId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  verifyServiceById: (serviceId: string, admin_password?: string, force?: boolean) =>
    request<TenantMailService>(`/api/v1/mail/services/${serviceId}/verify`, {
      method: "POST",
      body: JSON.stringify({ admin_password: admin_password || undefined, force: force || false }),
    }),
  deleteServiceById: (serviceId: string) => request<void>(`/api/v1/mail/services/${serviceId}`, { method: "DELETE" }),
  dnsHintsById: (serviceId: string) => request<DnsRecordHint[]>(`/api/v1/mail/services/${serviceId}/dns-hints`),
  overviewById: (serviceId: string) => request<MailOverview>(`/api/v1/mail/services/${serviceId}/overview`),
  listAccountsById: (serviceId: string) => request<MailAccount[]>(`/api/v1/mail/services/${serviceId}/accounts`),
  createAccountById: (serviceId: string, data: CreateMailAccountPayload) =>
    request<MailAccount & { password: string }>(`/api/v1/mail/services/${serviceId}/accounts`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateAccountById: (serviceId: string, id: string, data: { display_name?: string; quota_mb?: number; status?: string }) =>
    request<MailAccount>(`/api/v1/mail/services/${serviceId}/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteAccountById: (serviceId: string, id: string) =>
    request<void>(`/api/v1/mail/services/${serviceId}/accounts/${id}`, { method: "DELETE" }),
};
