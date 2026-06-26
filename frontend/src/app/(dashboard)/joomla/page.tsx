"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Blocks, RefreshCw, Trash2, Search, MoreHorizontal } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateJoomlaDialog } from "@/components/joomla/create-joomla-dialog";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";
import { SiteMonitoringCard } from "@/components/shared/site-monitoring-card";
import { joomlaApi, type JoomlaSite } from "@/lib/joomla";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function JoomlaContent() {
  const [sites, setSites] = useState<JoomlaSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [modifySiteId, setModifySiteId] = useState<string | null>(null);
  const [modifyOpen, setModifyOpen] = useState(false);

  const loadSites = useCallback(async () => {
    try {
      const data = await joomlaApi.list();
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
    await joomlaApi.delete(id);
    loadSites();
  }

  async function handleRestart(id: string) {
    await joomlaApi.restart(id);
    loadSites();
  }

  if (loading) return <CardGridSkeleton count={3} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Joomla"
        description="Despliegue y gestione sitios Joomla con un solo clic."
        action={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Desplegar Joomla
          </Button>
        }
      />

      {sites.length > 0 && (
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar sitios Joomla..."
            className="pl-9"
          />
        </div>
      )}

      {sites.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Blocks className="mb-4 h-12 w-12 text-muted-foreground" />
            <h3 className="text-lg font-semibold">Aún no hay sitios Joomla</h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Despliegue Joomla con MySQL, Nginx, PHP-FPM y SSL en segundos.
            </p>
            <Button className="mt-4" onClick={() => setDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Desplegar Joomla
            </Button>
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">Ningún sitio coincide con la búsqueda</p>
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
                badge: `Joomla ${site.joomla_version}`,
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
                      <span className="sr-only">Gestionar</span>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem asChild>
                      <Link href={`/joomla/${site.id}`}>Abrir panel</Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleRestart(site.id)}>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Reiniciar
                    </DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(site.id)}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Eliminar
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              }
            />
          ))}
        </div>
      )}

      <CreateJoomlaDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreated={loadSites} />
      <SiteModificationModal
        open={modifyOpen}
        onOpenChange={setModifyOpen}
        siteType="joomla"
        siteId={modifySiteId}
        onUpdated={loadSites}
      />
    </div>
  );
}

export default function JoomlaPage() {
  return (
    <Suspense fallback={<CardGridSkeleton />}>
      <JoomlaContent />
    </Suspense>
  );
}
