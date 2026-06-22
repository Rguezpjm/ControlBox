"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Circle,
  Database,
  ExternalLink,
  HardDrive,
  Loader2,
  Package,
  Server,
  Shield,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  applyServiceProfiles,
  confirmSecretsReviewed,
  getPlatformOverview,
  getServiceProfiles,
  updateSetupChecklist,
  type PlatformOverview,
  type ServiceProfile,
} from "@/lib/platform";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const SERVICE_ICONS: Record<string, typeof Database> = {
  databases: Database,
  backups: HardDrive,
  monitoring: Server,
  supabase: Package,
};

const CHECKLIST_ACTIONS: Record<string, { href: string; label: string }> = {
  configure_panel_access: { href: "/settings", label: "Abrir ajustes" },
  enable_totp: { href: "/security", label: "Seguridad" },
  configure_domains: { href: "/domains", label: "Dominios" },
  review_alert_thresholds: { href: "/settings", label: "Monitor y alertas" },
};

interface ProductionSetupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete?: () => void;
}

export function ProductionSetupDialog({ open, onOpenChange, onComplete }: ProductionSetupDialogProps) {
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [services, setServices] = useState<ServiceProfile[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [manageMessage, setManageMessage] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, svc] = await Promise.all([getPlatformOverview(), getServiceProfiles()]);
      setOverview(ov);
      setServices(svc.services);
      setCanManage(svc.can_manage);
      setManageMessage(svc.message);
      setSelected(new Set(svc.services.filter((s) => s.enabled).map((s) => s.id)));
    } catch {
      toast.error("No se pudo cargar la configuración de producción");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const lnmpServices = useMemo(() => services.filter((s) => s.category === "lnmp"), [services]);
  const platformServices = useMemo(() => services.filter((s) => s.category === "platform"), [services]);

  function toggleService(id: string, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) {
        next.add(id);
        const svc = services.find((s) => s.id === id);
        svc?.requires.forEach((r) => next.add(r));
      } else {
        next.delete(id);
        if (id === "backups") next.delete("supabase");
      }
      return next;
    });
  }

  async function handleApplyServices() {
    const profiles = Array.from(selected);
    if (profiles.length === 0) {
      toast.error("Seleccione al menos un servicio");
      return;
    }
    setApplying(true);
    try {
      const result = await applyServiceProfiles(profiles);
      toast[result.success ? "success" : "error"](result.message);
      if (result.success) await load();
      onComplete?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al instalar servicios");
    } finally {
      setApplying(false);
    }
  }

  async function markChecklist(key: string, completed: boolean) {
    try {
      await updateSetupChecklist(key, completed);
      await load();
      onComplete?.();
    } catch {
      toast.error("No se pudo actualizar el checklist");
    }
  }

  async function handleConfirmSecrets() {
    try {
      await confirmSecretsReviewed();
      toast.success("Revisión de seguridad confirmada");
      await load();
    } catch {
      toast.error("No se pudo confirmar");
    }
  }

  function renderServiceCard(svc: ServiceProfile) {
    const Icon = SERVICE_ICONS[svc.id] ?? Package;
    const isOn = selected.has(svc.id);
    return (
      <div
        key={svc.id}
        className={cn(
          "flex items-start gap-3 rounded-lg border p-4 transition-colors",
          isOn ? "border-primary/40 bg-primary/5" : "border-border bg-card"
        )}
      >
        <div className="mt-0.5 rounded-md bg-muted p-2">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">{svc.name}</p>
            {svc.running && (
              <Badge variant="outline" className="h-5 border-emerald-500/40 text-[10px] text-emerald-600">
                En ejecución
              </Badge>
            )}
            {svc.enabled && !svc.running && (
              <Badge variant="outline" className="h-5 text-[10px]">
                Configurado
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">{svc.description}</p>
          {svc.requires.length > 0 && (
            <p className="text-[10px] text-amber-700 dark:text-amber-300">
              Requiere: {svc.requires.join(", ")}
            </p>
          )}
        </div>
        <Switch checked={isOn} onCheckedChange={(v) => toggleService(svc.id, v)} disabled={!canManage} />
      </div>
    );
  }

  const checklist = overview?.setup_checklist;
  const secretsPending = overview?.secrets_rotation.items.filter((s) => !s.rotated).length ?? 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="h-5 w-5 text-primary" />
            Configuración del servidor
          </DialogTitle>
          <DialogDescription>
            Elija qué servicios instalar y complete el checklist de producción (estilo aaPanel).
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <Tabs defaultValue="services" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="services">Software</TabsTrigger>
              <TabsTrigger value="checklist">
                Checklist
                {checklist && checklist.completed_count < checklist.total_count && (
                  <span className="ml-1.5 rounded-full bg-amber-500 px-1.5 text-[10px] text-white">
                    {checklist.total_count - checklist.completed_count}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="security">Seguridad</TabsTrigger>
            </TabsList>

            <TabsContent value="services" className="mt-4 space-y-4">
              {!canManage && manageMessage && (
                <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-200">
                  {manageMessage}
                </p>
              )}

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Stack LNMP
                </p>
                <div className="space-y-2">{lnmpServices.map(renderServiceCard)}</div>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Plataforma
                </p>
                <div className="space-y-2">{platformServices.map(renderServiceCard)}</div>
              </div>

              <div className="flex justify-end gap-2 border-t pt-4">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  Cerrar
                </Button>
                <Button onClick={handleApplyServices} disabled={!canManage || applying}>
                  {applying ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Instalar / actualizar servicios
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="checklist" className="mt-4 space-y-3">
              {checklist?.items.map((item) => {
                const action = CHECKLIST_ACTIONS[item.key];
                return (
                  <div
                    key={item.key}
                    className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3"
                  >
                    <div className="flex items-start gap-2.5">
                      {item.completed ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                      ) : (
                        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                      <div>
                        <p className="text-sm font-medium">{item.label}</p>
                        {item.key === "configure_services" && !item.completed && (
                          <p className="text-xs text-muted-foreground">
                            Use la pestaña Software para instalar MySQL, MinIO, etc.
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {action && !item.completed && (
                        <Button size="sm" variant="outline" asChild>
                          <Link href={action.href} onClick={() => onOpenChange(false)}>
                            {action.label}
                            <ExternalLink className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                      )}
                      {item.key !== "configure_services" && (
                        <Button
                          size="sm"
                          variant={item.completed ? "ghost" : "secondary"}
                          onClick={() => markChecklist(item.key, !item.completed)}
                        >
                          {item.completed ? "Desmarcar" : "Marcar hecho"}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </TabsContent>

            <TabsContent value="security" className="mt-4 space-y-4">
              <div className="rounded-lg border bg-muted/20 p-4">
                <div className="flex items-start gap-3">
                  <Shield className="mt-0.5 h-5 w-5 text-primary" />
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Revisión de credenciales</p>
                    <p className="text-xs text-muted-foreground">
                      Confirme que ha revisado las contraseñas generadas en la instalación (Redis, MySQL,
                      Grafana, Supabase, etc.) y las ha guardado de forma segura.
                    </p>
                    {secretsPending > 0 && (
                      <p className="text-xs text-amber-700 dark:text-amber-300">
                        {secretsPending} credencial(es) pendiente(s) de confirmar
                      </p>
                    )}
                    <Button size="sm" onClick={handleConfirmSecrets}>
                      Confirmar revisión completada
                    </Button>
                  </div>
                </div>
              </div>

              <ul className="space-y-1.5 text-xs text-muted-foreground">
                {overview?.secrets_rotation.items.map((s) => (
                  <li key={s.key} className="flex items-center gap-2">
                    {s.rotated ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    ) : (
                      <Circle className="h-3.5 w-3.5" />
                    )}
                    {s.label}
                  </li>
                ))}
              </ul>
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
