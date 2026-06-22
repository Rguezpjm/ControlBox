"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { mainNav } from "@/config/navigation";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useI18n } from "@/providers/i18n-provider";
import { monitoringApi } from "@/lib/monitoring";

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const pathname = usePathname();
  const { t } = useI18n();
  const [websiteCount, setWebsiteCount] = useState<number | null>(null);

  useEffect(() => {
    monitoringApi
      .websites()
      .then((sites) => setWebsiteCount(sites.length))
      .catch(() => setWebsiteCount(null));
  }, []);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-sidebar-border bg-[#fbfcfe] dark:bg-sidebar transition-all duration-300",
        collapsed ? "w-16" : "w-[220px]"
      )}
    >
      <ScrollArea className="flex-1 py-3">
        <nav className="flex flex-col gap-0.5 px-2">
          {mainNav.map((item) => {
            const href = item.href;
            const isActive =
              pathname === href || (item.href !== "/" && pathname.startsWith(href));
            const Icon = item.icon;
            const badge =
              item.badgeKey === "websites" && websiteCount !== null && websiteCount > 0
                ? websiteCount
                : undefined;

            return (
              <Link
                key={item.href}
                href={href}
                className={cn(
                  "group flex items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium transition-all",
                  isActive
                    ? "bg-primary/10 text-primary shadow-sm"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                  collapsed && "justify-center px-2"
                )}
              >
                <Icon className={cn("h-4 w-4 shrink-0", isActive && "text-primary")} />
                {!collapsed && (
                  <>
                    <span className="flex-1">{t(item.titleKey)}</span>
                    {badge !== undefined && (
                      <Badge variant="secondary" className="h-5 min-w-5 justify-center px-1.5 text-[10px]">
                        {badge}
                      </Badge>
                    )}
                  </>
                )}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      {!collapsed && (
        <div className="border-t border-sidebar-border p-3">
          <div className="rounded-md border border-border/60 bg-white/70 p-3 dark:bg-sidebar-accent/30">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-[10px] font-bold text-primary-foreground">
                CB
              </div>
              <div>
                <p className="text-xs font-semibold text-sidebar-accent-foreground">ControlBox</p>
                <p className="text-[10px] text-muted-foreground">{t("topbar.serverManagement")}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
