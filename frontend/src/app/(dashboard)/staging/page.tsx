"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import {
  Plus,
  Layers,
  RefreshCw,
  Trash2,
  ArrowDownToLine,
  ArrowUpFromLine,
  Shield,
  Lock,
  ExternalLink,
  MoreHorizontal,
  Cpu,
  HardDrive,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CreateStagingDialog } from "@/components/staging/create-staging-dialog";
import { stagingApi, type StagingSite, type SyncType } from "@/lib/staging";
import type { ResourceStatus } from "@/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    running: "running",
    stopped: "stopped",
    pending: "pending",
    provisioning: "pending",
    syncing: "pending",
    deleting: "pending",
    error: "error",
  };
  return map[status] || "pending";
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function StagingContent() {
  const [sites, setSites] = useState<StagingSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [syncType, setSyncType] = useState<SyncType>("full");

  const loadSites = useCallback(async () => {
    try {
      const data = await stagingApi.list();
      setSites(data);
    } catch {
      setSites([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSites();
    const interval = setInterval(loadSites, 10000);
    return () => clearInterval(interval);
  }, [loadSites]);

  async function handleSync(id: string, direction: "from" | "to") {
    if (direction === "from") await stagingApi.syncFromProduction(id, syncType);
    else await stagingApi.syncToProduction(id, syncType);
    loadSites();
  }

  async function handleDelete(id: string) {
    await stagingApi.delete(id);
    loadSites();
  }

  async function handleRestart(id: string) {
    await stagingApi.restart(id);
    loadSites();
  }

  async function handleBlock(id: string, blocked: boolean) {
    await stagingApi.blockAccess(id, blocked);
    loadSites();
  }

  if (loading) {
    return <div className="flex h-48 items-center justify-center text-muted-foreground">Loading staging...</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Staging Sites"
        description="Isolated staging environments with independent containers, databases and SSL."
        action={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Staging
          </Button>
        }
      />

      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Default sync:</span>
        <Select value={syncType} onValueChange={(v) => setSyncType(v as SyncType)}>
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="files">Files only</SelectItem>
            <SelectItem value="database">Database only</SelectItem>
            <SelectItem value="full">Files + Database</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {sites.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Layers className="mb-4 h-12 w-12 text-muted-foreground" />
            <h3 className="text-lg font-semibold">No staging environments</h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Create an isolated clone of any production site with separate database and metrics.
            </p>
            <Button className="mt-4" onClick={() => setDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Staging
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {sites.map((site) => (
            <Card key={site.id} className="transition-shadow hover:shadow-md">
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div className="space-y-1">
                  <CardTitle className="text-base">{site.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">{site.domain}</p>
                  <p className="text-xs text-muted-foreground">
                    Production: {site.source_domain}
                  </p>
                </div>
                <StatusBadge status={mapStatus(site.status)} />
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{site.stack_type}</Badge>
                  <Badge variant="outline">{site.source_type}</Badge>
                  <Badge variant={site.ssl_status === "active" ? "default" : "secondary"}>
                    SSL {site.ssl_status}
                  </Badge>
                  {site.public_access_blocked && (
                    <Badge variant="destructive">
                      <Lock className="mr-1 h-3 w-3" />
                      Blocked
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Cpu className="h-3 w-3" />
                    {site.cpu_usage_percent.toFixed(1)}% CPU
                  </div>
                  <div>{site.memory_used_mb} MB RAM</div>
                  <div className="flex items-center gap-1">
                    <HardDrive className="h-3 w-3" />
                    {site.disk_used_mb} MB
                  </div>
                </div>

                <div className="text-xs text-muted-foreground">
                  <p>Created: {formatDate(site.created_at)}</p>
                  <p>Last sync: {formatDate(site.last_sync_at)} {site.last_sync_type ? `(${site.last_sync_type})` : ""}</p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" asChild>
                    <a href={`https://${site.domain}`} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="mr-1 h-3 w-3" />
                      Open
                    </a>
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleSync(site.id, "from")}>
                        <ArrowDownToLine className="mr-2 h-4 w-4" />
                        Sync from production
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleSync(site.id, "to")}>
                        <ArrowUpFromLine className="mr-2 h-4 w-4" />
                        Sync to production
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleRestart(site.id)}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Restart
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleBlock(site.id, !site.public_access_blocked)}>
                        <Shield className="mr-2 h-4 w-4" />
                        {site.public_access_blocked ? "Allow public access" : "Block public access"}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(site.id)}>
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete staging
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateStagingDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreated={loadSites} />
    </div>
  );
}

export default function StagingPage() {
  return (
    <Suspense fallback={<div className="p-6">Loading...</div>}>
      <StagingContent />
    </Suspense>
  );
}
