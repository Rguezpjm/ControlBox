import { cn } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

const statusConfig: Record<ResourceStatus, { label: string; className: string }> = {
  running: { label: "Running", className: "bg-success/15 text-success border-success/20" },
  stopped: { label: "Stopped", className: "bg-muted text-muted-foreground border-border" },
  pending: { label: "Pending", className: "bg-warning/15 text-warning border-warning/20" },
  error: { label: "Error", className: "bg-destructive/15 text-destructive border-destructive/20" },
  degraded: { label: "Degraded", className: "bg-warning/15 text-warning border-warning/20" },
};

interface StatusBadgeProps {
  status: ResourceStatus;
  showDot?: boolean;
}

export function StatusBadge({ status, showDot = true }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
      config.className
    )}>
      {showDot && (
        <span className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "running" && "bg-success animate-pulse",
          status === "pending" && "bg-warning",
          status === "error" && "bg-destructive",
          status === "stopped" && "bg-muted-foreground",
          status === "degraded" && "bg-warning"
        )} />
      )}
      {config.label}
    </span>
  );
}
