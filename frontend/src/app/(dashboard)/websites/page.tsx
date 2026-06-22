"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { Plus, Globe, Play, Square, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateWebsiteDialog } from "@/components/websites/create-website-dialog";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";
import { SiteListTable, type SiteTableRow } from "@/components/shared/site-list-table";
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
    const interval = setInterval(loadWebsites, 15000);
    return () => clearInterval(interval);
  }, [loadWebsites]);

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

  const rows: SiteTableRow[] = websites.map((site) => ({
    id: site.id,
    name: site.name,
    domain: site.domain,
    status: site.status,
    ssl_enabled: site.ssl_enabled,
    ssl_status: site.ssl_status,
    ssl_days_remaining: site.ssl_days_remaining,
    requests_count: site.requests_count,
    requests_sparkline: site.requests_sparkline,
    subtitle: `${RUNTIME_LABELS[site.runtime] || site.runtime}${site.runtime_version ? ` ${site.runtime_version}` : ""}`,
  }));

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
      ) : (
        <SiteListTable
          rows={rows}
          searchPlaceholder="Search by name or domain..."
          onSiteClick={(row) => {
            setModifySiteId(row.id);
            setModifyOpen(true);
          }}
          renderActions={(row) => {
            const site = websites.find((s) => s.id === row.id);
            if (!site) return null;
            return (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm">
                    Manage
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
            );
          }}
        />
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
