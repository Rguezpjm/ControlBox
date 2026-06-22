"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Blocks, RefreshCw, Trash2, Search, MoreHorizontal } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateWordPressDialog } from "@/components/wordpress/create-wordpress-dialog";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";
import { SiteMonitoringCard } from "@/components/shared/site-monitoring-card";
import { wordpressApi, type WordPressSite } from "@/lib/wordpress";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function WordPressContent() {
  const [sites, setSites] = useState<WordPressSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [modifySiteId, setModifySiteId] = useState<string | null>(null);
  const [modifyOpen, setModifyOpen] = useState(false);

  const loadSites = useCallback(async () => {
    try {
      const data = await wordpressApi.list();
      setSites(data);
    } catch {
      setSites([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSites();
    const interval = setInterval(loadSites, 30000);
    return () => clearInterval(interval);
  }, [loadSites]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sites;
    return sites.filter(
      (site) =>
        site.name.toLowerCase().includes(q) ||
        site.domain.toLowerCase().includes(q)
    );
  }, [sites, query]);

  async function handleDelete(id: string) {
    await wordpressApi.delete(id);
    loadSites();
  }

  async function handleRestart(id: string) {
    await wordpressApi.restart(id);
    loadSites();
  }

  if (loading) return <CardGridSkeleton count={3} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="WordPress"
        description="Deploy and manage WordPress sites with one click."
        action={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Deploy WordPress
          </Button>
        }
      />

      {sites.length > 0 && (
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search WordPress sites..."
            className="pl-9"
          />
        </div>
      )}

      {sites.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Blocks className="mb-4 h-12 w-12 text-muted-foreground" />
            <h3 className="text-lg font-semibold">No WordPress sites yet</h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Deploy WordPress with MySQL, Nginx, PHP-FPM and SSL in seconds.
            </p>
            <Button className="mt-4" onClick={() => setDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Deploy WordPress
            </Button>
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">No sites match your search</p>
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
                badge: `WP ${site.wordpress_version}`,
                error_message: site.error_message,
                disk_used_mb: site.disk_used_mb,
                monitoring_enabled: true,
                logs_enabled: true,
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
                    <DropdownMenuItem asChild>
                      <Link href={`/wordpress/${site.id}`}>Open dashboard</Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleRestart(site.id)}>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Restart
                    </DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(site.id)}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              }
            />
          ))}
        </div>
      )}

      <CreateWordPressDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreated={loadSites} />
      <SiteModificationModal
        open={modifyOpen}
        onOpenChange={setModifyOpen}
        siteType="wordpress"
        siteId={modifySiteId}
        onUpdated={loadSites}
      />
    </div>
  );
}

export default function WordPressPage() {
  return (
    <Suspense fallback={<CardGridSkeleton />}>
      <WordPressContent />
    </Suspense>
  );
}
