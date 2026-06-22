"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { acknowledgeAlert, listResourceAlerts, type ResourceAlert } from "@/lib/platform";
import { useRealtimeContext } from "@/providers/realtime-provider";
import { toast } from "sonner";

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
      setAlerts((prev) => [
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
      ].slice(0, 20));
      toast.warning(payload.message);
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

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative h-8 w-8">
          <Bell className="h-4 w-4" />
          {count > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
              {count > 9 ? "9+" : count}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80" align="end">
        <DropdownMenuLabel>Alertas de recursos</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {alerts.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-muted-foreground">
            Sin alertas activas
          </div>
        ) : (
          alerts.map((alert) => (
            <DropdownMenuItem
              key={alert.id}
              className="flex flex-col items-start gap-1 py-2"
              onSelect={(e) => e.preventDefault()}
            >
              <span className="text-xs font-medium">{alert.message}</span>
              <span className="text-[10px] text-muted-foreground uppercase">{alert.severity}</span>
              <Button
                size="sm"
                variant="outline"
                className="mt-1 h-6 text-[10px]"
                onClick={() => handleAck(alert.id)}
              >
                Reconocer
              </Button>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
