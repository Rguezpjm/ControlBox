"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Shield } from "lucide-react";
import { getPlatformOverview, type PlatformOverview } from "@/lib/platform";
import { ensureCsrfToken } from "@/lib/auth";
import { ProductionSetupDialog } from "@/components/platform/production-setup-dialog";
import { Button } from "@/components/ui/button";

function isConfigureServicesPending(overview: PlatformOverview | null): boolean {
  if (!overview) return false;
  const item = overview.setup_checklist.items.find((i) => i.key === "configure_services");
  return !item?.completed;
}

export function ProductionBanner() {
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      await ensureCsrfToken();
      const next = await getPlatformOverview();
      setOverview(next);
      if (isConfigureServicesPending(next)) {
        setDialogOpen(true);
      } else {
        setDialogOpen(false);
      }
    } catch {
      setOverview(null);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const needsInitialSetup = isConfigureServicesPending(overview);

  if (!loaded || !needsInitialSetup) {
    return null;
  }

  return (
    <>
      <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
        <div className="flex-1">
          <p className="font-medium text-amber-900 dark:text-amber-100">Preparación para producción</p>
          <p className="text-amber-800/90 dark:text-amber-200/90">
            Seleccione los servicios que desea instalar y activar en este servidor.
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          className="shrink-0 gap-1.5 bg-background/80"
          onClick={() => setDialogOpen(true)}
        >
          <Shield className="h-3.5 w-3.5" />
          Configurar servicios
        </Button>
      </div>

      <ProductionSetupDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onComplete={load}
      />
    </>
  );
}
