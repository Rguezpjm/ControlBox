"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";
import { mainNav, type NavItem } from "@/config/navigation";
import { getPanelSettings, updatePanelSettings } from "@/lib/platform";

interface SidebarNavContextValue {
  visibleNav: NavItem[];
  hiddenIds: Set<string>;
  loading: boolean;
  savingId: string | null;
  isVisible: (id: string) => boolean;
  setItemVisible: (id: string, visible: boolean) => Promise<void>;
}

const SidebarNavContext = createContext<SidebarNavContextValue | null>(null);

export function SidebarNavProvider({ children }: { children: ReactNode }) {
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getPanelSettings()
      .then((settings) => {
        if (!active) return;
        setHiddenIds(new Set(settings.sidebar_hidden_items ?? []));
      })
      .catch(() => {
        if (!active) return;
        setHiddenIds(new Set());
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const visibleNav = useMemo(
    () => mainNav.filter((item) => item.locked || !hiddenIds.has(item.id)),
    [hiddenIds]
  );

  const isVisible = useCallback(
    (id: string) => {
      const item = mainNav.find((entry) => entry.id === id);
      if (item?.locked) return true;
      return !hiddenIds.has(id);
    },
    [hiddenIds]
  );

  const setItemVisible = useCallback(
    async (id: string, visible: boolean) => {
      const item = mainNav.find((entry) => entry.id === id);
      if (!item || item.locked) return;

      const previous = new Set(hiddenIds);
      const next = new Set(hiddenIds);
      if (visible) {
        next.delete(id);
      } else {
        next.add(id);
      }

      setHiddenIds(next);
      setSavingId(id);

      try {
        await updatePanelSettings({ sidebar_hidden_items: Array.from(next) });
      } catch {
        setHiddenIds(previous);
        toast.error("Could not save sidebar preferences");
      } finally {
        setSavingId(null);
      }
    },
    [hiddenIds]
  );

  const value = useMemo(
    () => ({
      visibleNav,
      hiddenIds,
      loading,
      savingId,
      isVisible,
      setItemVisible,
    }),
    [visibleNav, hiddenIds, loading, savingId, isVisible, setItemVisible]
  );

  return <SidebarNavContext.Provider value={value}>{children}</SidebarNavContext.Provider>;
}

export function useSidebarNav() {
  const context = useContext(SidebarNavContext);
  if (!context) {
    throw new Error("useSidebarNav must be used within SidebarNavProvider");
  }
  return context;
}
