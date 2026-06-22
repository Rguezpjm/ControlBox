"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Blocks, RefreshCw, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateWordPressDialog } from "@/components/wordpress/create-wordpress-dialog";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";
import { SiteListTable, type SiteTableRow } from "@/components/shared/site-list-table";
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
    const interval = setInterval(loadSites, 10000);
    return () => clearInterval(interval);
  }, [loadSites]);

  async function handleDelete(id: string) {
    await wordpressApi.delete(id);
    loadSites();
  }

  async function handleRestart(id: string) {
    await wordpressApi.restart(id);
    loadSites();
  }

  const rows: SiteTableRow[] = sites.map((site) => ({
    id: site.id,
    name: site.name,
    domain: site.domain,
    status: site.status,
    ssl_enabled: site.ssl_enabled,
    ssl_status: site.ssl_status,
    ssl_days_remaining: site.ssl_days_remaining,
    requests_count: site.requests_count,
    requests_sparkline: site.requests_sparkline,
    subtitle: `PHP ${site.php_version} · WP ${site.wordpress_version}`,
  }));

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
      ) : (
        <SiteListTable
          rows={rows}
          searchPlaceholder="Search WordPress sites..."
          onSiteClick={(row) => {
            setModifySiteId(row.id);
            setModifyOpen(true);
          }}
          renderActions={(row) => (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  Manage
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link href={`/wordpress/${row.id}`}>Open dashboard</Link>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleRestart(row.id)}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Restart
                </DropdownMenuItem>
                <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(row.id)}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        />
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
