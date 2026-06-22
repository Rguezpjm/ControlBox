"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getWebSocketClient } from "@/lib/websocket";
import type { RealtimeEvent } from "@/types";

interface RealtimeContextValue {
  connected: boolean;
  lastEvent: RealtimeEvent | null;
  events: RealtimeEvent[];
  subscribe: (handler: (event: RealtimeEvent) => void) => () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [handlers] = useState(() => new Set<(event: RealtimeEvent) => void>());

  useEffect(() => {
    const client = getWebSocketClient();

    const unsubConnection = client.onConnectionChange(setConnected);
    const unsubEvents = client.subscribe((event) => {
      setLastEvent(event);
      setEvents((prev) => [event, ...prev].slice(0, 100));
      handlers.forEach((handler) => handler(event));
    });

    client.connect();

    return () => {
      unsubConnection();
      unsubEvents();
      client.disconnect();
    };
  }, [handlers]);

  const subscribe = useCallback((handler: (event: RealtimeEvent) => void) => {
    handlers.add(handler);
    return () => handlers.delete(handler);
  }, [handlers]);

  return (
    <RealtimeContext.Provider value={{ connected, lastEvent, events, subscribe }}>
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtimeContext() {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error("useRealtimeContext must be used within RealtimeProvider");
  }
  return context;
}
