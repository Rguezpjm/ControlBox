"use client";

import { ExternalLink, Globe, MoreHorizontal } from "lucide-react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "@/components/shared/status-badge";
import { MiniSparkline } from "@/components/shared/mini-sparkline";
import { UptimeBar, formatDownReason, type UptimeTimelinePoint } from "@/components/shared/uptime-bar";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string, isUp?: boolean): ResourceStatus {
  if (status === "running" && isUp === false) return "degraded";
  const map: Record<string, ResourceStatus> = {
    running: "running",
    stopped: "stopped",
    pending: "pending",
    provisioning: "pending",
    maintenance: "pending",
    error: "error",
    deleting: "pending",
  };
  return map[status] || "pending";
}

export interface SiteMonitoringCardData {
  id: string;
  name: string;
  domain: string;
  status: string;
  badge?: string;
  error_message?: string | null;
  disk_used_mb?: number;
  disk_limit_mb?: number;
  monitoring_enabled?: boolean;
  logs_enabled?: boolean;
  visit_count?: number;
  visits_sparkline?: number[];
  uptime_timeline?: UptimeTimelinePoint[];
  uptime_percent?: number;
  last_down_reason?: string | null;
  last_down_reason_label?: string | null;
  is_up?: boolean;
}

interface SiteMonitoringCardProps {
  site: SiteMonitoringCardData;
  onClick?: () => void;
  actions?: React.ReactNode;
}

export function SiteMonitoringCard({ site, onClick, actions }: SiteMonitoringCardProps) {
  const diskPct =
    site.disk_limit_mb && site.disk_limit_mb > 0
      ? Math.min(Math.round(((site.disk_used_mb ?? 0) / site.disk_limit_mb) * 100), 100)
      : 0;

  const displayStatus = mapStatus(site.status, site.is_up);
  const downLabel = site.last_down_reason_label ?? formatDownReason(site.last_down_reason);

  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-md">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Globe className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <button
                type="button"
                onClick={onClick}
                className="truncate text-left font-semibold hover:text-primary hover:underline"
              >
                {site.name}
              </button>
              <a
                href={`https://${site.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-0.5 flex items-center gap-1 truncate text-sm text-muted-foreground hover:text-primary"
                onClick={(e) => e.stopPropagation()}
              >
                {site.domain}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            </div>
          </div>
          {actions ?? (
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" disabled>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={displayStatus} />
          {site.is_up === false && site.status === "running" && (
            <span className="inline-flex items-center rounded-full border border-destructive/30 bg-destructive/10 px-2.5 py-0.5 text-xs font-medium text-destructive">
              Portal caído
            </span>
          )}
          {site.badge && (
            <span className="inline-flex items-center rounded-full border bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              {site.badge}
            </span>
          )}
        </div>

        {site.error_message && (
          <p className="text-xs leading-relaxed text-destructive">{site.error_message}</p>
        )}

        {!site.is_up && downLabel && site.status === "running" && (
          <p className="text-xs text-destructive">
            Última caída: {downLabel}
          </p>
        )}

        <div className="flex items-center gap-3 rounded-lg border bg-muted/20 px-3 py-2.5">
          <MiniSparkline
            data={site.visits_sparkline ?? []}
            width={88}
            height={32}
            className="shrink-0 text-sky-500"
          />
          <div>
            <p className="text-xs text-muted-foreground">Visitas (24h)</p>
            <p className="text-lg font-semibold tabular-nums leading-tight">
              {(site.visit_count ?? 0).toLocaleString()}
            </p>
          </div>
        </div>

        <UptimeBar
          timeline={site.uptime_timeline ?? []}
          uptimePercent={site.uptime_percent}
        />

        {(site.disk_limit_mb ?? 0) > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Disk</span>
              <span className="tabular-nums text-muted-foreground">{diskPct}%</span>
            </div>
            <Progress value={diskPct} className="h-1.5" />
          </div>
        )}
      </CardContent>

      <CardFooter className="border-t bg-muted/20 px-5 py-2.5 text-xs text-muted-foreground">
        <span>{site.monitoring_enabled !== false ? "Monitoring on" : "Monitoring off"}</span>
        <span className="ml-auto">{site.logs_enabled !== false ? "Logs on" : "Logs off"}</span>
      </CardFooter>
    </Card>
  );
}
