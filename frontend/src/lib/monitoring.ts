import { request } from "@/lib/api-client";

export interface MetricPoint {
  timestamp: string;
  value: number;
}

export interface HostMetrics {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  network_in_mbps: number;
  network_out_mbps: number;
  uptime_seconds: number;
}

export interface DockerContainerMetrics {
  name: string;
  container_id: string;
  status: string;
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_limit_mb: number;
  network_in_mb: number;
  network_out_mb: number;
}

export interface DatabaseMetrics {
  id: string;
  name: string;
  engine: string;
  status: string;
  size_mb: number;
  connections: number;
  cpu_percent: number;
}

export interface SupabaseMetrics {
  id: string;
  name: string;
  status: string;
  database_size_mb: number;
  storage_used_mb: number;
  requests_count: number;
}

export interface WebsiteMetrics {
  id: string;
  name: string;
  domain: string;
  status: string;
  cpu_percent: number;
  memory_percent: number;
  disk_used_mb: number;
  disk_limit_mb: number;
  site_type?: "website" | "wordpress";
  created_at?: string | null;
}

export interface ServiceHealth {
  name: string;
  status: string;
  latency_ms: number | null;
}

export interface MonitoringOverview {
  host: HostMetrics;
  docker: DockerContainerMetrics[];
  databases: DatabaseMetrics[];
  supabase: SupabaseMetrics[];
  websites: WebsiteMetrics[];
  services: ServiceHealth[];
  collected_at: string | null;
}

export interface MonitoringHistory {
  cpu: MetricPoint[];
  memory: MetricPoint[];
  disk: MetricPoint[];
  network_in: MetricPoint[];
  network_out: MetricPoint[];
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const monitoringApi = {
  overview: () => authRequest<MonitoringOverview>("/api/v1/monitoring/overview"),
  history: (limit = 60) =>
    authRequest<MonitoringHistory>(`/api/v1/monitoring/history?limit=${limit}`),
  docker: () => authRequest<DockerContainerMetrics[]>("/api/v1/monitoring/docker"),
  databases: () => authRequest<DatabaseMetrics[]>("/api/v1/monitoring/databases"),
  supabase: () => authRequest<SupabaseMetrics[]>("/api/v1/monitoring/supabase"),
  websites: () => authRequest<WebsiteMetrics[]>("/api/v1/monitoring/websites"),
  services: () => authRequest<ServiceHealth[]>("/api/v1/monitoring/services"),
};
