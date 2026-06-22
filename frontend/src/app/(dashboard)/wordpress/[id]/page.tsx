"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  Copy,
  Layers,
  Archive,
  RotateCcw,
  Wrench,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { PageSkeleton } from "@/components/skeletons";
import { wordpressApi, type WordPressBackup, type WordPressSite } from "@/lib/wordpress";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

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

function WordPressDetailContent() {
  const params = useParams();
  const siteId = params.id as string;
  const [site, setSite] = useState<WordPressSite | null>(null);
  const [backups, setBackups] = useState<WordPressBackup[]>([]);
  const [phpVersion, setPhpVersion] = useState("8.3");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, b] = await Promise.all([
        wordpressApi.get(siteId),
        wordpressApi.listBackups(siteId),
      ]);
      setSite(s);
      setPhpVersion(s.php_version);
      setBackups(b);
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
        <p className="text-muted-foreground">WordPress site not found</p>
        <Button asChild variant="link" className="mt-2">
          <Link href="/wordpress">Back to WordPress</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/wordpress">
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
              href={site.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-sm text-primary hover:underline"
            >
              {site.url}
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
            <CardTitle className="text-sm font-medium text-muted-foreground">Database Size</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {formatBytes(site.db_size_mb * 1024 * 1024)}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge>PHP {site.php_version}</Badge>
              <Badge variant="outline">WordPress {site.wordpress_version}</Badge>
              <Badge variant={site.ssl_status === "active" ? "default" : "secondary"}>
                SSL: {site.ssl_status}
              </Badge>
            </div>
            <div className="space-y-2">
              <Label>PHP Version</Label>
              <div className="flex gap-2">
                <Select value={phpVersion} onValueChange={setPhpVersion}>
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="8.2">PHP 8.2</SelectItem>
                    <SelectItem value="8.3">PHP 8.3</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  disabled={actionLoading || phpVersion === site.php_version}
                  onClick={() => runAction(() => wordpressApi.changePhp(siteId, phpVersion))}
                >
                  Apply
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label>Maintenance Mode</Label>
                <p className="text-xs text-muted-foreground">Show maintenance page to visitors</p>
              </div>
              <Switch
                checked={site.maintenance_mode}
                onCheckedChange={(enabled) =>
                  runAction(() => wordpressApi.maintenance(siteId, enabled))
                }
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2">
            <Button
              variant="outline"
              disabled={actionLoading}
              onClick={() => runAction(() => wordpressApi.restart(siteId))}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Restart
            </Button>
            <Button
              variant="outline"
              disabled={actionLoading}
              onClick={() => runAction(() => wordpressApi.staging(siteId))}
            >
              <Layers className="mr-2 h-4 w-4" />
              Create Staging
            </Button>
            <Button
              variant="outline"
              disabled={actionLoading}
              onClick={() => runAction(() => wordpressApi.createBackup(siteId))}
            >
              <Archive className="mr-2 h-4 w-4" />
              Create Backup
            </Button>
            <Button
              variant="outline"
              disabled={actionLoading}
              onClick={() => {
                const domain = prompt("Clone domain:");
                const name = prompt("Clone name:");
                if (domain && name) {
                  runAction(() => wordpressApi.clone(siteId, domain, name));
                }
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Clone Site
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Backups</CardTitle>
          <Button
            size="sm"
            disabled={actionLoading}
            onClick={() => runAction(() => wordpressApi.createBackup(siteId))}
          >
            <Archive className="mr-2 h-4 w-4" />
            New Backup
          </Button>
        </CardHeader>
        <CardContent>
          {backups.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No backups yet</p>
          ) : (
            <div className="space-y-2">
              {backups.map((backup) => (
                <div
                  key={backup.id}
                  className="flex items-center justify-between rounded-lg border p-3 text-sm"
                >
                  <div>
                    <p className="font-medium">{backup.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {backup.status} · {formatBytes(backup.size_mb * 1024 * 1024)}
                    </p>
                  </div>
                  {backup.status === "completed" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={actionLoading}
                      onClick={() =>
                        runAction(() => wordpressApi.restoreBackup(siteId, backup.id))
                      }
                    >
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Restore
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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
    </div>
  );
}

export default function WordPressDetailPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <WordPressDetailContent />
    </Suspense>
  );
}
