"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useLiveMetrics } from "@/hooks/use-realtime";
import { useI18n } from "@/providers/i18n-provider";
import { formatUptime } from "@/lib/utils";

interface ResourceMeterProps {
  initialMetrics: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    uptime_seconds: number;
    memory_used_mb?: number;
    memory_total_mb?: number;
    disk_used_gb?: number;
    disk_total_gb?: number;
  };
  connected?: boolean;
}

export function ResourceMeters({ initialMetrics, connected: connectedProp }: ResourceMeterProps) {
  const { t } = useI18n();
  const { metrics, connected: wsConnected } = useLiveMetrics({
    cpu: initialMetrics.cpu_percent,
    memory: initialMetrics.memory_percent,
    disk: initialMetrics.disk_percent,
    uptime: initialMetrics.uptime_seconds,
  });
  const connected = connectedProp ?? wsConnected;

  const uptimeSeconds = metrics.uptime ?? initialMetrics.uptime_seconds;

  const items = [
    { label: "CPU", value: metrics.cpu ?? initialMetrics.cpu_percent, color: "bg-primary", detail: undefined },
    {
      label: t("dashboard.memory"),
      value: metrics.memory ?? initialMetrics.memory_percent,
      color: "bg-blue-500",
      detail:
        initialMetrics.memory_used_mb && initialMetrics.memory_total_mb
          ? `${(initialMetrics.memory_used_mb / 1024).toFixed(1)} / ${(initialMetrics.memory_total_mb / 1024).toFixed(1)} GB`
          : undefined,
    },
    {
      label: t("dashboard.disk"),
      value: metrics.disk ?? initialMetrics.disk_percent,
      color: "bg-amber-500",
      detail:
        initialMetrics.disk_used_gb !== undefined && initialMetrics.disk_total_gb !== undefined
          ? `${initialMetrics.disk_used_gb.toFixed(1)} / ${initialMetrics.disk_total_gb.toFixed(1)} GB`
          : undefined,
    },
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-sm font-medium">{t("dashboard.resourceUsage")}</CardTitle>
        {connected && (
          <span className="text-[10px] uppercase tracking-wider text-success font-medium">{t("dashboard.live")}</span>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {items.map((item) => (
          <div key={item.label} className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-medium tabular-nums">
                {item.value.toFixed(1)}%
                {item.detail ? (
                  <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">({item.detail})</span>
                ) : null}
              </span>
            </div>
            <Progress value={item.value} className="h-1.5" />
          </div>
        ))}
        <div className="pt-2 border-t text-xs text-muted-foreground">
          {t("dashboard.uptime")}:{" "}
          <span className="font-medium text-foreground">{formatUptime(uptimeSeconds)}</span>
        </div>
      </CardContent>
    </Card>
  );
}
