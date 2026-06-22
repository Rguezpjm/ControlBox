import type { ResourceStatus } from "@/types";

const STATUS_MAP: Record<string, ResourceStatus> = {
  running: "running",
  active: "running",
  healthy: "running",
  up: "running",
  completed: "running",
  stopped: "stopped",
  suspended: "stopped",
  inactive: "stopped",
  pending: "pending",
  provisioning: "pending",
  maintenance: "pending",
  deleting: "pending",
  restoring: "pending",
  error: "error",
  failed: "error",
  unhealthy: "error",
  expired: "error",
  degraded: "degraded",
};

const VALID_STATUSES = new Set<ResourceStatus>([
  "running",
  "stopped",
  "pending",
  "error",
  "degraded",
]);

export function mapResourceStatus(
  status: string | ResourceStatus,
  options?: { isUp?: boolean }
): ResourceStatus {
  if (options?.isUp === false && (status === "running" || status === "active")) {
    return "degraded";
  }

  if (VALID_STATUSES.has(status as ResourceStatus)) {
    return status as ResourceStatus;
  }

  return STATUS_MAP[status] ?? "pending";
}
