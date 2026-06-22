"use client";

import { Suspense } from "react";
import { Globe, Database, HardDrive, Network } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { MetricsChart } from "@/components/dashboard/metrics-chart";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { ResourceMeters } from "@/components/dashboard/resource-meters";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/skeletons";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useI18n } from "@/providers/i18n-provider";
import { formatBytes } from "@/lib/utils";

function DashboardContent() {
  const { t } = useI18n();
  const { data, error, loading } = useDashboardData();

  if (loading && !data) return <PageSkeleton />;
  if (error || !data) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
        {t("dashboard.loadError")}
      </div>
    );
  }

  const { overview, history } = data;
  const { host, websites, databases, services } = overview;

  const runningSites = websites.filter((w) => w.status === "running" || w.status === "active").length;
  const pendingSites = websites.length - runningSites;
  const healthyDbs = databases.filter((d) => d.status === "running" || d.status === "healthy").length;
  const servicesUp = services.filter((s) => s.status === "healthy" || s.status === "up").length;

  const storageUsed = `${host.disk_used_gb.toFixed(1)} GB`;
  const storageTotal = `${host.disk_total_gb.toFixed(1)} GB`;

  const cpuHistory = history.cpu.map((p) => ({ timestamp: p.timestamp, value: p.value }));
  const netHistory = history.network_in.map((p, i) => ({
    timestamp: p.timestamp,
    value: p.value + (history.network_out[i]?.value ?? 0),
  }));

  return (
    <div className="space-y-6">
      <PageHeader title={t("dashboard.title")} description={t("dashboard.subtitle")} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title={t("dashboard.websites")}
          value={websites.length}
          description={`${runningSites} ${t("dashboard.running")}${pendingSites ? `, ${pendingSites} ${t("dashboard.pending")}` : ""}`}
          icon={Globe}
        />
        <StatCard
          title={t("dashboard.databases")}
          value={databases.length}
          description={
            databases.length === 0
              ? t("dashboard.noDatabases")
              : healthyDbs === databases.length
                ? t("dashboard.allHealthy")
                : t("dashboard.degraded")
          }
          icon={Database}
        />
        <StatCard
          title={t("dashboard.storage")}
          value={storageUsed}
          description={t("dashboard.ofUsed", { total: storageTotal })}
          icon={HardDrive}
        />
        <StatCard
          title={t("dashboard.network")}
          value={`${host.network_in_mbps.toFixed(1)} Mbps`}
          description={t("dashboard.inOutMbps", {
            in: host.network_in_mbps.toFixed(1),
            out: host.network_out_mbps.toFixed(1),
          })}
          icon={Network}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <MetricsChart title={t("dashboard.cpuUsage")} data={cpuHistory} unit="%" />
          <MetricsChart
            title={t("dashboard.networkTraffic")}
            data={netHistory}
            color="hsl(200 80% 50%)"
            unit=" Mbps"
          />
        </div>
        <div className="space-y-4">
          <ResourceMeters
            initialMetrics={{
              cpu_percent: host.cpu_percent,
              memory_percent: host.memory_percent,
              disk_percent: host.disk_percent,
              uptime_seconds: host.uptime_seconds,
            }}
          />
          <ActivityFeed />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">{t("dashboard.recentWebsites")}</CardTitle>
        </CardHeader>
        <CardContent>
          {websites.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("dashboard.noWebsites")}</p>
          ) : (
            <div className="space-y-3">
              {websites.slice(0, 8).map((site) => (
                <div
                  key={site.id}
                  className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                      <Globe className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{site.name}</p>
                      <p className="text-xs text-muted-foreground">{site.domain}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="hidden text-xs tabular-nums text-muted-foreground sm:block">
                      {formatBytes(site.disk_used_mb * 1024 * 1024)} /{" "}
                      {formatBytes(site.disk_limit_mb * 1024 * 1024)}
                    </span>
                    <StatusBadge status={site.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
          {services.length > 0 && (
            <p className="mt-4 text-xs text-muted-foreground">
              {t("dashboard.servicesUp", { up: servicesUp, total: services.length })}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <DashboardContent />
    </Suspense>
  );
}
