"use client";

import { useEffect, useState } from "react";
import { monitoringApi, type MonitoringHistory, type MonitoringOverview } from "@/lib/monitoring";

export interface DashboardData {
  overview: MonitoringOverview;
  history: MonitoringHistory;
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [overview, history] = await Promise.all([
          monitoringApi.overview(),
          monitoringApi.history(60),
        ]);
        if (!active) return;
        setData({ overview, history });
      } catch {
        if (active) setError("load_failed");
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    const timer = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return { data, error, loading };
}
