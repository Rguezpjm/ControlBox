"use client";

import { cn } from "@/lib/utils";

export interface UptimeTimelinePoint {
  timestamp: string;
  status: string;
  reason?: string | null;
  latency_ms?: number | null;
  http_status?: number | null;
}

const REASON_LABELS: Record<string, string> = {
  server: "Servidor / contenedor",
  cloudflare: "Cloudflare / CDN",
  domain_expired: "Dominio o SSL vencido",
  ssl: "Certificado SSL inválido",
  dns: "DNS no resuelve",
};

interface UptimeBarProps {
  timeline: UptimeTimelinePoint[];
  uptimePercent?: number;
  className?: string;
}

export function formatDownReason(reason: string | null | undefined): string | null {
  if (!reason) return null;
  return REASON_LABELS[reason] ?? reason;
}

export function UptimeBar({ timeline, uptimePercent, className }: UptimeBarProps) {
  const bars = timeline.length > 0 ? timeline : [];
  const pct = uptimePercent ?? (bars.length
    ? Math.round((bars.filter((b) => b.status === "up").length / bars.length) * 1000) / 10
    : 100);

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Uptime 24h</span>
        <span className="font-medium tabular-nums text-foreground">{pct.toFixed(1)}%</span>
      </div>
      <div
        className="flex h-7 gap-px overflow-hidden rounded-md bg-muted/40 p-0.5"
        role="img"
        aria-label={`Uptime ${pct.toFixed(1)} percent over 24 hours`}
      >
        {bars.length === 0 ? (
          <div className="flex-1 rounded-sm bg-emerald-500/70" title="Sin datos aún" />
        ) : (
          bars.map((point, index) => {
            const up = point.status === "up";
            const label = up
              ? `Up · ${new Date(point.timestamp).toLocaleString()}`
              : `Down · ${formatDownReason(point.reason) ?? "Error"} · ${new Date(point.timestamp).toLocaleString()}`;
            return (
              <div
                key={`${point.timestamp}-${index}`}
                title={label}
                className={cn(
                  "min-w-[2px] flex-1 rounded-[1px] transition-colors",
                  up ? "bg-emerald-500 hover:bg-emerald-400" : "bg-red-500 hover:bg-red-400"
                )}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
