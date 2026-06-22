"use client";

import { cn } from "@/lib/utils";

interface SslDaysCellProps {
  days: number | null | undefined;
  sslEnabled?: boolean;
  sslStatus?: string;
}

export function SslDaysCell({ days, sslEnabled, sslStatus }: SslDaysCellProps) {
  if (!sslEnabled) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  if (days === null || days === undefined) {
    if (sslStatus === "pending") {
      return <span className="text-xs text-amber-600">Pending</span>;
    }
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  const urgent = days < 14;
  return (
    <span
      className={cn(
        "text-xs font-medium tabular-nums",
        urgent ? "text-amber-600" : "text-emerald-600"
      )}
    >
      {days} Days
    </span>
  );
}
