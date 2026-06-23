"use client";

import { Suspense } from "react";
import Link from "next/link";
import {
  Activity,
  Cpu,
  HardDrive,
  Network,
  Server,
  Database,
  Globe,
  Box,
  Cloud,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { MetricsChart } from "@/components/dashboard/metrics-chart";
import { ResourceBarChart, MultiLineChart } from "@/components/monitoring/resource-charts";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PageSkeleton } from "@/components/skeletons";
import { StatusBadge } from "@/components/shared/status-badge";
import { useMonitoring } from "@/hooks/use-monitoring";
import { formatUptime } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    running: "running",
    healthy: "running",
    completed: "running",
    stopped: "stopped",
    suspended: "stopped",
    pending: "pending",
    provisioning: "pending",
    error: "error",
    failed: "error",
    unhealthy: "error",
  };
  return map[status] || "pending";
}

function MonitoringContent() {
  const { overview, history, loading, connected } = useMonitoring();

  if (loading || !overview || !history) return <PageSkeleton />;

  const host = overview.host;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Monitoring"
        description="Real-time infrastructure metrics for CPU, memory, disk, network and services"
        action={
          connected ? (
            <span className="flex items-center gap-2 text-xs text-success font-medium">
              <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
              Live streaming
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">Polling API</span>
          )
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="CPU" value={`${host.cpu_percent.toFixed(1)}%`} icon={Cpu} />
        <StatCard title="Memory" value={`${host.memory_percent.toFixed(1)}%`} icon={Server} />
        <StatCard title="Disk" value={`${host.disk_percent.toFixed(1)}%`} icon={HardDrive} />
        <StatCard title="Uptime" value={formatUptime(host.uptime_seconds)} icon={Activity} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <MetricsChart title="CPU Usage" data={history.cpu} />
        <MetricsChart title="Memory Usage" data={history.memory} color="hsl(220 80% 55%)" />
        <MetricsChart title="Disk Usage" data={history.disk} color="hsl(35 90% 50%)" />
        <MultiLineChart
          title="Network Traffic"
          unit="Mbps"
          series={[
            { name: "In", data: history.network_in, color: "hsl(160 60% 45%)" },
            { name: "Out", data: history.network_out, color: "hsl(280 60% 55%)" },
          ]}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ResourceBarChart
          title="Docker Containers — CPU"
          data={overview.docker.map((c) => ({ name: c.name.slice(0, 16), value: c.cpu_percent }))}
          color="hsl(200 70% 50%)"
        />
        <ResourceBarChart
          title="Docker Containers — Memory"
          data={overview.docker.map((c) => ({ name: c.name.slice(0, 16), value: c.memory_percent }))}
          color="hsl(260 60% 55%)"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Database className="h-4 w-4" />
              Databases
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {overview.databases.length === 0 ? (
              <p className="text-sm text-muted-foreground">No managed databases.</p>
            ) : (
              overview.databases.map((db) => (
                <div key={db.id} className="rounded-lg border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{db.name}</span>
                    <StatusBadge status={mapStatus(db.status)} />
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                    <span>{db.engine}</span>
                    <span>{db.size_mb} MB</span>
                    <span>{db.connections} conn</span>
                  </div>
                  <Progress value={Math.min(db.connections * 2, 100)} className="h-1.5" />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Cloud className="h-4 w-4" />
              Supabase Projects
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {overview.supabase.length === 0 ? (
              <p className="text-sm text-muted-foreground">No Supabase projects.</p>
            ) : (
              overview.supabase.map((p) => (
                <div key={p.id} className="rounded-lg border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{p.name}</span>
                    <StatusBadge status={mapStatus(p.status)} />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                    <span>DB {p.database_size_mb} MB</span>
                    <span>Storage {p.storage_used_mb} MB</span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Websites & WordPress
          </CardTitle>
        </CardHeader>
        <CardContent>
          {overview.websites.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sites deployed.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Site</th>
                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">CPU</th>
                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Memory</th>
                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Disk</th>
                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.websites.map((site) => (
                    <tr key={`${site.site_type ?? "website"}-${site.id}`} className="border-b last:border-0">
                      <td className="px-3 py-2">
                        <Link
                          href={
                            site.site_type === "wordpress"
                              ? `/wordpress/${site.id}`
                              : `/websites/${site.id}`
                          }
                          className="hover:underline"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{site.name}</span>
                            {site.site_type === "wordpress" ? (
                              <Badge variant="secondary" className="text-[10px]">
                                WordPress
                              </Badge>
                            ) : null}
                          </div>
                          <div className="text-xs text-muted-foreground">{site.domain}</div>
                        </Link>
                      </td>
                      <td className="px-3 py-2">{site.cpu_percent.toFixed(1)}%</td>
                      <td className="px-3 py-2">{site.memory_percent.toFixed(1)}%</td>
                      <td className="px-3 py-2 text-xs">
                        {site.disk_limit_mb > 0
                          ? `${site.disk_used_mb} / ${site.disk_limit_mb} MB`
                          : `${site.disk_used_mb} MB`}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={mapStatus(site.status)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Box className="h-4 w-4" />
            Service Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {overview.services.map((service) => (
              <div key={service.name} className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm font-medium">{service.name}</span>
                <span className="flex items-center gap-1.5 text-xs">
                  <StatusBadge status={mapStatus(service.status)} />
                  {service.latency_ms != null && (
                    <span className="text-muted-foreground">{service.latency_ms}ms</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Network className="h-4 w-4" />
            Network Summary
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg bg-muted/50 p-4">
            <p className="text-xs text-muted-foreground">Inbound</p>
            <p className="text-2xl font-semibold">{host.network_in_mbps.toFixed(2)} Mbps</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-4">
            <p className="text-xs text-muted-foreground">Outbound</p>
            <p className="text-2xl font-semibold">{host.network_out_mbps.toFixed(2)} Mbps</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function MonitoringPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <MonitoringContent />
    </Suspense>
  );
}
