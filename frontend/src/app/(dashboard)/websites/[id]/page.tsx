"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  Play,
  Square,
  Wrench,
  Settings,
  Share2,
  TrendingUp,
  Calendar,
  Globe,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { PageSkeleton } from "@/components/skeletons";
import { websitesApi, type Website } from "@/lib/websites";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";
import { CredentialRow } from "@/components/wordpress/credential-row";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    running: "running",
    stopped: "stopped",
    pending: "pending",
    provisioning: "pending",
    maintenance: "pending",
    error: "error",
  };
  return map[status] || "pending";
}

const RUNTIME_LABELS: Record<string, string> = {
  html: "HTML Static",
  php: "PHP",
  nodejs: "Node.js",
  python: "Python",
  flutter: "Flutter Web",
};

function WebsiteDetailContent() {
  const params = useParams();
  const siteId = params.id as string;
  const [site, setSite] = useState<Website | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [modifyOpen, setModifyOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const s = await websitesApi.get(siteId);
      setSite(s);
    } catch {
      setSite(null);
    } finally {
      setLoading(false);
    }
  }, [siteId]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, [load]);

  async function runAction(fn: () => Promise<unknown>) {
    setActionLoading(true);
    try {
      await fn();
      await load();
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <PageSkeleton />;
  if (!site) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Website not found</p>
        <Button asChild variant="link" className="mt-2">
          <Link href="/websites">Back to Websites</Link>
        </Button>
      </div>
    );
  }

  // Generate last 7 days names / data
  const chartData = (site.visits_sparkline && site.visits_sparkline.length > 0)
    ? site.visits_sparkline.map((visits, index) => {
        const date = new Date();
        date.setDate(date.getDate() - (site.visits_sparkline!.length - 1 - index));
        const dayLabel = date.toLocaleDateString("en-US", { weekday: "short" });
        return { name: dayLabel, visits };
      })
    : Array.from({ length: 7 }).map((_, index) => {
        const date = new Date();
        date.setDate(date.getDate() - (6 - index));
        const dayLabel = date.toLocaleDateString("en-US", { weekday: "short" });
        return { name: dayLabel, visits: [12, 19, 3, 5, 2, 3, 9][index] };
      });

  const domainExpirationDate = (() => {
    if (site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null) {
      const expirationDate = new Date();
      expirationDate.setDate(expirationDate.getDate() + site.ssl_days_remaining);
      return expirationDate.toLocaleDateString("en-US", {
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    }
    return "Unknown";
  })();

  const dbConfig = site.database_config || {};
  const hasDb = site.database_engine && site.database_engine !== "none";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/websites">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <PageHeader title={site.name} description={site.domain} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
          </CardHeader>
          <CardContent>
            <StatusBadge status={mapStatus(site.status)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">URL</CardTitle>
          </CardHeader>
          <CardContent>
            <a
              href={`https://${site.domain}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-sm text-primary hover:underline"
            >
              {site.domain}
              <ExternalLink className="ml-1 h-3 w-3" />
            </a>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Disk Usage</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {formatBytes(site.disk_used_mb * 1024 * 1024)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Port</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {site.port || "—"}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="grid gap-8 p-6 lg:grid-cols-2 lg:gap-10">
          <div className="space-y-8">
            <section className="space-y-4">
              <h3 className="text-lg font-semibold tracking-tight">Configuration</h3>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge>{RUNTIME_LABELS[site.runtime] || site.runtime} {site.runtime_version}</Badge>
                  <Badge variant={site.ssl_status === "active" ? "default" : "secondary"}>
                    SSL: {site.ssl_status}
                  </Badge>
                  {hasDb && <Badge variant="outline">DB: {site.database_engine}</Badge>}
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label>Advanced settings</Label>
                    <p className="text-xs text-muted-foreground">Manage domains, SSL certificates, runtime flags, etc.</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setModifyOpen(true)}>
                    <Settings className="mr-2 h-4 w-4" />
                    Configure
                  </Button>
                </div>
              </div>
            </section>

            <section className="space-y-4 border-t pt-8">
              <h3 className="text-lg font-semibold tracking-tight">Actions</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {site.status !== "running" ? (
                  <Button
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() => runAction(() => websitesApi.start(siteId))}
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Start
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() => runAction(() => websitesApi.stop(siteId))}
                  >
                    <Square className="mr-2 h-4 w-4" />
                    Stop
                  </Button>
                )}
                <Button
                  variant="outline"
                  disabled={actionLoading || site.status !== "running"}
                  onClick={() =>
                    runAction(async () => {
                      await websitesApi.stop(siteId);
                      await websitesApi.start(siteId);
                    })
                  }
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Restart
                </Button>
                <Button
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() =>
                    runAction(async () => {
                      const res = await websitesApi.publish(siteId);
                      if (res.url) {
                        navigator.clipboard.writeText(res.url);
                        toast.success(`Site published to: ${res.url} (Copied to clipboard)`);
                      }
                    })
                  }
                >
                  <Share2 className="mr-2 h-4 w-4" />
                  Publish
                </Button>
              </div>
            </section>
          </div>

          <section className="space-y-4 lg:border-l lg:pl-10">
            <h3 className="text-lg font-semibold tracking-tight">Access details</h3>
            <div className="space-y-6">
              {hasDb && (
                <div className="space-y-3 rounded-lg border p-4">
                  <p className="text-sm font-medium">Database ({site.database_engine})</p>
                  <CredentialRow label="DB_NAME" value={dbConfig.database_name as string} mono />
                  <CredentialRow label="DB_USER" value={dbConfig.username as string} mono />
                  <CredentialRow label="DB_HOST" value={dbConfig.host as string} mono />
                  <CredentialRow label="DB_PORT" value={dbConfig.port ? String(dbConfig.port) : undefined} mono />
                </div>
              )}

              {/* FTP Credentials if present */}
              {(site.ftp_username || site.ftp_home) && (
                <div className="space-y-3 rounded-lg border p-4">
                  <p className="text-sm font-medium">FTP</p>
                  <CredentialRow label="FTP user" value={site.ftp_username} mono />
                  {site.ftp_password && <CredentialRow label="FTP password" value={site.ftp_password} secret mono />}
                  <CredentialRow label="FTP directory" value={site.ftp_home} mono />
                </div>
              )}

              {!hasDb && !site.ftp_username && (
                <p className="text-sm text-muted-foreground">No specific database or FTP credentials configured for this website.</p>
              )}
            </div>
          </section>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Visits History
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Total visits registered in the last 7 days
              </p>
            </div>
            <div className="text-right">
              <span className="text-3xl font-bold tracking-tight">
                {site.visit_count ?? 0}
              </span>
              <p className="text-xs text-muted-foreground">Total visits</p>
            </div>
          </CardHeader>
          <CardContent className="h-60 pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorVisitsWebsites" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-muted/30" />
                <XAxis
                  dataKey="name"
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="rounded-lg border bg-background p-2 shadow-sm text-xs">
                          <p className="font-semibold">{payload[0].payload.name}</p>
                          <p className="text-primary">{payload[0].value} visits</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="visits"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorVisitsWebsites)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" />
              Domain & SSL
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center space-y-6">
            <div className="space-y-2">
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Domain Status</span>
                <Badge variant={site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null && site.ssl_days_remaining > 0 ? "default" : "destructive"}>
                  {site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null && site.ssl_days_remaining > 0 ? "Active" : "Expired/No SSL"}
                </Badge>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Expiration Date</span>
                <span className="font-medium flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                  {domainExpirationDate}
                </span>
              </div>
            </div>

            <div className="rounded-lg bg-muted/40 p-4 border space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Days remaining:</span>
                <span className="font-semibold text-primary">
                  {site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null ? `${site.ssl_days_remaining} days` : '—'}
                </span>
              </div>
              {site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null && (
                <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${site.ssl_days_remaining < 15 ? 'bg-destructive' : 'bg-primary'}`}
                    style={{ width: `${Math.min(100, Math.max(0, (site.ssl_days_remaining / 90) * 100))}%` }}
                  />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {site.error_message && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <Wrench className="h-4 w-4" />
              Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{site.error_message}</p>
          </CardContent>
        </Card>
      )}

      <SiteModificationModal
        open={modifyOpen}
        onOpenChange={setModifyOpen}
        siteType="website"
        siteId={siteId}
        onUpdated={load}
      />
    </div>
  );
}

export default function WebsiteDetailPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <WebsiteDetailContent />
    </Suspense>
  );
}
