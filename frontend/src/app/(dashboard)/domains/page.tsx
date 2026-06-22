"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Cloud, Globe, Link2, Plus, Settings, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TableSkeleton } from "@/components/skeletons";
import { StatusBadge } from "@/components/shared/status-badge";
import { SiteModificationModal } from "@/components/sites/site-modification-modal";
import { CloudflareZoneDialog } from "@/components/cloudflare/cloudflare-zone-dialog";
import { websitesApi } from "@/lib/websites";
import { wordpressApi } from "@/lib/wordpress";
import { dnsApi } from "@/lib/dns";
import { cloudflareApi, type CloudflareSettings, type CloudflareZone } from "@/lib/cloudflare";
import type { SiteType } from "@/lib/site-modification";
import { toast } from "sonner";

interface DomainRow {
  id: string;
  domain: string;
  source: "Website" | "WordPress" | "DNS Zone" | "Cloudflare";
  siteType?: SiteType;
  status: string;
  ssl?: string;
  cloudflareZone?: CloudflareZone;
  paused?: boolean;
  underAttack?: boolean;
}

function DomainsContent() {
  const [rows, setRows] = useState<DomainRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [cfSettings, setCfSettings] = useState<CloudflareSettings | null>(null);
  const [modifyOpen, setModifyOpen] = useState(false);
  const [modifySiteId, setModifySiteId] = useState<string | null>(null);
  const [modifySiteType, setModifySiteType] = useState<SiteType>("website");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [cfZoneOpen, setCfZoneOpen] = useState(false);
  const [activeCfZone, setActiveCfZone] = useState<CloudflareZone | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [websites, wpSites, zones, cfConfig] = await Promise.all([
        websitesApi.list().catch(() => []),
        wordpressApi.list().catch(() => []),
        dnsApi.listZones().catch(() => []),
        cloudflareApi.getSettings().catch(() => null),
      ]);

      setCfSettings(cfConfig);

      const cfZones =
        cfConfig?.enabled && cfConfig.configured
          ? await cloudflareApi.listZones().catch(() => [])
          : [];

      const seen = new Set<string>();
      const next: DomainRow[] = [];

      for (const site of websites) {
        if (!site.domain || seen.has(site.domain)) continue;
        seen.add(site.domain);
        next.push({
          id: site.id,
          domain: site.domain,
          source: "Website",
          siteType: "website",
          status: site.status,
          ssl: site.ssl_status,
        });
      }

      for (const site of wpSites) {
        if (!site.domain || seen.has(site.domain)) continue;
        seen.add(site.domain);
        next.push({
          id: site.id,
          domain: site.domain,
          source: "WordPress",
          siteType: "wordpress",
          status: site.status,
          ssl: site.ssl_status,
        });
      }

      for (const zone of zones) {
        if (!zone.name || seen.has(zone.name)) continue;
        seen.add(zone.name);
        next.push({
          id: zone.id,
          domain: zone.name,
          source: "DNS Zone",
          status: zone.status ?? "active",
        });
      }

      for (const zone of cfZones) {
        if (!zone.name || seen.has(zone.name)) continue;
        seen.add(zone.name);
        next.push({
          id: zone.id,
          domain: zone.name,
          source: "Cloudflare",
          status: zone.status,
          paused: zone.paused,
          underAttack: zone.security_level === "under_attack",
          cloudflareZone: zone,
        });
      }

      setRows(next);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = useMemo(
    () => [...rows].sort((a, b) => a.domain.localeCompare(b.domain)),
    [rows]
  );

  const cloudflareActive = Boolean(cfSettings?.enabled && cfSettings?.configured);

  function handleManage(row: DomainRow) {
    if (row.source === "Cloudflare" && row.cloudflareZone) {
      setActiveCfZone(row.cloudflareZone);
      setCfZoneOpen(true);
      return;
    }
    if (!row.siteType) return;
    setModifySiteType(row.siteType);
    setModifySiteId(row.id);
    setModifyOpen(true);
  }

  async function handleDelete(row: DomainRow) {
    const label =
      row.source === "DNS Zone"
        ? "DNS zone"
        : row.source === "Cloudflare"
          ? "Cloudflare zone"
          : row.source.toLowerCase();
    if (!window.confirm(`Delete ${label} "${row.domain}"? This cannot be undone.`)) return;

    setDeletingId(row.id);
    try {
      if (row.source === "Website") {
        await websitesApi.delete(row.id);
      } else if (row.source === "WordPress") {
        await wordpressApi.delete(row.id);
      } else if (row.source === "Cloudflare") {
        await cloudflareApi.deleteZone(row.id);
      } else {
        await dnsApi.deleteZone(row.id);
      }
      await load();
    } catch {
      toast.error("No se pudo eliminar el dominio");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleCreateDomain() {
    const name = newDomain.trim().toLowerCase();
    if (!name) return;
    setCreating(true);
    try {
      await cloudflareApi.createZone(name);
      toast.success(`Dominio ${name} creado en Cloudflare`);
      setCreateOpen(false);
      setNewDomain("");
      await load();
    } catch {
      toast.error("No se pudo crear el dominio en Cloudflare");
    } finally {
      setCreating(false);
    }
  }

  if (loading && rows.length === 0) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Domains"
        description="Manage domains for websites, WordPress, DNS zones and Cloudflare"
        action={
          <div className="flex flex-wrap gap-2">
            {cloudflareActive && (
              <Button variant="default" className="bg-orange-500 hover:bg-orange-600" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Nuevo dominio CF
              </Button>
            )}
            <Button asChild variant="outline">
              <Link href="/websites">
                <Globe className="h-4 w-4" />
                Add website
              </Link>
            </Button>
          </div>
        }
      />

      {cloudflareActive && (
        <p className="rounded-lg border border-orange-500/30 bg-orange-500/5 px-4 py-3 text-xs text-orange-900 dark:text-orange-100">
          <Cloud className="mr-1.5 inline h-3.5 w-3.5" />
          Cloudflare conectado — puede pausar zonas, activar Under Attack y editar DNS desde Manage.
        </p>
      )}

      <Card>
        <CardContent className="p-0">
          {sorted.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              No domains yet. Create a website or connect Cloudflare in Settings.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Domain</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Source</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">SSL</th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((row) => (
                    <tr
                      key={`${row.source}-${row.id}`}
                      className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Link2 className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{row.domain}</span>
                          {row.paused && (
                            <Badge variant="secondary" className="text-[10px]">
                              Pausado
                            </Badge>
                          )}
                          {row.underAttack && (
                            <Badge variant="destructive" className="text-[10px]">
                              Under Attack
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={row.source === "Cloudflare" ? "border-orange-400 text-orange-600" : ""}>
                          {row.source}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">
                        {row.ssl ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {(row.siteType || row.source === "Cloudflare") && (
                            <Button variant="outline" size="sm" onClick={() => handleManage(row)}>
                              <Settings className="h-3.5 w-3.5 mr-1.5" />
                              Manage
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            disabled={deletingId === row.id}
                            onClick={() => void handleDelete(row)}
                          >
                            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <SiteModificationModal
        open={modifyOpen}
        onOpenChange={setModifyOpen}
        siteType={modifySiteType}
        siteId={modifySiteId}
        onUpdated={load}
      />

      <CloudflareZoneDialog
        open={cfZoneOpen}
        onOpenChange={setCfZoneOpen}
        zone={activeCfZone}
        onUpdated={load}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo dominio en Cloudflare</DialogTitle>
            <DialogDescription>
              Agrega una zona en Cloudflare. Luego configure los nameservers en su registrador.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            placeholder="ejemplo.com"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => void handleCreateDomain()} disabled={creating || !newDomain.trim()}>
              Crear dominio
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function DomainsPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <DomainsContent />
    </Suspense>
  );
}
