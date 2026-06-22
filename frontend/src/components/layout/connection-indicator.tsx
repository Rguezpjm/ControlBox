"use client";

import { Wifi, WifiOff } from "lucide-react";
import { useApiHealth } from "@/hooks/use-api-health";
import { useRealtime } from "@/hooks/use-realtime";
import { useI18n } from "@/providers/i18n-provider";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ConnectionIndicatorProps {
  /** Compact icon-only mode for the sysadmin topbar. */
  compact?: boolean;
}

export function ConnectionIndicator({ compact = false }: ConnectionIndicatorProps) {
  const { t } = useI18n();
  const { connected: wsConnected, lastEvent } = useRealtime();
  const { health, isOperational } = useApiHealth();

  const status: "healthy" | "degraded" | "checking" | "offline" =
    health.status === "healthy"
      ? "healthy"
      : health.status === "degraded"
        ? "degraded"
        : health.status === "offline"
          ? "offline"
          : "checking";

  const showGreen = status === "healthy";
  const showAmber = status === "degraded";

  function tooltipText() {
    if (status === "checking") return t("conn.checking");
    if (status === "offline") return t("conn.offline");
    if (status === "degraded") {
      return t("conn.degraded", {
        postgres: health.postgres ?? "?",
        redis: health.redis ?? "?",
      });
    }
    if (wsConnected) {
      return lastEvent
        ? t("conn.liveWithEvent", { type: lastEvent.type })
        : t("conn.live");
    }
    return t("conn.operational");
  }

  if (compact) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={cn(
                "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors",
                showGreen
                  ? "text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400"
                  : showAmber
                    ? "text-amber-600 hover:bg-amber-500/10 dark:text-amber-400"
                    : "text-foreground/70 hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
              )}
              aria-label={
                showGreen
                  ? t("conn.ariaHealthy")
                  : showAmber
                    ? t("conn.ariaDegraded")
                    : t("conn.ariaOffline")
              }
            >
              <span className="relative flex h-2.5 w-2.5">
                {showGreen && wsConnected && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
                )}
                <span
                  className={cn(
                    "relative inline-flex h-2.5 w-2.5 rounded-full",
                    showGreen
                      ? "bg-emerald-500"
                      : showAmber
                        ? "bg-amber-500"
                        : status === "checking"
                          ? "bg-muted-foreground/40"
                          : "bg-red-500"
                  )}
                />
              </span>
            </div>
          </TooltipTrigger>
          <TooltipContent>{tooltipText()}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
              showGreen
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                : showAmber
                  ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                  : isOperational
                    ? "bg-muted text-muted-foreground"
                    : "bg-red-500/10 text-red-700 dark:text-red-400"
            )}
          >
            {showGreen || isOperational ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            <span className="hidden sm:inline">
              {showGreen ? t("conn.badgeLive") : showAmber ? t("conn.badgeDegraded") : t("conn.badgeOffline")}
            </span>
            {showGreen && (
              <span className="relative flex h-2 w-2">
                {wsConnected && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                )}
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>{tooltipText()}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
