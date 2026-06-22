"use client";

import { useCallback, useEffect, useState } from "react";
import { Cloud, Loader2, Shield, Wifi } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { SettingsSection, PanelSettingRow } from "@/components/settings/panel-setting-row";
import { cloudflareApi, type CloudflareSettings } from "@/lib/cloudflare";

export function CloudflareSettingsPanel() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [settings, setSettings] = useState<CloudflareSettings | null>(null);
  const [apiToken, setApiToken] = useState("");
  const [accountId, setAccountId] = useState("");
  const [tunnelHostname, setTunnelHostname] = useState("");
  const [enabled, setEnabled] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await cloudflareApi.getSettings();
      setSettings(data);
      setAccountId(data.account_id);
      setTunnelHostname(data.tunnel_hostname);
      setEnabled(data.enabled);
      setApiToken("");
    } catch {
      toast.error("No se pudo cargar la configuración de Cloudflare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await cloudflareApi.updateSettings({
        enabled,
        api_token: apiToken.trim() || undefined,
        account_id: accountId.trim() || undefined,
        tunnel_hostname: tunnelHostname.trim() || undefined,
      });
      setSettings(updated);
      setApiToken("");
      toast.success("Configuración de Cloudflare guardada");
    } catch {
      toast.error("Error al guardar Cloudflare");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    try {
      const result = await cloudflareApi.testConnection({
        api_token: apiToken.trim() || undefined,
        account_id: accountId.trim() || undefined,
      });
      if (result.success) {
        toast.success(result.message);
        if (result.account_id) setAccountId(result.account_id);
        await load();
      } else {
        toast.error(result.message);
      }
    } catch {
      toast.error("No se pudo verificar la conexión");
    } finally {
      setTesting(false);
    }
  }

  async function handleTunnelToggle(next: boolean) {
    setSaving(true);
    try {
      const updated = await cloudflareApi.updateSettings({
        tunnel_enabled: next,
        tunnel_hostname: tunnelHostname.trim() || undefined,
      });
      setSettings(updated);
      toast.success(next ? "Cloudflare Tunnel activado" : "Cloudflare Tunnel detenido");
    } catch {
      toast.error("Error al cambiar el túnel");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Cargando Cloudflare...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsSection
        title="Cloudflare"
        description="Conecta tu cuenta de Cloudflare para administrar dominios, DNS y exponer tu panel con Tunnel."
        icon={<Cloud className="h-4 w-4" />}
      >
        <PanelSettingRow
          label="Integración activa"
          hint="Habilita la gestión de zonas Cloudflare en Dominios"
        >
          <Switch checked={enabled} onCheckedChange={setEnabled} disabled={!settings?.configured && !apiToken} />
        </PanelSettingRow>

        <PanelSettingRow
          label="API Token"
          hint="Crea un token en Cloudflare con permisos Zone:Read, Zone:Edit, DNS:Edit y Account:Cloudflare Tunnel:Edit"
        >
          <div className="flex w-full max-w-md flex-col gap-2">
            <Input
              type="password"
              placeholder={settings?.configured ? "•••••••• (dejar vacío para mantener)" : "Pegue su API Token"}
              value={apiToken}
              onChange={(e) => setApiToken(e.target.value)}
              autoComplete="off"
            />
            {settings?.configured && (
              <Badge variant="outline" className="w-fit text-emerald-600">
                Token configurado
              </Badge>
            )}
          </div>
        </PanelSettingRow>

        <PanelSettingRow label="Account ID" hint="Opcional — se detecta automáticamente al probar la conexión">
          <Input
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            placeholder="Account ID"
            className="max-w-md"
          />
        </PanelSettingRow>

        <div className="flex flex-wrap gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => void handleTest()} disabled={testing}>
            {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wifi className="mr-2 h-4 w-4" />}
            Probar conexión
          </Button>
          <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => void handleSave()} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Guardar
          </Button>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Cloudflare Tunnel"
        description="Expone su IP privada como URL pública segura sin abrir puertos en el firewall."
        icon={<Shield className="h-4 w-4" />}
      >
        <PanelSettingRow
          label="Hostname público"
          hint="Subdominio en Cloudflare que apuntará a este panel (ej. panel.midominio.com)"
        >
          <Input
            value={tunnelHostname}
            onChange={(e) => setTunnelHostname(e.target.value)}
            placeholder="panel.ejemplo.com"
            className="max-w-md"
            disabled={!settings?.configured}
          />
        </PanelSettingRow>

        <PanelSettingRow label="Activar Tunnel" hint="Levanta cloudflared en el servidor y conecta el hostname">
          <div className="flex items-center gap-3">
            <Switch
              checked={settings?.tunnel_enabled ?? false}
              onCheckedChange={(v) => void handleTunnelToggle(v)}
              disabled={!settings?.configured || saving}
            />
            {settings?.tunnel_running ? (
              <Badge className="bg-emerald-600">En ejecución</Badge>
            ) : settings?.tunnel_enabled ? (
              <Badge variant="secondary">Detenido</Badge>
            ) : null}
          </div>
        </PanelSettingRow>

        {settings?.tunnel_id && (
          <p className="text-xs text-muted-foreground px-1">
            Tunnel ID: <code className="rounded bg-muted px-1">{settings.tunnel_id}</code>
          </p>
        )}
      </SettingsSection>
    </div>
  );
}
