"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  ExternalLink,
  FolderOpen,
  Globe,
  Loader2,
  Palette,
  Power,
  Send,
  Server,
  Settings2,
} from "lucide-react";
import { useTheme } from "next-themes";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageSkeleton } from "@/components/skeletons";
import {
  PanelSettingRow,
  PanelSettingsCard,
  SettingsSection,
} from "@/components/settings/panel-setting-row";
import {
  getPanelSettings,
  shutdownPanelService,
  syncPanelServerTime,
  testTelegramAlerts,
  updatePanelSettings,
  type PanelSettings,
} from "@/lib/platform";
import { useI18n } from "@/providers/i18n-provider";
import { toast } from "sonner";

function SaveButton({
  onClick,
  saving,
  label = "Guardar",
}: {
  onClick: () => void;
  saving: boolean;
  label?: string;
}) {
  return (
    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={onClick} disabled={saving}>
      {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
      {label}
    </Button>
  );
}

function normalizePanelPath(path: string) {
  const trimmed = path.trim();
  if (!trimmed || trimmed === "/") return "/";
  return trimmed.startsWith("/") ? trimmed.replace(/\/+$/, "") || "/" : `/${trimmed.replace(/\/+$/, "")}`;
}

function SettingsContent() {
  const { locale, setLocale } = useI18n();
  const { theme, setTheme } = useTheme();
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [data, setData] = useState<PanelSettings | null>(null);

  const [alias, setAlias] = useState("");
  const [timeoutHours, setTimeoutHours] = useState("24");
  const [siteFolder, setSiteFolder] = useState("");
  const [backupFolder, setBackupFolder] = useState("");
  const [serverIp, setServerIp] = useState("");
  const [serverTime, setServerTime] = useState("");
  const [panelPort, setPanelPort] = useState("");
  const [panelPath, setPanelPath] = useState("");
  const [cpuThreshold, setCpuThreshold] = useState("90");
  const [ramThreshold, setRamThreshold] = useState("90");
  const [diskThreshold, setDiskThreshold] = useState("90");
  const [alertCooldown, setAlertCooldown] = useState("15");
  const [backupRetention, setBackupRetention] = useState("30");
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");

  const syncForm = useCallback((settings: PanelSettings) => {
    setData(settings);
    setAlias(settings.panel_alias);
    setTimeoutHours(String(settings.session_timeout_hours));
    setSiteFolder(settings.default_site_folder);
    setBackupFolder(settings.default_backup_folder);
    setServerIp(settings.server_ip);
    setServerTime(settings.server_time.display);
    setPanelPort(String(settings.panel_port));
    setPanelPath(settings.panel_base_path);
    setCpuThreshold(String(settings.cpu_threshold_percent));
    setRamThreshold(String(settings.memory_threshold_percent));
    setDiskThreshold(String(settings.disk_threshold_percent));
    setAlertCooldown(String(settings.alert_cooldown_minutes));
    setBackupRetention(String(settings.auto_backup_retention));
    setTelegramEnabled(settings.telegram_alerts_enabled);
    setTelegramChatId(settings.telegram_chat_id);
    setTelegramBotToken("");
  }, []);

  const load = useCallback(async () => {
    try {
      const settings = await getPanelSettings();
      syncForm(settings);
      setForbidden(false);
    } catch {
      setForbidden(true);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [syncForm]);

  useEffect(() => {
    load();
  }, [load]);

  const panelPreviewUrl = useMemo(() => {
    const ip = serverIp || "IP";
    const port = panelPort || "8443";
    const path = normalizePanelPath(panelPath);
    const suffix = path === "/" ? "" : path;
    return `http://${ip}:${port}${suffix}`;
  }, [serverIp, panelPort, panelPath]);

  async function patch(
    key: string,
    payload: Parameters<typeof updatePanelSettings>[0],
    successMsg: string
  ) {
    setSavingKey(key);
    try {
      const updated = await updatePanelSettings(payload);
      syncForm(updated);
      toast.success(successMsg);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSavingKey(null);
    }
  }

  async function toggle(
    key: keyof PanelSettings,
    value: boolean,
    field: Parameters<typeof updatePanelSettings>[0]
  ) {
    setSavingKey(String(key));
    try {
      const updated = await updatePanelSettings(field);
      syncForm(updated);
    } catch {
      toast.error("Error al actualizar");
      await load();
    } finally {
      setSavingKey(null);
    }
  }

  if (loading) return <PageSkeleton />;

  if (forbidden) {
    return (
      <div className="space-y-6">
        <PageHeader title="Ajustes" description="Configuración del panel ControlBox" />
        <PanelSettingsCard title="Apariencia">
          <PanelSettingRow label="Tema" hint="Tema claro u oscuro del panel">
            <Select value={theme || "system"} onValueChange={setTheme}>
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">Fresh (Light)</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
                <SelectItem value="system">System</SelectItem>
              </SelectContent>
            </Select>
          </PanelSettingRow>
          <PanelSettingRow label="Idioma" hint="Idioma de la interfaz del panel">
            <Select value={locale} onValueChange={(v) => setLocale(v as "en" | "es")}>
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Español</SelectItem>
              </SelectContent>
            </Select>
          </PanelSettingRow>
          <p className="py-6 text-center text-sm text-muted-foreground">
            Inicie sesión como Owner o Administrator para ver todas las opciones del panel.
          </p>
        </PanelSettingsCard>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6 pb-8">
      <PageHeader
        title="Ajustes"
        description={`ControlBox ${data.controlbox_version} · ${data.os_label} · ${data.controlbox_profile}`}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <SettingsSection
          icon={<Settings2 className="h-4 w-4" />}
          title="Acceso al panel"
          description="Puerto y ruta de URL donde se publica el panel (ej. /ControlBox_Panel)"
        >
          <PanelSettingRow label="URL de acceso" hint="Vista previa con la IP y ruta configuradas">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2.5 font-mono text-xs">
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="break-all text-foreground">{panelPreviewUrl}</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-[120px_1fr]">
                <div className="space-y-1.5">
                  <Label className="text-xs">Puerto</Label>
                  <Input
                    type="number"
                    min={1024}
                    max={65535}
                    value={panelPort}
                    onChange={(e) => setPanelPort(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Ruta base</Label>
                  <Input
                    value={panelPath}
                    onChange={(e) => setPanelPath(e.target.value)}
                    placeholder="/ControlBox_Panel"
                    className="font-mono"
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SaveButton
                  saving={savingKey === "panelAccess"}
                  onClick={() =>
                    patch(
                      "panelAccess",
                      {
                        panel_port: Number(panelPort),
                        panel_base_path: normalizePanelPath(panelPath),
                      },
                      "Acceso al panel guardado"
                    )
                  }
                />
                {!data.can_apply_host_changes && (
                  <Badge variant="outline" className="text-[10px] text-amber-700">
                    Requiere repair en el host
                  </Badge>
                )}
              </div>
            </div>
          </PanelSettingRow>

          <PanelSettingRow label="Alias" hint="Nombre visible del servidor en el panel">
            <div className="flex flex-wrap items-center gap-2">
              <Input value={alias} onChange={(e) => setAlias(e.target.value)} className="max-w-md flex-1" />
              <SaveButton
                saving={savingKey === "alias"}
                onClick={() => patch("alias", { panel_alias: alias }, "Alias guardado")}
              />
            </div>
          </PanelSettingRow>

          <PanelSettingRow
            label="Timeout de sesión"
            hint="Cierra la sesión tras este tiempo sin actividad"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Input
                type="number"
                min={1}
                max={168}
                value={timeoutHours}
                onChange={(e) => setTimeoutHours(e.target.value)}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">horas</span>
              <SaveButton
                label="Aplicar"
                saving={savingKey === "timeout"}
                onClick={() =>
                  patch("timeout", { session_timeout_hours: Number(timeoutHours) }, "Timeout actualizado")
                }
              />
            </div>
          </PanelSettingRow>
        </SettingsSection>

        <SettingsSection
          icon={<Server className="h-4 w-4" />}
          title="Servidor"
          description="IP, hora y rutas por defecto del host"
        >
          <PanelSettingRow label="IP del servidor" hint="IP mostrada y usada en enlaces del panel">
            <div className="flex flex-wrap items-center gap-2">
              <Input value={serverIp} onChange={(e) => setServerIp(e.target.value)} className="max-w-xs flex-1" />
              <SaveButton
                saving={savingKey === "serverIp"}
                onClick={() => patch("serverIp", { server_ip: serverIp }, "IP guardada")}
              />
            </div>
          </PanelSettingRow>

          <PanelSettingRow label="Hora del servidor">
            <div className="flex flex-wrap items-center gap-2">
              <Input value={serverTime} readOnly className="flex-1 font-mono text-xs" />
              <SaveButton
                label="Sincronizar"
                saving={savingKey === "syncTime"}
                onClick={async () => {
                  setSavingKey("syncTime");
                  try {
                    const result = await syncPanelServerTime();
                    if (result.server_time) setServerTime(result.server_time.display);
                    toast.success(result.message);
                    await load();
                  } catch {
                    toast.error("No se pudo sincronizar la hora");
                  } finally {
                    setSavingKey(null);
                  }
                }}
              />
            </div>
          </PanelSettingRow>

          <PanelSettingRow label="Carpeta de sitios" hint="Ruta por defecto para sitios nuevos">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-[200px] flex-1">
                <FolderOpen className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={siteFolder}
                  onChange={(e) => setSiteFolder(e.target.value)}
                  className="pl-9 font-mono text-xs"
                />
              </div>
              <SaveButton
                saving={savingKey === "siteFolder"}
                onClick={() =>
                  patch("siteFolder", { default_site_folder: siteFolder }, "Carpeta de sitios guardada")
                }
              />
            </div>
          </PanelSettingRow>

          <PanelSettingRow label="Carpeta de backups">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-[200px] flex-1">
                <FolderOpen className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={backupFolder}
                  onChange={(e) => setBackupFolder(e.target.value)}
                  className="pl-9 font-mono text-xs"
                />
              </div>
              <SaveButton
                saving={savingKey === "backupFolder"}
                onClick={() =>
                  patch("backupFolder", { default_backup_folder: backupFolder }, "Carpeta de backups guardada")
                }
              />
            </div>
          </PanelSettingRow>
        </SettingsSection>

        <SettingsSection
          icon={<Activity className="h-4 w-4" />}
          title="Monitor y alertas"
          description="Umbrales de CPU, RAM y disco. Notificaciones en panel y Telegram"
        >
          <PanelSettingRow label="Monitor de recursos">
            <Switch
              checked={data.site_monitor_enabled}
              disabled={savingKey === "site_monitor_enabled"}
              onCheckedChange={(v) => toggle("site_monitor_enabled", v, { site_monitor_enabled: v })}
            />
          </PanelSettingRow>

          {data.site_monitor_enabled && (
            <>
              <PanelSettingRow label="Umbrales (%)" hint="Se dispara alerta al superar estos valores">
                <div className="grid max-w-md gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label className="text-[10px] text-muted-foreground">CPU</Label>
                    <Input
                      type="number"
                      min={50}
                      max={100}
                      value={cpuThreshold}
                      onChange={(e) => setCpuThreshold(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px] text-muted-foreground">RAM</Label>
                    <Input
                      type="number"
                      min={50}
                      max={100}
                      value={ramThreshold}
                      onChange={(e) => setRamThreshold(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px] text-muted-foreground">Disco</Label>
                    <Input
                      type="number"
                      min={50}
                      max={100}
                      value={diskThreshold}
                      onChange={(e) => setDiskThreshold(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[10px] text-muted-foreground">Cooldown (min)</Label>
                    <Input
                      type="number"
                      min={5}
                      max={1440}
                      value={alertCooldown}
                      onChange={(e) => setAlertCooldown(e.target.value)}
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <SaveButton
                    label="Guardar umbrales"
                    saving={savingKey === "monitor"}
                    onClick={() =>
                      patch(
                        "monitor",
                        {
                          cpu_threshold_percent: Number(cpuThreshold),
                          memory_threshold_percent: Number(ramThreshold),
                          disk_threshold_percent: Number(diskThreshold),
                          alert_cooldown_minutes: Number(alertCooldown),
                        },
                        "Umbrales actualizados"
                      )
                    }
                  />
                </div>
              </PanelSettingRow>

              <PanelSettingRow
                label="Telegram"
                hint="Cree un bot con @BotFather y obtenga el Chat ID con @userinfobot o su grupo"
              >
                <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Bell className="h-4 w-4 text-sky-500" />
                      <span className="text-sm font-medium">Enviar alertas por Telegram</span>
                    </div>
                    <Switch
                      checked={telegramEnabled}
                      onCheckedChange={setTelegramEnabled}
                    />
                  </div>
                  <div className="grid gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Bot Token</Label>
                      <Input
                        type="password"
                        value={telegramBotToken}
                        onChange={(e) => setTelegramBotToken(e.target.value)}
                        placeholder={
                          data.telegram_bot_configured
                            ? "••••••••  (dejar vacío para mantener)"
                            : "123456789:ABCdefGHI..."
                        }
                        className="font-mono text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Chat ID</Label>
                      <Input
                        value={telegramChatId}
                        onChange={(e) => setTelegramChatId(e.target.value)}
                        placeholder="-1001234567890"
                        className="font-mono text-xs"
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SaveButton
                      label="Guardar Telegram"
                      saving={savingKey === "telegram"}
                      onClick={() =>
                        patch(
                          "telegram",
                          {
                            telegram_alerts_enabled: telegramEnabled,
                            telegram_chat_id: telegramChatId,
                            ...(telegramBotToken.trim()
                              ? { telegram_bot_token: telegramBotToken.trim() }
                              : {}),
                          },
                          "Configuración de Telegram guardada"
                        )
                      }
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={savingKey === "telegramTest"}
                      onClick={async () => {
                        setSavingKey("telegramTest");
                        try {
                          const result = await testTelegramAlerts({
                            telegram_bot_token: telegramBotToken.trim() || undefined,
                            telegram_chat_id: telegramChatId.trim() || undefined,
                          });
                          toast[result.success ? "success" : "error"](result.message);
                        } catch (e) {
                          toast.error(e instanceof Error ? e.message : "Error al probar Telegram");
                        } finally {
                          setSavingKey(null);
                        }
                      }}
                    >
                      {savingKey === "telegramTest" ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="mr-2 h-4 w-4" />
                      )}
                      Probar envío
                    </Button>
                  </div>
                </div>
              </PanelSettingRow>
            </>
          )}
        </SettingsSection>

        <SettingsSection
          icon={<Palette className="h-4 w-4" />}
          title="Apariencia e idioma"
        >
          <PanelSettingRow label="Tema">
            <Select value={theme || "system"} onValueChange={setTheme}>
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">Fresh (Light)</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
                <SelectItem value="system">System</SelectItem>
              </SelectContent>
            </Select>
          </PanelSettingRow>

          <PanelSettingRow label="Idioma">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <Select value={locale} onValueChange={(v) => setLocale(v as "en" | "es")}>
                <SelectTrigger className="max-w-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Español</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </PanelSettingRow>
        </SettingsSection>

        <SettingsSection
          icon={<Power className="h-4 w-4" />}
          title="Avanzado"
          description="Red, CDN, backups y control del servicio panel"
          className="lg:col-span-2"
        >
          <div className="grid gap-0 lg:grid-cols-2 lg:gap-x-8">
            <PanelSettingRow label="IPv6" hint="Permitir acceso al panel por IPv6">
              <Switch
                checked={data.ipv6_enabled}
                disabled={savingKey === "ipv6_enabled"}
                onCheckedChange={(v) => toggle("ipv6_enabled", v, { ipv6_enabled: v })}
              />
            </PanelSettingRow>

            <PanelSettingRow label="Modo offline" hint="Servicios que requieren internet quedarán deshabilitados">
              <Switch
                checked={data.offline_mode}
                disabled={savingKey === "offline_mode"}
                onCheckedChange={(v) => toggle("offline_mode", v, { offline_mode: v })}
              />
            </PanelSettingRow>

            <PanelSettingRow label="CDN Proxy" hint="IP real desde proxy CDN (solo panel)">
              <Switch
                checked={data.cdn_proxy}
                disabled={savingKey === "cdn_proxy"}
                onCheckedChange={(v) => toggle("cdn_proxy", v, { cdn_proxy: v })}
              />
            </PanelSettingRow>

            <PanelSettingRow label="Favicon automático" hint="Intenta obtener favicons cada 12 h">
              <Switch
                checked={data.auto_fetch_favicon}
                disabled={savingKey === "auto_fetch_favicon"}
                onCheckedChange={(v) => toggle("auto_fetch_favicon", v, { auto_fetch_favicon: v })}
              />
            </PanelSettingRow>

            <PanelSettingRow label="Backup automático del panel">
              <div className="space-y-2">
                <Switch
                  checked={data.auto_backup_panel}
                  disabled={savingKey === "auto_backup_panel"}
                  onCheckedChange={(v) => toggle("auto_backup_panel", v, { auto_backup_panel: v })}
                />
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {data.auto_backup_count} backups · {data.auto_backup_used_mb} MB
                  </span>
                  <Input
                    type="number"
                    min={1}
                    max={365}
                    value={backupRetention}
                    onChange={(e) => setBackupRetention(e.target.value)}
                    className="h-8 w-20"
                  />
                  <span>días retención</span>
                  <SaveButton
                    label="Aplicar"
                    saving={savingKey === "backupRetention"}
                    onClick={() =>
                      patch(
                        "backupRetention",
                        { auto_backup_retention: Number(backupRetention) },
                        "Retención actualizada"
                      )
                    }
                  />
                </div>
              </div>
            </PanelSettingRow>

            <PanelSettingRow
              label="Detener panel"
              hint="Solo detiene el panel; webs y bases de datos siguen activos"
            >
              <Button
                variant="outline"
                size="sm"
                className="border-destructive/40 text-destructive hover:bg-destructive/10"
                disabled={savingKey === "close"}
                onClick={async () => {
                  setSavingKey("close");
                  try {
                    const result = await shutdownPanelService();
                    toast[result.success ? "success" : "error"](result.message);
                  } finally {
                    setSavingKey(null);
                  }
                }}
              >
                {savingKey === "close" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Detener servicio panel
              </Button>
            </PanelSettingRow>
          </div>
        </SettingsSection>
      </div>

      {!data.can_apply_host_changes && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-800 dark:text-amber-200">
          Tras cambiar puerto o ruta del panel, aplique en el servidor:{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono">sudo controlbox repair --apply-panel</code>
        </p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <SettingsContent />
    </Suspense>
  );
}
