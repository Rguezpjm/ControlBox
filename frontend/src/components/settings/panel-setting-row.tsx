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
        "grid grid-cols-1 gap-2 border-b border-border/50 py-4 last:border-b-0 sm:grid-cols-[minmax(120px,180px)_1fr] sm:items-start sm:gap-6",
        className
      )}
    >
      <div className="sm:pt-2">
        <p className="text-sm font-medium">{label}</p>
        {hint ? <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground sm:hidden">{hint}</p> : null}
      </div>
      <div className="min-w-0 space-y-1">
        {children}
        {hint ? <p className="hidden text-xs leading-relaxed text-muted-foreground sm:block">{hint}</p> : null}
      </div>
    </div>
  );
}

interface PanelSettingsCardProps {
  children: React.ReactNode;
  title?: string;
}

/** @deprecated Use SettingsSection instead */
export function PanelSettingsCard({ children, title = "Panel Setting" }: PanelSettingsCardProps) {
  return (
    <div className="rounded-xl border bg-card shadow-sm">
      <div className="border-b px-5 py-3">
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      <div className="px-5 pb-2">{children}</div>
    </div>
  );
}

interface SettingsSectionProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function SettingsSection({ icon, title, description, children, className }: SettingsSectionProps) {
  return (
    <section className={cn("overflow-hidden rounded-xl border bg-card shadow-sm", className)}>
      <header className="flex items-start gap-3 border-b bg-muted/20 px-5 py-4">
        {icon ? (
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {icon}
          </div>
        ) : null}
        <div className="min-w-0">
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
        </div>
      </header>
      <div className="px-5 pb-1">{children}</div>
    </section>
  );
}
