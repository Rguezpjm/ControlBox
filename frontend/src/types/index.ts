export type ResourceStatus = "running" | "stopped" | "pending" | "error" | "degraded";

export type DatabaseEngine = "supabase" | "mysql" | "mssql" | "sqlite" | "postgresql";

export interface User {
  id: string;
  email: string;
  full_name: string;
  tenant_id: string | null;
  roles: string[];
  permissions: string[];
}

export interface Website {
  id: string;
  name: string;
  domain: string;
  status: ResourceStatus;
  ssl: boolean;
  php_version?: string;
  disk_used_mb: number;
  disk_limit_mb: number;
  visitors_24h: number;
  created_at: string;
}

export interface Domain {
  id: string;
  name: string;
  status: "active" | "pending" | "expired";
  auto_renew: boolean;
  expires_at: string;
  nameservers: string[];
}

export interface DnsRecord {
  id: string;
  zone: string;
  type: "A" | "AAAA" | "CNAME" | "MX" | "TXT" | "NS" | "SRV";
  name: string;
  value: string;
  ttl: number;
  priority?: number;
}

export interface EmailAccount {
  id: string;
  address: string;
  quota_mb: number;
  used_mb: number;
  status: ResourceStatus;
}

export interface Database {
  id: string;
  name: string;
  engine: DatabaseEngine;
  status: ResourceStatus;
  size_mb: number;
  connections: number;
  host: string;
  port: number;
  created_at: string;
}

export interface FtpAccount {
  id: string;
  username: string;
  directory: string;
  status: ResourceStatus;
  last_login?: string;
}

export interface Backup {
  id: string;
  name: string;
  type: "full" | "incremental" | "database" | "files";
  size_mb: number;
  status: "completed" | "running" | "failed";
  created_at: string;
  retention_days: number;
}

export interface MetricPoint {
  timestamp: string;
  value: number;
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  network_in_mbps: number;
  network_out_mbps: number;
  uptime_seconds: number;
  active_connections: number;
}

export interface SecurityEvent {
  id: string;
  type: "login" | "firewall" | "ssl" | "malware" | "brute_force";
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  ip_address?: string;
  created_at: string;
}

export interface RealtimeEvent {
  type: "metric" | "status" | "alert" | "backup" | "deployment";
  resource: string;
  resource_id: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: string | number;
  children?: NavItem[];
}

export interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}
