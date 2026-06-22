"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Gem,
  Languages,
  Loader2,
  Menu,
  Power,
  RefreshCw,
  Settings2,
  SquarePen,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AlertBell } from "@/components/platform/alert-bell";
import { ConnectionIndicator } from "@/components/layout/connection-indicator";
import { useSysadminBar } from "@/hooks/use-sysadmin-bar";
import { useI18n } from "@/providers/i18n-provider";
import { logoutApi } from "@/lib/auth";
import { platformOperations } from "@/lib/platform";
import { cn, getInitials, maskEmail } from "@/lib/utils";

interface SysadminTopbarProps {
  onMenuClick?: () => void;
}

function UbuntuMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="#E95420" />
      <circle cx="8.5" cy="10" r="1.6" fill="#fff" />
      <circle cx="15.5" cy="10" r="1.6" fill="#fff" />
      <circle cx="12" cy="15.5" r="1.6" fill="#fff" />
      <path
        d="M12 4.5c3.2 0 6 1.7 7.5 4.2M4.5 12c0-2.2 1-4.2 2.6-5.5M19.5 12c0 2.2-1 4.2-2.6 5.5"
        stroke="#fff"
        strokeWidth="1.2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TopbarDivider() {
  return <span className="mx-2 hidden h-4 w-px bg-border/80 sm:inline-block" aria-hidden="true" />;
}

function TopbarAction({
  label,
  icon: Icon,
  onClick,
  disabled,
  loading,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-foreground/80 transition-colors hover:bg-black/5 hover:text-foreground disabled:opacity-50 dark:hover:bg-white/10"
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      <span className="hidden md:inline">{label}</span>
    </button>
  );
}

