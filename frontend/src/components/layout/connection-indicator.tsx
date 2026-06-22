"use client";

import { Wifi, WifiOff } from "lucide-react";
import { useRealtime } from "@/hooks/use-realtime";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ConnectionIndicatorProps {
  /** Compact icon-only mode for the sysadmin topbar (aaPanel style). */
  compact?: boolean;
}

export function ConnectionIndicator({ compact = false }: ConnectionIndicatorProps) {
  const { connected, lastEvent } = useRealtime();

  if (compact) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={cn(
                "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors",
                "text-foreground/70 hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
              )}
              aria-label={connected ? "Realtime connected" : "Realtime offline"}
            >
              <span className="relative flex h-2.5 w-2.5">
                {connected && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
                )}
                <span
                  className={cn(
                    "relative inline-flex h-2.5 w-2.5 rounded-full",
                    connected ? "bg-emerald-500" : "bg-muted-foreground/50"
                  )}
                />
              </span>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            {connected
              ? `Live${lastEvent ? ` · ${lastEvent.type}` : ""}`
              : "Reconnecting to realtime..."}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={cn(
            "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
            connected
              ? "bg-success/10 text-success"
              : "bg-muted text-muted-foreground"
          )}>
            {connected ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            <span className="hidden sm:inline">
              {connected ? "Live" : "Offline"}
            </span>
            {connected && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {connected
            ? `Realtime connected${lastEvent ? ` · Last: ${lastEvent.type}` : ""}`
            : "Reconnecting to realtime service..."}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
