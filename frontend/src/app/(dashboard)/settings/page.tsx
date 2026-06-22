"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { FolderOpen, Globe, Loader2 } from "lucide-react";
import { useTheme } from "next-themes";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
} from "@/components/settings/panel-setting-row";
import {
  getPanelSettings,
  shutdownPanelService,
  syncPanelServerTime,
  updatePanelSettings,
  type PanelSettings,
} from "@/lib/platform";
import { useI18n } from "@/providers/i18n-provider";
import { toast } from "sonner";

function SaveButton({
  onClick,
  saving,
  label = "Save",
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

  async function toggle(key: keyof PanelSettings, value: boolean, field: Parameters<typeof updatePanelSettings>[0]) {
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
        <PageHeader title="Panel Setting" description="Configuración del panel ControlBox" />
        <PanelSettingsCard>
          <PanelSettingRow
            label="Theme"
            hint="Tema claro u oscuro del panel"
          >
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
          <PanelSettingRow label="Language" hint="Idioma de la interfaz del panel">
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
    <div className="space-y-6">
      <PageHeader
        title="Panel Setting"
        description={`ControlBox ${data.controlbox_version} · ${data.os_label} · ${data.controlbox_profile}`}
      />

      <PanelSettingsCard>
        <PanelSettingRow
          label="Close panel"
          hint="Solo detiene el panel; no afecta webs, bases de datos ni otros servicios"
        >
          <Button
            variant="outline"
            size="sm"
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
            Stop panel service
          </Button>
        </PanelSettingRow>

        <PanelSettingRow label="Alias" hint="Nombre visible del servidor en el panel">
          <div className="flex max-w-lg flex-wrap items-center gap-2">
            <Input value={alias} onChange={(e) => setAlias(e.target.value)} className="flex-1" />
            <SaveButton
              saving={savingKey === "alias"}
              onClick={() => patch("alias", { panel_alias: alias }, "Alias guardado")}
            />
          </div>
        </PanelSettingRow>

        <PanelSettingRow
          label="Timeout"
          hint="Si no hay actividad en este tiempo, la sesión del panel se cierra automáticamente"
        >
          <div className="flex max-w-lg flex-wrap items-center gap-2">
            <Input
              type="number"
              min={1}
              max={168}
              value={timeoutHours}
              onChange={(e) => setTimeoutHours(e.target.value)}
              className="w-28"
            />
            <span className="text-sm text-muted-foreground">Hour(s)</span>
            <SaveButton
              label="Modify"
              saving={savingKey === "timeout"}
              onClick={() =>
                patch(
                  "timeout",
                  { session_timeout_hours: Number(timeoutHours) },
                  "Timeout actualizado"
                )
              }
            />
          </div>
        </PanelSettingRow>

        <PanelSettingRow
          label="Default site folder"
          hint="Los sitios nuevos se crearán por defecto en esta ruta"
        >
          <div className="flex max-w-xl flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[200px]">
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

        <PanelSettingRow
          label="Default backup folder"
          hint="Directorio de respaldos de sitios y bases de datos"
        >
          <div className="flex max-w-xl flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[200px]">
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
                patch(
                  "backupFolder",
                  { default_backup_folder: backupFolder },
                  "Carpeta de backups guardada"
                )
              }
            />
          </div>
        </PanelSettingRow>

        <PanelSettingRow label="Server IP" hint="IP por defecto del servidor. Use IP interna para pruebas en VM">
          <div className="flex max-w-lg flex-wrap items-center gap-2">
            <Input value={serverIp} onChange={(e) => setServerIp(e.target.value)} className="flex-1" />
            <SaveButton
              saving={savingKey === "serverIp"}
              onClick={() => patch("serverIp", { server_ip: serverIp }, "IP guardada")}
            />
          </div>
        </PanelSettingRow>

        <PanelSettingRow label="Server time" hint="Hora actual del servidor">
          <div className="flex max-w-xl flex-wrap items-center gap-2">
            <Input value={serverTime} readOnly className="flex-1 font-mono text-xs" />
            <SaveButton
              label="Sync"
              saving={savingKey === "syncTime"}
              onClick={async () => {
                setSavingKey("syncTime");
                try {
                  const result = await syncPanelServerTime();
                  if (result.server_time) {
                    setServerTime(result.server_time.display);
                  }
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

        <PanelSettingRow label="Panel port" hint={`URL: IP${data.panel_url_hint}`}>
          <div className="flex max-w-lg flex-wrap items-center gap-2">
            <Input
              type="number"
              min={1024}
              max={65535}
              value={panelPort}
              onChange={(e) => setPanelPort(e.target.value)}
              className="w-32"
            />
            <Input
              value={panelPath}
              onChange={(e) => setPanelPath(e.target.value)}
              placeholder="/"
              className="flex-1 font-mono text-xs"
            />
            <SaveButton
              saving={savingKey === "panelAccess"}
              onClick={() =>
                patch(
                  "panelAccess",
                  {
                    panel_port: Number(panelPort),
                    panel_base_path: panelPath,
                  },
                  "Acceso al panel guardado"
                )
              }
            />
          </div>
        </PanelSettingRow>

        <PanelSettingRow label="IPv6" hint="Permitir acceso al panel mediante dirección IPv6">
          <Switch
            checked={data.ipv6_enabled}
            disabled={savingKey === "ipv6_enabled"}
            onCheckedChange={(v) => toggle("ipv6_enabled", v, { ipv6_enabled: v })}
          />
        </PanelSettingRow>

        <PanelSettingRow
          label="Offline mode"
          hint="Los servicios que requieren internet no estarán disponibles"
        >
          <Switch
            checked={data.offline_mode}
            disabled={savingKey === "offline_mode"}
            onCheckedChange={(v) => toggle("offline_mode", v, { offline_mode: v })}
          />
        </PanelSettingRow>

        <PanelSettingRow label="Theme" hint="Apariencia visual del panel">
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

        <PanelSettingRow label="Language" hint="Idioma de la interfaz">
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

        <PanelSettingRow
          label="CDN Proxy"
          hint="Obtener la IP real de la petición desde el proxy CDN (solo panel)"
        >
          <Switch
            checked={data.cdn_proxy}
            disabled={savingKey === "cdn_proxy"}
            onCheckedChange={(v) => toggle("cdn_proxy", v, { cdn_proxy: v })}
          />
        </PanelSettingRow>

        <PanelSettingRow label="Site Monitor" hint="Monitor gratuito de sitios y alertas de recursos">
          <div className="space-y-3">
            <Switch
              checked={data.site_monitor_enabled}
              disabled={savingKey === "site_monitor_enabled"}
              onCheckedChange={(v) => toggle("site_monitor_enabled", v, { site_monitor_enabled: v })}
            />
            {data.site_monitor_enabled && (
              <div className="grid max-w-md gap-2 sm:grid-cols-2">
                <Input
                  type="number"
                  min={50}
                  max={100}
                  value={cpuThreshold}
                  onChange={(e) => setCpuThreshold(e.target.value)}
                  placeholder="CPU %"
                />
                <Input
                  type="number"
                  min={50}
                  max={100}
                  value={ramThreshold}
                  onChange={(e) => setRamThreshold(e.target.value)}
                  placeholder="RAM %"
                />
                <Input
                  type="number"
                  min={50}
                  max={100}
                  value={diskThreshold}
                  onChange={(e) => setDiskThreshold(e.target.value)}
                  placeholder="Disk %"
                />
                <Input
                  type="number"
                  min={5}
                  max={1440}
                  value={alertCooldown}
                  onChange={(e) => setAlertCooldown(e.target.value)}
                  placeholder="Cooldown min"
                />
                <SaveButton
                  label="Modify"
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
                      "Umbrales de monitor actualizados"
                    )
                  }
                />
              </div>
            )}
          </div>
        </PanelSettingRow>

        <PanelSettingRow
          label="Auto-fetch favicon"
          hint="Intenta obtener el favicon cada 12 horas cuando está activo"
        >
          <Switch
            checked={data.auto_fetch_favicon}
            disabled={savingKey === "auto_fetch_favicon"}
            onCheckedChange={(v) => toggle("auto_fetch_favicon", v, { auto_fetch_favicon: v })}
          />
        </PanelSettingRow>

        <PanelSettingRow
          label="Auto Backup Panel"
          hint="El backup automático no incluye datos de sitios web ni MySQL"
        >
          <div className="space-y-3">
            <Switch
              checked={data.auto_backup_panel}
              disabled={savingKey === "auto_backup_panel"}
              onCheckedChange={(v) => toggle("auto_backup_panel", v, { auto_backup_panel: v })}
            />
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>
                Backups: {data.auto_backup_count} · Usado: {data.auto_backup_used_mb} MB
              </span>
              <Input
                type="number"
                min={1}
                max={365}
                value={backupRetention}
                onChange={(e) => setBackupRetention(e.target.value)}
                className="h-8 w-20"
              />
              <span>retención</span>
              <SaveButton
                label="Modify"
                saving={savingKey === "backupRetention"}
                onClick={() =>
                  patch(
                    "backupRetention",
                    { auto_backup_retention: Number(backupRetention) },
                    "Retención de backup actualizada"
                  )
                }
              />
            </div>
          </div>
        </PanelSettingRow>
      </PanelSettingsCard>

      {!data.can_apply_host_changes && (
        <p className="text-xs text-amber-600">
          Algunos cambios de host requieren ejecutar en el servidor:{" "}
          <code className="rounded bg-muted px-1">sudo controlbox repair --apply-panel</code>
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
