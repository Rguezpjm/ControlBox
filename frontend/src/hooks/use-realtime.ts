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
    return subscribe((event) => {
      if (event.type === "metric" && typeof event.payload.value === "number") {
        setMetrics((prev) => ({
          ...prev,
          [event.resource]: event.payload.value as number,
        }));
      }
    });
  }, [subscribe]);

  return { metrics, connected, lastEvent };
}
