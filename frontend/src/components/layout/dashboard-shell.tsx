"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { SysadminTopbar } from "@/components/layout/sysadmin-topbar";
import { SidebarNavProvider } from "@/providers/sidebar-nav-provider";
import { ensureCsrfToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface DashboardShellProps {
  children: React.ReactNode;
  banner?: React.ReactNode;
}

export function DashboardShell({ children, banner }: DashboardShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    void ensureCsrfToken(true);
  }, []);

  return (
    <SidebarNavProvider>
      <div className="flex h-screen flex-col overflow-hidden bg-background">
        <SysadminTopbar onMenuClick={() => setMobileOpen(true)} />

        <div className="flex flex-1 overflow-hidden">
          <div className="hidden lg:flex">
            <Sidebar />
          </div>

          {mobileOpen && (
            <div className="fixed inset-0 z-50 lg:hidden">
              <div
                className="absolute inset-0 bg-background/80 backdrop-blur-sm"
                onClick={() => setMobileOpen(false)}
              />
              <div className="absolute left-0 top-11 h-[calc(100%-2.75rem)]">
                <Sidebar />
              </div>
            </div>
          )}

          <main className={cn("flex-1 overflow-y-auto bg-[#f4f6f9] dark:bg-background")}>
            <div className="mx-auto max-w-[1400px] p-4 lg:p-6">
              {banner}
              {children}
            </div>
          </main>
        </div>
      </div>
    </SidebarNavProvider>
  );
}
