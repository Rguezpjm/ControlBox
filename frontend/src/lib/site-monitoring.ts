export interface UptimeTimelinePoint {
  timestamp: string;
  status: string;
  reason?: string | null;
  latency_ms?: number | null;
  http_status?: number | null;
}

export interface SiteMonitoringFields {
  visit_count?: number;
  visits_sparkline?: number[];
  uptime_timeline?: UptimeTimelinePoint[];
  uptime_percent?: number;
  last_down_reason?: string | null;
  last_down_reason_label?: string | null;
  is_up?: boolean;
  traffic_mbps?: number;
  traffic_sparkline?: number[];
}
