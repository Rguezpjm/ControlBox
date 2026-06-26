import { request } from "@/lib/api-client";

export type SiteType = "website" | "wordpress" | "joomla";

export interface SiteDomain {
  domain: string;
  port: number;
  primary?: boolean;
}

export interface SubdirectoryBinding {
  domain: string;
  directory: string;
}

export interface SiteSettings {
  domains?: SiteDomain[];
  document_root?: string;
  running_directory?: string;
  open_basedir_enabled?: boolean;
  logs_enabled?: boolean;
  subdirectory_bindings?: SubdirectoryBinding[];
  index_files?: string[];
  url_rewrite?: string;
  limit_access_enabled?: boolean;
  limit_access_user?: string;
  limit_access_password?: string;
  redirects?: Array<{ from: string; to: string; code?: number }>;
  reverse_proxy_enabled?: boolean;
  reverse_proxy_target?: string;
  hotlink_protection?: boolean;
  maintenance_mode?: boolean;
}

export interface SiteSslConfig {
  provider: "letsencrypt" | "custom" | "none";
  deployed: boolean;
  force_https: boolean;
  cert_type: string;
  cert_brand: string;
  cert_domains: string[];
  expires_at?: string | null;
  days_remaining?: number | null;
  certificate_pem: string;
}

export interface PhpExtensionOption {
  id: string;
  label: string;
  group: string;
}

export interface SiteModification {
  site_type: SiteType;
  site_id: string;
  name: string;
  primary_domain: string;
  status: string;
  created_at: string;
  runtime?: string | null;
  runtime_version?: string | null;
  php_version?: string | null;
  php_extensions?: string[];
  php_extensions_available?: PhpExtensionOption[];
  ssl_enabled: boolean;
  ssl_status: string;
  ssl_config?: SiteSslConfig | null;
  document_root: string;
  running_directory?: string;
  running_directory_options?: string[];
  open_basedir_enabled?: boolean;
  logs_enabled?: boolean;
  site_files_path?: string;
  site_path?: string;
  subdirectory_bindings?: SubdirectoryBinding[];
  settings: SiteSettings;
  vhost_config: string;
  nginx_config?: string | null;
  access_log: string;
  error_log: string;
}

export interface AccessLogEntry {
  raw: string;
  ip: string;
  timestamp: string;
  method: string;
  path: string;
  protocol: string;
  status: number;
  bytes: string;
  user_agent: string;
  ip_location?: string | null;
}

export interface SiteAccessLogs {
  source: string;
  entries: AccessLogEntry[];
}

export interface SiteErrorLog {
  source: string;
  content: string;
}

export interface UpdateSiteModificationPayload {
  settings?: SiteSettings;
  document_root?: string;
  logs_enabled?: boolean;
  vhost_config?: string;
  nginx_config?: string;
  ssl_enabled?: boolean;
  runtime_version?: string;
  php_version?: string;
  php_extensions?: string[];
  ssl_provider?: "letsencrypt" | "custom" | "none";
  ssl_certificate_pem?: string;
  ssl_private_key_pem?: string;
  ssl_force_https?: boolean;
}

function basePath(siteType: SiteType, siteId: string) {
  if (siteType === "wordpress") {
    return `/api/v1/wordpress/${siteId}`;
  }
  if (siteType === "joomla") {
    return `/api/v1/joomla/${siteId}`;
  }
  return `/api/v1/websites/${siteId}`;
}

export const siteModificationApi = {
  get: (siteType: SiteType, siteId: string) =>
    request<SiteModification>(`${basePath(siteType, siteId)}/modification`),

  update: (siteType: SiteType, siteId: string, payload: UpdateSiteModificationPayload) =>
    request<SiteModification>(`${basePath(siteType, siteId)}/modification`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  addDomain: (siteType: SiteType, siteId: string, domain: string, port = 443) =>
    request<SiteModification>(`${basePath(siteType, siteId)}/domains`, {
      method: "POST",
      body: JSON.stringify({ domain, port }),
    }),

  removeDomain: (siteType: SiteType, siteId: string, domain: string) =>
    request<SiteModification>(
      `${basePath(siteType, siteId)}/domains/${encodeURIComponent(domain)}`,
      { method: "DELETE" }
    ),

  accessLogs: (siteType: SiteType, siteId: string, limit = 100) =>
    request<SiteAccessLogs>(
      `${basePath(siteType, siteId)}/access-logs?limit=${limit}`
    ),

  errorLog: (siteType: SiteType, siteId: string, limit = 100) =>
    request<SiteErrorLog>(
      `${basePath(siteType, siteId)}/error-log?limit=${limit}`
    ),
};
