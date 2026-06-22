"use client";

import { useRealtimeContext } from "@/providers/realtime-provider";
import type { RealtimeEvent } from "@/types";
import { useEffect, useState } from "react";

export function useRealtime() {
  return useRealtimeContext();
}

export function useRealtimeResource<T>(
  initialData: T,
  resource: string,
  updater: (data: T, event: RealtimeEvent) => T
) {
  const { subscribe, connected } = useRealtimeContext();
  const [data, setData] = useState<T>(initialData);

  useEffect(() => {
    return subscribe((event) => {
      if (event.resource === resource) {
        setData((prev) => updater(prev, event));
      }
    });
  }, [subscribe, resource, updater]);

  return { data, setData, connected };
}

export function useLiveMetrics(initialMetrics: Record<string, number>) {
  const { subscribe, connected, lastEvent } = useRealtimeContext();
  const [metrics, setMetrics] = useState(initialMetrics);

  useEffect(() => {
    setMetrics(initialMetrics);
  }, [initialMetrics.cpu, initialMetrics.memory, initialMetrics.disk, initialMetrics.uptime_seconds]);

  useEffect(() => {
    return subscribe((event) => {
      if (event.type !== "metric") return;

      if (event.resource === "monitoring") {
        const payload = event.payload as {
          host?: {
            cpu_percent?: number;
            memory_percent?: number;
            disk_percent?: number;
            uptime_seconds?: number;
          };
        };
        const host = payload?.host;
        if (!host) return;
        setMetrics((prev) => ({
          ...prev,
          cpu: host.cpu_percent ?? prev.cpu,
          memory: host.memory_percent ?? prev.memory,
          disk: host.disk_percent ?? prev.disk,
          uptime: host.uptime_seconds ?? prev.uptime,
        }));
        return;
      }

      if (typeof event.payload?.value === "number") {
        setMetrics((prev) => ({
          ...prev,
          [event.resource]: event.payload.value as number,
        }));
      }
    });
  }, [subscribe]);

  return { metrics, connected, lastEvent };
}
