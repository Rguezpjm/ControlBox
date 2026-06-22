"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Globe, Play, Square, Trash2, Search, MoreHorizontal } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateWebsiteDialog } from "@/components/websites/create-website-dialog";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";
import { SiteMonitoringCard } from "@/components/shared/site-monitoring-card";
import { websitesApi, type Website } from "@/lib/websites";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const RUNTIME_LABELS: Record<string, string> = {
  html: "HTML",
  php: "PHP",
  nodejs: "Node.js",
  python: "Python",
  flutter: "Flutter",
};

function WebsitesContent() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [modifySiteId, setModifySiteId] = useState<string | null>(null);
  const [modifyOpen, setModifyOpen] = useState(false);

  const loadWebsites = useCallback(async () => {
    try {
      const data = await websitesApi.list();
      setWebsites(data);
    } catch {
      setWebsites([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWebsites();
    const interval = setInterval(loadWebsites, 30000);
    return () => clearInterval(interval);
  }, [loadWebsites]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return websites;
    return websites.filter(
      (site) =>
        site.name.toLowerCase().includes(q) ||
        site.domain.toLowerCase().includes(q) ||
        site.runtime.toLowerCase().includes(q)
    );
  }, [websites, query]);

  async function handleDelete(id: string) {
    await websitesApi.delete(id);
    loadWebsites();
  }

  async function handleStart(id: string) {
    await websitesApi.start(id);
    loadWebsites();
  }

  async function handleStop(id: string) {
    await websitesApi.stop(id);
    loadWebsites();
  }

  if (loading) return <CardGridSkeleton count={3} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Websites"
        description="Manage your hosted websites and applications"
        action={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            New Website
          </Button>
        }
      />

      {websites.length > 0 && (
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or domain..."
            className="pl-9"
          />
        </div>
      )}

      {websites.length === 0 ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <Globe className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-lg font-medium">No websites yet</p>
          <p className="text-sm text-muted-foreground mb-4">Create your first website to get started</p>
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Website
          </Button>
        </Card>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">No websites match your search</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((site) => (
            <SiteMonitoringCard
              key={site.id}
              site={{
                id: site.id,
                name: site.name,
                domain: site.domain,
                status: site.status,
                badge: RUNTIME_LABELS[site.runtime] || site.runtime,
                error_message: site.error_message,
                disk_used_mb: site.disk_used_mb,
                disk_limit_mb: site.disk_limit_mb,
                monitoring_enabled: site.monitoring_enabled,
                logs_enabled: site.logs_enabled,
                visit_count: site.visit_count,
                visits_sparkline: site.visits_sparkline,
                uptime_timeline: site.uptime_timeline,
                uptime_percent: site.uptime_percent,
                last_down_reason: site.last_down_reason,
                last_down_reason_label: site.last_down_reason_label,
                is_up: site.is_up,
              }}
              onClick={() => {
                setModifySiteId(site.id);
                setModifyOpen(true);
              }}
              actions={
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <span className="sr-only">Manage</span>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {site.status !== "running" && (
                      <DropdownMenuItem onClick={() => handleStart(site.id)}>
                        <Play className="h-4 w-4 mr-2" />
                        Start
                      </DropdownMenuItem>
                    )}
                    {site.status === "running" && (
                      <DropdownMenuItem onClick={() => handleStop(site.id)}>
                        <Square className="h-4 w-4 mr-2" />
                        Stop
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(site.id)}>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              }
            />
          ))}
        </div>
      )}

      <CreateWebsiteDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreated={loadWebsites} />
      <SiteModificationModal
        open={modifyOpen}
        onOpenChange={setModifyOpen}
        siteType="website"
        siteId={modifySiteId}
        onUpdated={loadWebsites}
      />
    </div>
  );
}

export default function WebsitesPage() {
  return (
    <Suspense fallback={<CardGridSkeleton />}>
      <WebsitesContent />
    </Suspense>
  );
}
