"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ControlBoxLogo } from "@/components/layout/controlbox-logo";
import { SidebarMenuManager } from "@/components/layout/sidebar-menu-manager";
import { useI18n } from "@/providers/i18n-provider";
import { useSidebarNav } from "@/providers/sidebar-nav-provider";
import { websitesApi } from "@/lib/websites";
import { wordpressApi } from "@/lib/wordpress";

interface SidebarProps {
  collapsed?: boolean;
}

function countRunningSites(sites: { status: string }[]) {
  return sites.filter((s) => s.status === "running").length;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const pathname = usePathname();
  const { t } = useI18n();
  const { visibleNav } = useSidebarNav();
  const [websiteCount, setWebsiteCount] = useState<number | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [websites, wpSites] = await Promise.all([
          websitesApi.list(),
          wordpressApi.list().catch(() => []),
        ]);
        setWebsiteCount(countRunningSites(websites) + countRunningSites(wpSites));
      } catch {
        setWebsiteCount(null);
      }
    }
    void load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [pathname]);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-sidebar-border bg-[#fbfcfe] dark:bg-sidebar transition-all duration-300",
        collapsed ? "w-16" : "w-[220px]"
      )}
    >
      <div className={cn("border-b border-sidebar-border px-3 py-3", collapsed && "flex justify-center px-2")}>
        <ControlBoxLogo href="/" size={collapsed ? 32 : 40} />
      </div>

      <ScrollArea className="flex-1 py-3">
        <nav className="flex flex-col gap-0.5 px-2">
          {visibleNav.map((item) => {
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
                key={item.id}
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

        <div className="mt-2 px-2">
          <SidebarMenuManager collapsed={collapsed} />
        </div>
      </ScrollArea>

      {!collapsed && (
        <div className="border-t border-sidebar-border p-3">
          <div className="rounded-md border border-border/60 bg-white/70 p-3 dark:bg-sidebar-accent/30">
            <div className="flex items-center gap-2">
              <ControlBoxLogo size={32} />
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