export function SysadminTopbar({ onMenuClick }: SysadminTopbarProps) {
  const router = useRouter();
  const { setTheme, resolvedTheme } = useTheme();
  const { user, system, systemLoading } = useSysadminBar();
  const { t, toggleLocale, locale } = useI18n();
  const [busy, setBusy] = useState<"restart" | "fix" | "update" | null>(null);

  const version = system?.version?.trim() ?? "";
  const osLabel = system?.os_label ?? "Linux";
  const edition = system?.edition ?? "PRO";
  const displayEmail = user?.email ? maskEmail(user.email) : "admin";

  async function handleLogout() {
    await logoutApi();
    router.push("/login");
    router.refresh();
  }

  function handleLanguageToggle() {
    toggleLocale();
    toast.success(locale === "en" ? "Idioma cambiado a Español" : "Language changed to English");
  }

  async function handleRestart() {
    setBusy("restart");
    const toastId = toast.loading(t("ops.restarting"));
    try {
      const result = await platformOperations.restartPanel();
      if (result.success) {
        toast.success(t("ops.restartOk"), { id: toastId, description: result.message });
      } else {
        toast.error(t("ops.restartFail"), { id: toastId, description: result.detail ?? result.message });
      }
    } catch {
      toast.error(t("ops.restartFail"), { id: toastId });
    } finally {
      setBusy(null);
    }
  }

  async function handleFix() {
    setBusy("fix");
    const toastId = toast.loading(t("ops.fixing"));
    try {
      const result = await platformOperations.fixStack();
      if (result.success) {
        toast.success(t("ops.fixOk"), { id: toastId, description: result.message });
      } else {
        toast.error(t("ops.fixFail"), { id: toastId, description: result.detail ?? result.message });
      }
    } catch {
      toast.error(t("ops.fixFail"), { id: toastId });
    } finally {
      setBusy(null);
    }
  }

  async function handleUpdate() {
    setBusy("update");
    const checkToast = toast.loading(t("ops.checkingUpdate"));
    try {
      const check = await platformOperations.checkUpdate();
      if (!check.latest_version) {
        toast.error(t("ops.noReleaseFound"), { id: checkToast });
        return;
      }

      const compareDesc = t("ops.versionCompare", {
        current: check.current_version,
        latest: check.latest_version,
      });

      if (!check.update_available) {
        toast.success(t("ops.upToDate"), {
          id: checkToast,
          description: compareDesc,
        });
        return;
      }

      toast.loading(t("ops.updateAvailable", { version: check.latest_version }), {
        id: checkToast,
        description: compareDesc,
      });
      const result = await platformOperations.applyUpdate();
      if (result.success) {
        toast.success(t("ops.updateOk"), {
          id: checkToast,
          description: result.message,
        });
      } else {
        toast.error(t("ops.updateFail"), {
          id: checkToast,
          description: result.detail ?? result.message,
        });
      }
    } catch {
      toast.error(t("ops.updateCheckFail"), { id: checkToast });
    } finally {
      setBusy(null);
    }
  }

  return (
    <header className="sysadmin-topbar relative z-50 shrink-0 border-b border-border/70">
      <div className="flex h-11 items-center justify-between px-3 lg:px-4">
        <div className="flex min-w-0 items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 lg:hidden"
            onClick={onMenuClick}
          >
            <Menu className="h-4 w-4" />
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex min-w-0 items-center gap-2 rounded-md px-1.5 py-1 transition-colors hover:bg-black/5 dark:hover:bg-white/10"
              >
                <Avatar className="h-7 w-7 border border-border/60">
                  <AvatarFallback className="bg-slate-700 text-[10px] font-semibold text-white">
                    {getInitials(user?.full_name || "Admin")}
                  </AvatarFallback>
                </Avatar>
                <span className="truncate text-sm font-medium text-foreground/90">{displayEmail}</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuLabel>
                <div className="space-y-1">
                  <p className="text-sm font-medium">{user?.full_name || t("topbar.administrator")}</p>
                  <p className="text-xs text-muted-foreground">{user?.email || ""}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => router.push("/settings")}>
                {t("topbar.settings")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive" onClick={() => void handleLogout()}>
                {t("topbar.signOut")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <TopbarDivider />

          <div className="hidden items-center gap-2 sm:flex">
            <UbuntuMark className="h-5 w-5 shrink-0" />
            <span className="text-sm font-medium text-foreground/85">{osLabel}</span>
          </div>

          <span
            className={cn(
              "ml-1 hidden items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wide text-white sm:inline-flex",
              "bg-[#4f5864] shadow-sm"
            )}
          >
            <Gem className="h-3 w-3" />
            {edition}
          </span>
        </div>

        <div className="flex items-center gap-0.5">
          <div className="hidden items-center gap-0.5 sm:flex">
            <Link
              href="/settings"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-foreground/70 transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
              title={t("topbar.settings")}
            >
              <SquarePen className="h-4 w-4" />
            </Link>
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-foreground/70 transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
              title={t("topbar.language")}
              onClick={handleLanguageToggle}
            >
              <Languages className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-foreground/70 transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
              title={t("topbar.theme")}
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            >
              <Sun className="h-4 w-4" />
            </button>
          </div>

          <TopbarDivider />

          {(systemLoading || version) && (
            <span
              className="hidden px-2 text-xs font-semibold tabular-nums text-foreground/70 sm:inline"
              title="ControlBox version"
            >
              {systemLoading ? "…" : version}
            </span>
          )}

          <TopbarDivider />

          <div className="hidden items-center lg:flex">
            <TopbarAction
              label={t("topbar.update")}
              icon={RefreshCw}
              onClick={() => void handleUpdate()}
              loading={busy === "update"}
              disabled={busy !== null && busy !== "update"}
            />
            <TopbarAction
              label={t("topbar.fix")}
              icon={Settings2}
              onClick={() => void handleFix()}
              loading={busy === "fix"}
              disabled={busy !== null && busy !== "fix"}
            />
            <TopbarAction
              label={t("topbar.restart")}
              icon={Power}
              onClick={() => void handleRestart()}
              loading={busy === "restart"}
              disabled={busy !== null && busy !== "restart"}
            />
          </div>

          <div className="ml-1 flex items-center">
            <ConnectionIndicator compact />
            <AlertBell />
          </div>
        </div>
      </div>
    </header>
  );
}

