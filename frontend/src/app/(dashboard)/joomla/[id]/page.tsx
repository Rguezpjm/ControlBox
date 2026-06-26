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
import { JoomlaSiteAccessPanel } from "@/components/joomla/site-access-panel";
import { joomlaApi, type JoomlaBackup, type JoomlaSite } from "@/lib/joomla";
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

function JoomlaDetailContent() {
  const params = useParams();
  const siteId = params.id as string;
  const [site, setSite] = useState<JoomlaSite | null>(null);
  const [backups, setBackups] = useState<JoomlaBackup[]>([]);
  const [phpVersion, setPhpVersion] = useState("8.3");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, b] = await Promise.all([
        joomlaApi.get(siteId),
        joomlaApi.listBackups(siteId),
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
        <p className="text-muted-foreground">Sitio Joomla no encontrado</p>
        <Button asChild variant="link" className="mt-2">
          <Link href="/joomla">Volver a Joomla</Link>
        </Button>
      </div>
    );
  }

  // Generate last 7 days names / data
  const chartData = (site.visits_sparkline && site.visits_sparkline.length > 0)
    ? site.visits_sparkline.map((visits, index) => {
        const date = new Date();
        date.setDate(date.getDate() - (site.visits_sparkline!.length - 1 - index));
        const dayLabel = date.toLocaleDateString("es-ES", { weekday: "short" });
        return { name: dayLabel, visits };
      })
    : Array.from({ length: 7 }).map((_, index) => {
        const date = new Date();
        date.setDate(date.getDate() - (6 - index));
        const dayLabel = date.toLocaleDateString("es-ES", { weekday: "short" });
        return { name: dayLabel, visits: [12, 19, 3, 5, 2, 3, 9][index] };
      });

  const domainExpirationDate = (() => {
    if (site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null) {
      const expirationDate = new Date();
      expirationDate.setDate(expirationDate.getDate() + site.ssl_days_remaining);
      return expirationDate.toLocaleDateString("es-ES", {
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    }
    return "Desconocido";
  })();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/joomla">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <PageHeader title={site.name} description={site.domain} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Estado</CardTitle>
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
            <CardTitle className="text-sm font-medium text-muted-foreground">Uso de Disco</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {formatBytes(site.disk_used_mb * 1024 * 1024)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Tamaño de BD</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {formatBytes(site.db_size_mb * 1024 * 1024)}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="grid gap-8 p-6 lg:grid-cols-2 lg:gap-10">
          <div className="space-y-8">
            <section className="space-y-4">
              <h3 className="text-lg font-semibold tracking-tight">Configuración</h3>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge>PHP {site.php_version}</Badge>
                  <Badge variant="outline">Joomla {site.joomla_version}</Badge>
                  <Badge variant={site.ssl_status === "active" ? "default" : "secondary"}>
                    SSL: {site.ssl_status}
                  </Badge>
                </div>
                <div className="space-y-2">
                  <Label>Versión de PHP</Label>
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
                      onClick={() => runAction(() => joomlaApi.changePhp(siteId, phpVersion))}
                    >
                      Aplicar
                    </Button>
                  </div>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label>Modo Mantenimiento</Label>
                    <p className="text-xs text-muted-foreground">Mostrar página de fuera de servicio a visitantes</p>
                  </div>
                  <Switch
                    checked={site.maintenance_mode}
                    onCheckedChange={(enabled) =>
                      runAction(() => joomlaApi.maintenance(siteId, enabled))
                    }
                  />
                </div>
              </div>
            </section>

            <section className="space-y-4 border-t pt-8">
              <h3 className="text-lg font-semibold tracking-tight">Acciones</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                <Button
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() => runAction(() => joomlaApi.restart(siteId))}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Reiniciar
                </Button>
                <Button
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() => runAction(() => joomlaApi.staging(siteId))}
                >
                  <Layers className="mr-2 h-4 w-4" />
                  Crear Staging
                </Button>
                <Button
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() => runAction(() => joomlaApi.createBackup(siteId))}
                >
                  <Archive className="mr-2 h-4 w-4" />
                  Crear Copia de Seguridad
                </Button>
                <Button
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() => {
                    const domain = prompt("Dominio de clonación:");
                    const name = prompt("Nombre del clon:");
                    if (domain && name) {
                      runAction(() => joomlaApi.clone(siteId, domain, name));
                    }
                  }}
                >
                  <Copy className="mr-2 h-4 w-4" />
                  Clonar Sitio
                </Button>
                <Button
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() =>
                    runAction(async () => {
                      const res = await joomlaApi.publish(siteId);
                      if (res.url) {
                        navigator.clipboard.writeText(res.url);
                        toast.success(`Sitio publicado en: ${res.url} (Copiado al portapapeles)`);
                      }
                    })
                  }
                >
                  <Share2 className="mr-2 h-4 w-4" />
                  Publicar
                </Button>
              </div>
            </section>
          </div>

          <section className="space-y-4 lg:border-l lg:pl-10">
            <h3 className="text-lg font-semibold tracking-tight">Acceso al sitio</h3>
            <JoomlaSiteAccessPanel
              embedded
              siteId={siteId}
              access={site.access_info}
              siteStatus={site.status}
              onUpdated={load}
            />
          </section>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Historial de Visitas
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Visitas totales registradas en los últimos 7 días
              </p>
            </div>
            <div className="text-right">
              <span className="text-3xl font-bold tracking-tight">
                {site.visit_count ?? 0}
              </span>
              <p className="text-xs text-muted-foreground">Visitas totales</p>
            </div>
          </CardHeader>
          <CardContent className="h-60 pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorVisits" x1="0" y1="0" x2="0" y2="1">
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
                          <p className="text-primary">{payload[0].value} visitas</p>
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
                  fill="url(#colorVisits)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" />
              Dominio y SSL
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center space-y-6">
            <div className="space-y-2">
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Estado del Dominio</span>
                <Badge variant={site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null && site.ssl_days_remaining > 0 ? "default" : "destructive"}>
                  {site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null && site.ssl_days_remaining > 0 ? "Activo" : "Expirado/Sin SSL"}
                </Badge>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Expiración</span>
                <span className="font-medium flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                  {domainExpirationDate}
                </span>
              </div>
            </div>

            <div className="rounded-lg bg-muted/40 p-4 border space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Días restantes:</span>
                <span className="font-semibold text-primary">
                  {site.ssl_days_remaining !== undefined && site.ssl_days_remaining !== null ? `${site.ssl_days_remaining} días` : '—'}
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

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Copias de seguridad</CardTitle>
          <Button
            size="sm"
            disabled={actionLoading}
            onClick={() => runAction(() => joomlaApi.createBackup(siteId))}
          >
            <Archive className="mr-2 h-4 w-4" />
            Nueva copia
          </Button>
        </CardHeader>
        <CardContent>
          {backups.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Aún no hay copias de seguridad</p>
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
                        runAction(() => joomlaApi.restoreBackup(siteId, backup.id))
                      }
                    >
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Restaurar
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

export default function JoomlaDetailPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <JoomlaDetailContent />
    </Suspense>
  );
}
