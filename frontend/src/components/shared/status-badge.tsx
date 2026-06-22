import { cn } from "@/lib/utils";
import { mapResourceStatus } from "@/lib/resource-status";
import type { ResourceStatus } from "@/types";

const statusConfig: Record<ResourceStatus, { label: string; className: string }> = {
  running: { label: "Running", className: "bg-success/15 text-success border-success/20" },
  stopped: { label: "Stopped", className: "bg-muted text-muted-foreground border-border" },
  pending: { label: "Pending", className: "bg-warning/15 text-warning border-warning/20" },
  error: { label: "Error", className: "bg-destructive/15 text-destructive border-destructive/20" },
  degraded: { label: "Degraded", className: "bg-warning/15 text-warning border-warning/20" },
};

interface StatusBadgeProps {
  status: ResourceStatus | string;
  isUp?: boolean;
  showDot?: boolean;
}

export function StatusBadge({ status, isUp, showDot = true }: StatusBadgeProps) {
  const resolved = mapResourceStatus(status, { isUp });
  const config = statusConfig[resolved];

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
      config.className
    )}>
      {showDot && (
        <span className={cn(
          "h-1.5 w-1.5 rounded-full",
          resolved === "running" && "bg-success animate-pulse",
          resolved === "pending" && "bg-warning",
          resolved === "error" && "bg-destructive",
          resolved === "stopped" && "bg-muted-foreground",
          resolved === "degraded" && "bg-warning"
        )} />
      )}
      {config.label}
    </span>
  );
}
