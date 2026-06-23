"use client";

import { useState } from "react";
import { LayoutGrid } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { useI18n } from "@/providers/i18n-provider";
import { useSidebarNav } from "@/providers/sidebar-nav-provider";
import { cn } from "@/lib/utils";

interface SidebarMenuManagerProps {
  collapsed?: boolean;
}

export function SidebarMenuManager({ collapsed = false }: SidebarMenuManagerProps) {
  const { t } = useI18n();
  const { availableNav, isVisible, setItemVisible, savingId } = useSidebarNav();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "group flex w-full items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium text-sidebar-foreground/70 transition-all hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
          collapsed && "justify-center px-2"
        )}
        title={t("sidebar.manageMenu")}
      >
        <LayoutGrid className="h-4 w-4 shrink-0" />
        {!collapsed && <span className="flex-1 text-left">{t("sidebar.manageMenu")}</span>}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md gap-0 overflow-hidden p-0 sm:rounded-xl">
          <DialogHeader className="space-y-1 border-b px-5 py-4 text-left">
            <DialogTitle>{t("sidebar.manageMenuTitle")}</DialogTitle>
            <DialogDescription>{t("sidebar.manageMenuHint")}</DialogDescription>
          </DialogHeader>

          <div className="max-h-[min(60vh,520px)] overflow-y-auto">
            <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-b bg-muted/40 px-5 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <span>{t("sidebar.menuColumn")}</span>
              <span>{t("sidebar.displayColumn")}</span>
            </div>

            {availableNav.map((item) => {
              const Icon = item.icon;
              const visible = isVisible(item.id);

              return (
                <div
                  key={item.id}
                  className="grid grid-cols-[1fr_auto] items-center gap-3 border-b px-5 py-3 last:border-b-0"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm font-medium">{t(item.titleKey)}</span>
                  </div>

                  {item.locked ? (
                    <span className="min-w-[72px] text-right text-xs text-muted-foreground">
                      {t("sidebar.lockedItem")}
                    </span>
                  ) : (
                    <Switch
                      checked={visible}
                      disabled={savingId === item.id}
                      onCheckedChange={(checked) => void setItemVisible(item.id, checked)}
                      aria-label={t(item.titleKey)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
