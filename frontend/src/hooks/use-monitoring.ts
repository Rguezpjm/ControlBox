"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRealtimeContext } from "@/providers/realtime-provider";
import {
  monitoringApi,
  type MonitoringHistory,
  type MonitoringOverview,
} from "@/lib/monitoring";

const MAX_POINTS = 60;

function appendPoint(history: { timestamp: string; value: number }[], value: number) {
  const next = [...history, { timestamp: new Date().toISOString(), value }];
  return next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next;
}

function historyFromOverview(overview: MonitoringOverview): MonitoringHistory {
  const ts = overview.collected_at || new Date().toISOString();
  const point = (value: number) => [{ timestamp: ts, value }];
  return {
    cpu: point(overview.host.cpu_percent),
    memory: point(overview.host.memory_percent),
    disk: point(overview.host.disk_percent),
    network_in: point(overview.host.network_in_mbps),
    network_out: point(overview.host.network_out_mbps),
  };
}

export function useMonitoring() {
  const { subscribe, connected } = useRealtimeContext();
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [history, setHistory] = useState<MonitoringHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const initialized = useRef(false);

  const applySnapshot = useCallback((data: MonitoringOverview) => {
    setOverview(data);
    setHistory((prev) => {
      if (!prev) return historyFromOverview(data);
      return {
        cpu: appendPoint(prev.cpu, data.host.cpu_percent),
        memory: appendPoint(prev.memory, data.host.memory_percent),
        disk: appendPoint(prev.disk, data.host.disk_percent),
        network_in: appendPoint(prev.network_in, data.host.network_in_mbps),
        network_out: appendPoint(prev.network_out, data.host.network_out_mbps),
      };
    });
  }, []);

  const load = useCallback(async () => {
    try {
      const [overviewData, historyData] = await Promise.all([
        monitoringApi.overview(),
        monitoringApi.history(60),
      ]);
      setOverview(overviewData);
      setHistory(historyData);
    } catch {
      setOverview(null);
      setHistory(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      load();
    }
  }, [load]);

  useEffect(() => {
    if (connected) return;
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [connected, load]);

  useEffect(() => {
    return subscribe((event) => {
      if (event.type !== "metric" || event.resource !== "monitoring") return;
      const payload = event.payload as unknown as MonitoringOverview;
      if (payload && typeof payload === "object" && "host" in payload) {
        applySnapshot(payload);
      }
    });
  }, [subscribe, applySnapshot]);

  return { overview, history, loading, connected, reload: load };
}
