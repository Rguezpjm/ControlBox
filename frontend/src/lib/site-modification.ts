import { request } from "@/lib/api-client";

export type SiteType = "website" | "wordpress";

export interface SiteDomain {
  domain: string;
  port: number;
  primary?: boolean;
}

export interface SiteSettings {
  domains?: SiteDomain[];
  document_root?: string;
  index_files?: string[];
  url_rewrite?: string;
  limit_access_enabled?: boolean;
  limit_access_user?: string;
  redirects?: Array<{ from: string; to: string; code?: number }>;
  reverse_proxy_enabled?: boolean;
  reverse_proxy_target?: string;
  hotlink_protection?: boolean;
  maintenance_mode?: boolean;
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
  ssl_enabled: boolean;
  ssl_status: string;
  document_root: string;
  settings: SiteSettings;
  vhost_config: string;
  nginx_config?: string | null;
  access_log: string;
  error_log: string;
}

export interface UpdateSiteModificationPayload {
  settings?: SiteSettings;
  vhost_config?: string;
  nginx_config?: string;
  ssl_enabled?: boolean;
  runtime_version?: string;
  php_version?: string;
}

function basePath(siteType: SiteType, siteId: string) {
  return siteType === "wordpress"
    ? `/api/v1/wordpress/${siteId}`
    : `/api/v1/websites/${siteId}`;
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
};
