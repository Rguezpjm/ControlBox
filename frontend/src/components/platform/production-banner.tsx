"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Shield } from "lucide-react";
import { getPlatformOverview } from "@/lib/platform";
import { ProductionSetupDialog } from "@/components/platform/production-setup-dialog";
import { Button } from "@/components/ui/button";

export function ProductionBanner() {
  const [visible, setVisible] = useState(false);
  const [message, setMessage] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const overview = await getPlatformOverview();
      if (!overview.is_production_ready) {
        const pending = overview.setup_checklist.total_count - overview.setup_checklist.completed_count;
        setMessage(
          pending === 1
            ? "Queda 1 tarea pendiente en el checklist de producción"
            : `Quedan ${pending} tareas pendientes en el checklist de producción`
        );
        setVisible(true);
      } else {
        setVisible(false);
      }
    } catch {
      setVisible(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!visible) {
    return (
      <ProductionSetupDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onComplete={load}
      />
    );
  }

  return (
    <>
      <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
        <div className="flex-1">
          <p className="font-medium text-amber-900 dark:text-amber-100">Preparación para producción</p>
          <p className="text-amber-800/90 dark:text-amber-200/90">{message}</p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          className="shrink-0 gap-1.5 bg-background/80"
          onClick={() => setDialogOpen(true)}
        >
          <Shield className="h-3.5 w-3.5" />
          Completar configuración
        </Button>
        <button
          type="button"
          onClick={() => setVisible(false)}
          className="text-amber-700 hover:text-amber-900 dark:text-amber-300"
          aria-label="Cerrar"
        >
          <CheckCircle2 className="h-4 w-4 opacity-50" />
        </button>
      </div>

      <ProductionSetupDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onComplete={() => {
          load();
          if (dialogOpen) {
            getPlatformOverview().then((o) => {
              if (o.is_production_ready) setVisible(false);
            });
          }
        }}
      />
    </>
  );
}
