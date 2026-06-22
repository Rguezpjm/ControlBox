"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  Cpu,
  HardDrive,
  MemoryStick,
  Shield,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { acknowledgeAlert, listResourceAlerts, type ResourceAlert } from "@/lib/platform";
import { useRealtimeContext } from "@/providers/realtime-provider";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const METRIC_META: Record<string, { label: string; icon: typeof Cpu; color: string }> = {
  cpu: { label: "CPU", icon: Cpu, color: "text-sky-500" },
  memory: { label: "RAM", icon: MemoryStick, color: "text-violet-500" },
  disk: { label: "Disco", icon: HardDrive, color: "text-amber-500" },
};

function severityStyles(severity: string) {
  if (severity === "critical") {
    return {
      badge: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
      ring: "ring-red-500/20",
    };
  }
  return {
    badge: "bg-amber-500/15 text-amber-800 dark:text-amber-200 border-amber-500/30",
    ring: "ring-amber-500/20",
  };
}

function AlertItem({
  alert,
  onAck,
}: {
  alert: ResourceAlert;
  onAck: (id: string) => void;
}) {
  const meta = METRIC_META[alert.metric] ?? {
    label: alert.metric.toUpperCase(),
    icon: Activity,
    color: "text-muted-foreground",
  };
  const Icon = meta.icon;
  const styles = severityStyles(alert.severity);
  const pct = Math.min(100, Math.max(0, alert.current_value));

  return (
    <div
      className={cn(
        "rounded-lg border bg-background/80 p-3 shadow-sm ring-1",
        styles.ring
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className={cn("mt-0.5 rounded-md bg-muted/60 p-1.5", meta.color)}>
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold">{meta.label}</span>
            <Badge variant="outline" className={cn("h-5 px-1.5 text-[10px] uppercase", styles.badge)}>
              {alert.severity === "critical" ? "Crítico" : "Aviso"}
            </Badge>
          </div>
          <p className="text-xs leading-relaxed text-foreground/90">{alert.message}</p>
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>Uso actual</span>
              <span>
                {alert.current_value.toFixed(1)}% / umbral {alert.threshold_value.toFixed(0)}%
              </span>
            </div>
            <Progress value={pct} className="h-1.5" />
          </div>
          <Button
            size="sm"
            variant="secondary"
            className="h-7 w-full text-xs"
            onClick={() => onAck(alert.id)}
          >
            Reconocer alerta
          </Button>
        </div>
      </div>
    </div>
  );
}

export function AlertBell() {
  const [alerts, setAlerts] = useState<ResourceAlert[]>([]);
  const [open, setOpen] = useState(false);
  const { subscribe } = useRealtimeContext();

  const load = useCallback(async () => {
    try {
      const data = await listResourceAlerts(true);
      setAlerts(data);
    } catch {
      setAlerts([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    return subscribe((event) => {
      if (event.type !== "alert") return;
      const payload = event.payload as {
        id?: string;
        message?: string;
        metric?: string;
        severity?: string;
        current_value?: number;
        threshold_value?: number;
      };
      if (!payload.id || !payload.message) return;
      setAlerts((prev) =>
        [
          {
            id: payload.id!,
            metric: payload.metric || "resource",
            severity: payload.severity || "warning",
            message: payload.message!,
            current_value: payload.current_value || 0,
            threshold_value: payload.threshold_value || 0,
            is_acknowledged: false,
            created_at: event.timestamp,
          },
          ...prev.filter((a) => a.id !== payload.id),
        ].slice(0, 20)
      );
      toast.warning(payload.message, {
        description: payload.severity === "critical" ? "Alerta crítica" : "Alerta de recursos",
      });
    });
  }, [subscribe]);

  const handleAck = async (alertId: string) => {
    try {
      await acknowledgeAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
      toast.success("Alerta reconocida");
    } catch {
      toast.error("No se pudo reconocer la alerta");
    }
  };

  const count = alerts.length;
  const hasCritical = useMemo(() => alerts.some((a) => a.severity === "critical"), [alerts]);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "relative h-8 w-8",
            count > 0 && hasCritical && "text-red-600 dark:text-red-400"
          )}
        >
          <Bell className={cn("h-4 w-4", count > 0 && "animate-pulse")} />
          {count > 0 && (
            <span
              className={cn(
                "absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-0.5 text-[10px] font-bold text-white",
                hasCritical ? "bg-red-600" : "bg-amber-500"
              )}
            >
              {count > 9 ? "9+" : count}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-[340px] p-0" align="end">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            <div>
              <p className="text-sm font-semibold">Alertas de recursos</p>
              <p className="text-[10px] text-muted-foreground">
                {count === 0 ? "Todo en orden" : `${count} activa${count === 1 ? "" : "s"}`}
              </p>
            </div>
          </div>
          {count > 0 && (
            <Badge variant="secondary" className="text-[10px]">
              Monitor
            </Badge>
          )}
        </div>
        <ScrollArea className="max-h-[380px]">
          {alerts.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
              <div className="rounded-full bg-emerald-500/10 p-3">
                <Activity className="h-5 w-5 text-emerald-600" />
              </div>
              <p className="text-sm font-medium">Sin alertas activas</p>
              <p className="text-xs text-muted-foreground">
                Los umbrales se configuran en Ajustes → Monitor y alertas
              </p>
            </div>
          ) : (
            <div className="space-y-2 p-3">
              {alerts.map((alert) => (
                <AlertItem key={alert.id} alert={alert} onAck={handleAck} />
              ))}
            </div>
          )}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
