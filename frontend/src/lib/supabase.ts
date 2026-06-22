import { ApiError, request } from "@/lib/api-client";

export interface SupabaseProject {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  status: string;
  project_ref: string;
  database_name: string;
  database_user: string;
  api_url: string;
  studio_url: string;
  storage_used_mb: number;
  database_size_mb: number;
  requests_count: number;
  error_message: string | null;
  suspended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupabaseCredentials {
  database_name: string;
  database_user: string;
  database_password: string;
  anon_key: string;
  service_role_key: string;
  api_url: string;
  studio_url: string;
  connection_url: string;
}

export interface SupabaseUsage {
  database_size_mb: number;
  storage_used_mb: number;
  buckets_count: number;
  schemas_count: number;
  realtime_channels_count: number;
  rls_policies_count: number;
  requests_count: number;
}

export interface SupabaseSchema {
  id: string;
  project_id: string;
  name: string;
  is_default: boolean;
  created_at: string;
}

export interface SupabaseBucket {
  id: string;
  project_id: string;
  name: string;
  public: boolean;
  file_size_limit_mb: number;
  status: string;
  objects_count: number;
  size_mb: number;
  created_at: string;
}

export interface SupabaseRealtimeChannel {
  id: string;
  project_id: string;
  name: string;
  table_name: string;
  schema_name: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

export interface SupabaseRlsPolicy {
  id: string;
  project_id: string;
  name: string;
  table_name: string;
  schema_name: string;
  action: string;
  role_name: string;
  using_expression: string;
  check_expression: string | null;
  is_enabled: boolean;
  created_at: string;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export interface SupabaseServiceStatus {
  enabled: boolean;
  profile_enabled: boolean;
  status: string;
  host: string;
  port: number;
  message: string;
}

export const supabaseApi = {
  status: () => authRequest<SupabaseServiceStatus>("/api/v1/supabase/status"),
  listProjects: () => authRequest<SupabaseProject[]>("/api/v1/supabase/projects"),
  getProject: (id: string) => authRequest<SupabaseProject>(`/api/v1/supabase/projects/${id}`),
  createProject: (name: string) =>
    authRequest<SupabaseProject>("/api/v1/supabase/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  suspendProject: (id: string) =>
    authRequest<SupabaseProject>(`/api/v1/supabase/projects/${id}/suspend`, { method: "POST" }),
  resumeProject: (id: string) =>
    authRequest<SupabaseProject>(`/api/v1/supabase/projects/${id}/resume`, { method: "POST" }),
  deleteProject: (id: string) =>
    authRequest<void>(`/api/v1/supabase/projects/${id}`, { method: "DELETE" }),
  rotateKeys: (id: string) =>
    authRequest<SupabaseCredentials>(`/api/v1/supabase/projects/${id}/rotate-keys`, { method: "POST" }),
  getCredentials: (id: string) =>
    authRequest<SupabaseCredentials>(`/api/v1/supabase/projects/${id}/credentials`),
  getUsage: (id: string) =>
    authRequest<SupabaseUsage>(`/api/v1/supabase/projects/${id}/usage`),
  listSchemas: (id: string) =>
    authRequest<SupabaseSchema[]>(`/api/v1/supabase/projects/${id}/schemas`),
  createSchema: (id: string, name: string) =>
    authRequest<SupabaseSchema>(`/api/v1/supabase/projects/${id}/schemas`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  deleteSchema: (id: string, schemaId: string) =>
    authRequest<void>(`/api/v1/supabase/projects/${id}/schemas/${schemaId}`, { method: "DELETE" }),
  listBuckets: (id: string) =>
    authRequest<SupabaseBucket[]>(`/api/v1/supabase/projects/${id}/buckets`),
  createBucket: (id: string, name: string, publicBucket = false) =>
    authRequest<SupabaseBucket>(`/api/v1/supabase/projects/${id}/buckets`, {
      method: "POST",
      body: JSON.stringify({ name, public: publicBucket }),
    }),
  deleteBucket: (id: string, bucketId: string) =>
    authRequest<void>(`/api/v1/supabase/projects/${id}/buckets/${bucketId}`, { method: "DELETE" }),
  listRealtimeChannels: (id: string) =>
    authRequest<SupabaseRealtimeChannel[]>(`/api/v1/supabase/projects/${id}/realtime-channels`),
  createRealtimeChannel: (id: string, data: { name: string; table_name: string; schema_name?: string }) =>
    authRequest<SupabaseRealtimeChannel>(`/api/v1/supabase/projects/${id}/realtime-channels`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteRealtimeChannel: (id: string, channelId: string) =>
    authRequest<void>(`/api/v1/supabase/projects/${id}/realtime-channels/${channelId}`, { method: "DELETE" }),
  listRlsPolicies: (id: string) =>
    authRequest<SupabaseRlsPolicy[]>(`/api/v1/supabase/projects/${id}/rls-policies`),
  createRlsPolicy: (id: string, data: {
    name: string;
    table_name: string;
    schema_name?: string;
    using_expression?: string;
  }) =>
    authRequest<SupabaseRlsPolicy>(`/api/v1/supabase/projects/${id}/rls-policies`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteRlsPolicy: (id: string, policyId: string) =>
    authRequest<void>(`/api/v1/supabase/projects/${id}/rls-policies/${policyId}`, { method: "DELETE" }),
};

export { ApiError };
