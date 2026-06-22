"use client";

import { cn } from "@/lib/utils";

interface PanelSettingRowProps {
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

export function PanelSettingRow({ label, hint, children, className }: PanelSettingRowProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-3 border-b border-border/60 py-4 last:border-b-0 lg:grid-cols-[minmax(140px,200px)_minmax(0,1fr)_minmax(200px,280px)] lg:items-center lg:gap-6",
        className
      )}
    >
      <p className="text-sm font-medium text-muted-foreground lg:text-right">{label}</p>
      <div className="min-w-0">{children}</div>
      {hint ? <p className="text-xs leading-relaxed text-muted-foreground lg:pl-0">{hint}</p> : <span className="hidden lg:block" />}
    </div>
  );
}

interface PanelSettingsCardProps {
  children: React.ReactNode;
  title?: string;
}

export function PanelSettingsCard({ children, title = "Panel Setting" }: PanelSettingsCardProps) {
  return (
    <div className="rounded-lg border bg-card shadow-sm">
      <div className="border-b px-5 py-3">
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      <div className="px-5 pb-2">{children}</div>
    </div>
  );
}
