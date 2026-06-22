"use client";

import { useEffect, useState } from "react";
import { APP_BASE_PATH } from "@/lib/base-path";

export type ApiHealthStatus = "unknown" | "healthy" | "degraded" | "offline";

export interface ApiHealthSnapshot {
  status: ApiHealthStatus;
  postgres?: string;
  redis?: string;
}

const HEALTH_URL = `${APP_BASE_PATH}/health`;

export function useApiHealth(pollMs = 20_000) {
  const [health, setHealth] = useState<ApiHealthSnapshot>({ status: "unknown" });

  useEffect(() => {
    let active = true;

    async function poll() {
      try {
        const response = await fetch(HEALTH_URL, {
          credentials: "include",
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`health ${response.status}`);
        }
        const data = (await response.json()) as {
          status?: string;
          postgres?: string;
          redis?: string;
        };
        if (!active) return;
        setHealth({
          status: data.status === "healthy" ? "healthy" : "degraded",
          postgres: data.postgres,
          redis: data.redis,
        });
      } catch {
        if (active) {
          setHealth({ status: "offline" });
        }
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), pollMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [pollMs]);

  const isOperational = health.status === "healthy" || health.status === "degraded";

  return { health, isOperational, isHealthy: health.status === "healthy" };
}
