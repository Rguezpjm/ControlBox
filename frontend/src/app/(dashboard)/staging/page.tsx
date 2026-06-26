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
  Wrench,
  Check,
  X,
  Upload,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

interface StagingCardProps {
  site: StagingSite;
  onSync: (id: string, direction: "from" | "to") => void;
  onRestart: (id: string) => void;
  onBlock: (id: string, blocked: boolean) => void;
  onDelete: (id: string) => void;
  onRefresh: () => void;
}

function StagingCard({ site, onSync, onRestart, onBlock, onDelete, onRefresh }: StagingCardProps) {
  const [cmsVersion, setCmsVersion] = useState(site.cms_version || "");
  const [phpVersion, setPhpVersion] = useState(site.runtime_version || "8.3");
  const [updating, setUpdating] = useState(false);
  const [showVersionForm, setShowVersionForm] = useState(false);

  useEffect(() => {
    if (site.cms_version) setCmsVersion(site.cms_version);
    if (site.runtime_version) setPhpVersion(site.runtime_version);
  }, [site.cms_version, site.runtime_version]);

  async function handleVersionUpdate() {
    setUpdating(true);
    try {
      await stagingApi.changeVersion(site.id, cmsVersion, phpVersion);
      setShowVersionForm(false);
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to change version");
    } finally {
      setUpdating(false);
    }
  }

  async function handleBloggerUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUpdating(true);
    try {
      await stagingApi.importBlogger(site.id, file);
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to import Blogger");
    } finally {
      setUpdating(false);
    }
  }

  async function handleJoomlaToWp() {
    if (!confirm("Are you sure you want to migrate this Joomla staging site to WordPress? This will recreate the containers as WordPress and convert database items.")) return;
    setUpdating(true);
    try {
      await stagingApi.migrateJoomlaToWp(site.id);
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to migrate Joomla to WordPress");
    } finally {
      setUpdating(false);
    }
  }

  return (
    <Card className="transition-shadow hover:shadow-md relative overflow-hidden">
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
          {site.cms_version && (
            <Badge variant="outline">
              V: {site.cms_version}
            </Badge>
          )}
          <Badge variant="outline">
            PHP: {site.runtime_version}
          </Badge>
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

        {/* Database Migration Progress Bar */}
        {site.migration_progress !== null && site.migration_progress !== undefined && (
          <div className="space-y-1.5 p-3 bg-muted/40 rounded-lg border border-primary/20 animate-pulse">
            <div className="flex justify-between text-xs text-primary font-semibold">
              <span className="truncate max-w-[80%]">{site.migration_status || "Migrating data..."}</span>
              <span>{site.migration_progress}%</span>
            </div>
            <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
              <div 
                className="bg-primary h-full transition-all duration-500" 
                style={{ width: `${site.migration_progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Inline PHP & CMS Version Form */}
        {showVersionForm && (
          <div className="space-y-3 p-3 bg-muted/30 rounded-lg border">
            <h4 className="text-xs font-semibold">Switch Environment Versions</h4>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label htmlFor={`cms-${site.id}`} className="text-[10px]">CMS Version</Label>
                <Input 
                  id={`cms-${site.id}`} 
                  value={cmsVersion} 
                  onChange={(e) => setCmsVersion(e.target.value)}
                  placeholder="e.g. 6.5.5 or 5.1.1"
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`php-${site.id}`} className="text-[10px]">PHP Version</Label>
                <Select value={phpVersion} onValueChange={setPhpVersion}>
                  <SelectTrigger id={`php-${site.id}`} className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7.4">7.4</SelectItem>
                    <SelectItem value="8.0">8.0</SelectItem>
                    <SelectItem value="8.1">8.1</SelectItem>
                    <SelectItem value="8.2">8.2</SelectItem>
                    <SelectItem value="8.3">8.3</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setShowVersionForm(false)}>
                <X className="mr-1 h-3.5 w-3.5" /> Cancel
              </Button>
              <Button size="sm" className="h-7 text-xs" disabled={updating} onClick={handleVersionUpdate}>
                <Check className="mr-1 h-3.5 w-3.5" /> Apply
              </Button>
            </div>
          </div>
        )}

        {/* Hidden Blogger File Upload Input */}
        <input 
          type="file" 
          id={`blogger-upload-${site.id}`}
          className="hidden"
          accept=".xml"
          onChange={handleBloggerUpload}
        />

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild disabled={updating}>
            <a href={`https://${site.domain}`} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-1 h-3 w-3" />
              Open
            </a>
          </Button>

          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setShowVersionForm(!showVersionForm)} 
            disabled={updating || site.stack_type === "html"}
          >
            <Wrench className="mr-1 h-3 w-3" />
            Switch Version
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={updating}>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onSync(site.id, "from")}>
                <ArrowDownToLine className="mr-2 h-4 w-4" />
                Sync from production
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onSync(site.id, "to")}>
                <ArrowUpFromLine className="mr-2 h-4 w-4" />
                Sync to production
              </DropdownMenuItem>
              
              <DropdownMenuSeparator />
              
              <DropdownMenuItem onClick={() => document.getElementById(`blogger-upload-${site.id}`)?.click()}>
                <Upload className="mr-2 h-4 w-4" />
                Import Blogger Backup
              </DropdownMenuItem>

              {site.stack_type === "joomla" && (
                <DropdownMenuItem onClick={handleJoomlaToWp}>
                  <RefreshCw className="mr-2 h-4 w-4 text-primary" />
                  <span className="text-primary font-medium">Migrate to WordPress</span>
                </DropdownMenuItem>
              )}

              <DropdownMenuSeparator />

              <DropdownMenuItem onClick={() => onRestart(site.id)}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Restart
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onBlock(site.id, !site.public_access_blocked)}>
                <Shield className="mr-2 h-4 w-4" />
                {site.public_access_blocked ? "Allow public access" : "Block public access"}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive" onClick={() => onDelete(site.id)}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete staging
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
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
    const interval = setInterval(loadSites, 5000); // Poll faster (5s) to capture migration progress in real-time
    return () => clearInterval(interval);
  }, [loadSites]);

  async function handleSync(id: string, direction: "from" | "to") {
    if (direction === "from") await stagingApi.syncFromProduction(id, syncType);
    else await stagingApi.syncToProduction(id, syncType);
    loadSites();
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this staging environment?")) return;
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
            <StagingCard 
              key={site.id} 
              site={site} 
              onSync={handleSync} 
              onRestart={handleRestart} 
              onBlock={handleBlock} 
              onDelete={handleDelete}
              onRefresh={loadSites}
            />
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
