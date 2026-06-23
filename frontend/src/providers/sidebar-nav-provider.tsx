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
import { api } from "@/lib/api-client";
import { getPanelSettings, updatePanelSettings } from "@/lib/platform";

interface SidebarNavContextValue {
  availableNav: NavItem[];
  visibleNav: NavItem[];
  hiddenIds: Set<string>;
  loading: boolean;
  savingId: string | null;
  isVisible: (id: string) => boolean;
  setItemVisible: (id: string, visible: boolean) => Promise<void>;
}

const SidebarNavContext = createContext<SidebarNavContextValue | null>(null);

function isAllowedByPermissions(item: NavItem, permissions: Set<string> | null): boolean {
  if (!item.requiredPermissions?.length) return true;
  if (!permissions) return true;
  if (permissions.has("*")) return true;
  return item.requiredPermissions.some((code) => permissions.has(code));
}

export function SidebarNavProvider({ children }: { children: ReactNode }) {
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set());
  const [permissions, setPermissions] = useState<Set<string> | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      getPanelSettings().catch(() => ({ sidebar_hidden_items: [] as string[] })),
      api.auth.me().catch(() => ({ permissions: [] as string[] })),
    ])
      .then(([settings, me]) => {
        if (!active) return;
        setHiddenIds(new Set(settings.sidebar_hidden_items ?? []));
        setPermissions(new Set(Array.isArray((me as { permissions?: unknown }).permissions) ? ((me as { permissions: string[] }).permissions ?? []) : []));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const availableNav = useMemo(
    () => mainNav.filter((item) => isAllowedByPermissions(item, permissions)),
    [permissions]
  );

  const visibleNav = useMemo(
    () => availableNav.filter((item) => item.locked || !hiddenIds.has(item.id)),
    [availableNav, hiddenIds]
  );

  const isVisible = useCallback(
    (id: string) => {
      const item = availableNav.find((entry) => entry.id === id);
      if (!item) return false;
      if (item?.locked) return true;
      return !hiddenIds.has(id);
    },
    [availableNav, hiddenIds]
  );

  const setItemVisible = useCallback(
    async (id: string, visible: boolean) => {
      const item = availableNav.find((entry) => entry.id === id);
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
    [availableNav, hiddenIds]
  );

  const value = useMemo(
    () => ({
      availableNav,
      visibleNav,
      hiddenIds,
      loading,
      savingId,
      isVisible,
      setItemVisible,
    }),
    [availableNav, visibleNav, hiddenIds, loading, savingId, isVisible, setItemVisible]
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
