"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Save, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  siteModificationApi,
  type SiteModification,
  type SiteSettings,
  type SiteType,
  type UpdateSiteModificationPayload,
} from "@/lib/site-modification";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api-client";
import { websitesApi } from "@/lib/websites";
import { wordpressApi } from "@/lib/wordpress";
import { SiteAccessLogViewer } from "@/components/sites/site-access-log-viewer";
import { SiteDirectoryPanel } from "@/components/sites/site-directory-panel";

type SectionId =
  | "domains"
  | "directory"
  | "url-rewrite"
  | "default-document"
  | "config"
  | "ssl"
  | "runtime"
  | "nginx"
  | "redirect"
  | "reverse-proxy"
  | "hotlink"
  | "maintenance"
  | "logs";

interface SectionDef {
  id: SectionId;
  label: string;
  types: SiteType[];
}

const SECTIONS: SectionDef[] = [
  { id: "domains", label: "Domain Manager", types: ["website", "wordpress"] },
  { id: "directory", label: "Directory", types: ["website", "wordpress"] },
  { id: "url-rewrite", label: "URL rewrite", types: ["website", "wordpress"] },
  { id: "default-document", label: "Default document", types: ["website", "wordpress"] },
  { id: "config", label: "Config", types: ["website", "wordpress"] },
  { id: "ssl", label: "SSL", types: ["website", "wordpress"] },
  { id: "runtime", label: "PHP version", types: ["wordpress"] },
  { id: "runtime", label: "Runtime", types: ["website"] },
  { id: "nginx", label: "Web Server", types: ["website", "wordpress"] },
  { id: "redirect", label: "Redirect", types: ["website", "wordpress"] },
  { id: "reverse-proxy", label: "Reverse proxy", types: ["website", "wordpress"] },
  { id: "hotlink", label: "Hotlink Protection", types: ["website", "wordpress"] },
  { id: "maintenance", label: "Maintenance Mode", types: ["website", "wordpress"] },
  { id: "logs", label: "Response log", types: ["website", "wordpress"] },
];

function sectionsForType(siteType: SiteType): SectionDef[] {
  return SECTIONS.filter((s) => s.types.includes(siteType));
}

function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "flex min-h-[120px] w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono",
        className
      )}
      {...props}
    />
  );
}

interface SiteModificationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteType: SiteType;
  siteId: string | null;
  onUpdated?: () => void;
}

export function SiteModificationModal({
  open,
  onOpenChange,
  siteType,
  siteId,
  onUpdated,
}: SiteModificationModalProps) {
  const [data, setData] = useState<SiteModification | null>(null);
  const [settings, setSettings] = useState<SiteSettings>({});
  const [vhostConfig, setVhostConfig] = useState("");
  const [nginxConfig, setNginxConfig] = useState("");
  const [sslEnabled, setSslEnabled] = useState(true);
  const [sslTab, setSslTab] = useState<"deployed" | "letsencrypt" | "custom">("deployed");
  const [sslForceHttps, setSslForceHttps] = useState(true);
  const [sslCertificatePem, setSslCertificatePem] = useState("");
  const [sslPrivateKeyPem, setSslPrivateKeyPem] = useState("");
  const [runtimeVersion, setRuntimeVersion] = useState("");
  const [activeSection, setActiveSection] = useState<SectionId>("domains");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newDomainsText, setNewDomainsText] = useState("");
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [phpVersions, setPhpVersions] = useState<string[]>([]);
  const [websiteRuntimeVersions, setWebsiteRuntimeVersions] = useState<string[]>([]);

  const sidebarSections = useMemo(() => sectionsForType(siteType), [siteType]);

  const syncFromData = useCallback((mod: SiteModification) => {
    setData(mod);
    setSettings(mod.settings || {});
    setVhostConfig(mod.vhost_config || "");
    setNginxConfig(mod.nginx_config || "");
    setSslEnabled(mod.ssl_enabled);
    setSslForceHttps(mod.ssl_config?.force_https ?? true);
    setSslCertificatePem(mod.ssl_config?.certificate_pem || "");
    setSslPrivateKeyPem("");
    const provider = mod.ssl_config?.provider ?? "letsencrypt";
    setSslTab(provider === "custom" ? "deployed" : provider === "letsencrypt" ? "letsencrypt" : "deployed");
    setRuntimeVersion(mod.php_version || mod.runtime_version || "");
  }, []);

  const load = useCallback(async () => {
    if (!siteId) return;
    setLoading(true);
    setError(null);
    try {
      const mod = await siteModificationApi.get(siteType, siteId);
      syncFromData(mod);
      if (siteType === "wordpress") {
        const opts = await wordpressApi.options();
        setPhpVersions(opts.php_versions);
      } else {
        const rtOpts = await websitesApi.options();
        const current = rtOpts.runtimes.find((r) => r.runtime === mod.runtime);
        setWebsiteRuntimeVersions(current?.versions ?? []);
      }
      setActiveSection("domains");
      setNewDomainsText("");
      setSelectedDomains([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load site settings");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [siteId, siteType, syncFromData]);

  useEffect(() => {
    if (open && siteId) {
      load();
    }
    if (!open) {
      setData(null);
      setError(null);
    }
  }, [open, siteId, load]);

  async function handleSave(sectionSettings?: Partial<SiteSettings>, sslPayload?: UpdateSiteModificationPayload) {
    if (!siteId) return;
    setSaving(true);
    setError(null);
    try {
      const mergedSettings = sectionSettings ? { ...settings, ...sectionSettings } : settings;
      const payload: UpdateSiteModificationPayload = sslPayload ?? {
        settings: mergedSettings,
        vhost_config:
          activeSection === "config" || (activeSection === "nginx" && siteType === "website")
            ? vhostConfig
            : undefined,
        nginx_config: activeSection === "nginx" && siteType === "wordpress" ? nginxConfig : undefined,
        ssl_enabled: activeSection === "ssl" ? sslEnabled : undefined,
        php_version: siteType === "wordpress" && activeSection === "runtime" ? runtimeVersion : undefined,
        runtime_version: siteType === "website" && activeSection === "runtime" ? runtimeVersion : undefined,
      };
      const mod = await siteModificationApi.update(siteType, siteId, payload);
      syncFromData(mod);
      onUpdated?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddDomains() {
    if (!siteId) return;
    const lines = newDomainsText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      let latest: SiteModification | null = data;
      for (const line of lines) {
        const match = line.match(/^(.+?)(?::(\d+))?$/);
        const domain = (match?.[1] || line).trim();
        const port = match?.[2] ? parseInt(match[2], 10) : 443;
        latest = await siteModificationApi.addDomain(siteType, siteId, domain, port);
      }
      if (latest) syncFromData(latest);
      setNewDomainsText("");
      onUpdated?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add domains");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemoveDomains() {
    if (!siteId || selectedDomains.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      let latest: SiteModification | null = data;
      for (const domain of selectedDomains) {
        latest = await siteModificationApi.removeDomain(siteType, siteId, domain);
      }
      if (latest) syncFromData(latest);
      setSelectedDomains([]);
      onUpdated?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to remove domains");
    } finally {
      setSaving(false);
    }
  }

  function updateSettings(patch: Partial<SiteSettings>) {
    setSettings((prev) => ({ ...prev, ...patch }));
  }

  const domains = settings.domains || [];

  function renderContent() {
    if (loading) {
      return (
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      );
    }
    if (!data) {
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          {error || "No site data"}
        </div>
      );
    }

    switch (activeSection) {
      case "domains":
        return (
          <div className="space-y-4">
            <p className="text-xs text-muted-foreground">
              One domain per line. Default port is 443. Wildcard: *.domain.com. With port: www.domain.com:8080
            </p>
            <div className="flex gap-2">
              <Textarea
                value={newDomainsText}
                onChange={(e) => setNewDomainsText(e.target.value)}
                placeholder="www.example.com"
                className="min-h-[100px] font-sans"
              />
              <Button onClick={handleAddDomains} disabled={saving || !newDomainsText.trim()}>
                Add
              </Button>
            </div>
            <div className="overflow-hidden rounded-lg border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="w-10 px-3 py-2" />
                    <th className="px-3 py-2 text-left font-medium">Domain name</th>
                    <th className="px-3 py-2 text-left font-medium">Port</th>
                    <th className="px-3 py-2 text-left font-medium">Operate</th>
                  </tr>
                </thead>
                <tbody>
                  {domains.map((d) => (
                    <tr key={d.domain} className="border-b last:border-0">
                      <td className="px-3 py-2">
                        {!d.primary && (
                          <input
                            type="checkbox"
                            checked={selectedDomains.includes(d.domain)}
                            onChange={(e) => {
                              setSelectedDomains((prev) =>
                                e.target.checked
                                  ? [...prev, d.domain]
                                  : prev.filter((x) => x !== d.domain)
                              );
                            }}
                          />
                        )}
                      </td>
                      <td className={cn("px-3 py-2", d.primary && "font-medium text-emerald-600")}>
                        {d.domain}
                      </td>
                      <td className="px-3 py-2">{d.port}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {d.primary ? "Inoperable" : "Removable"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Button
              variant="destructive"
              size="sm"
              disabled={selectedDomains.length === 0 || saving}
              onClick={handleRemoveDomains}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete selected
            </Button>
          </div>
        );

      case "directory":
        return siteId && data ? (
          <SiteDirectoryPanel
            siteType={siteType}
            siteId={siteId}
            data={data}
            onUpdated={(mod) => syncFromData(mod)}
            onError={setError}
          />
        ) : null;

      case "url-rewrite":
        return (
          <div className="space-y-4">
            <Label>Rewrite rules (.htaccess / nginx include)</Label>
            <Textarea
              value={settings.url_rewrite || ""}
              onChange={(e) => updateSettings({ url_rewrite: e.target.value })}
              className="min-h-[280px]"
            />
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "default-document":
        return (
          <div className="space-y-4">
            <Label>Index files (one per line, priority top to bottom)</Label>
            <Textarea
              value={(settings.index_files || []).join("\n")}
              onChange={(e) =>
                updateSettings({
                  index_files: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                })
              }
              className="min-h-[160px] font-sans"
            />
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "config":
        return (
          <div className="space-y-4">
            <Label>docker-compose.yml (Traefik VHOST labels)</Label>
            <Textarea
              value={vhostConfig}
              onChange={(e) => setVhostConfig(e.target.value)}
              className="min-h-[360px]"
            />
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "ssl": {
        const ssl = data.ssl_config;
        const expiryLabel =
          ssl?.expires_at && ssl.days_remaining != null
            ? `${ssl.expires_at}, expira en ${ssl.days_remaining} días`
            : ssl?.expires_at ?? "—";

        async function saveSsl(payload: UpdateSiteModificationPayload) {
          await handleSave(undefined, payload);
        }

        return (
          <div className="space-y-4">
            <Tabs value={sslTab} onValueChange={(v) => setSslTab(v as typeof sslTab)}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="deployed">
                  Certificado actual
                  {ssl?.deployed && (
                    <Badge variant="outline" className="ml-1.5 h-5 border-emerald-500/40 text-[10px] text-emerald-600">
                      Activo
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="letsencrypt">Let&apos;s Encrypt</TabsTrigger>
                <TabsTrigger value="custom">Terceros / Cloudflare</TabsTrigger>
              </TabsList>

              <TabsContent value="deployed" className="mt-4 space-y-4">
                <div className="grid gap-3 rounded-lg border bg-muted/20 p-4 text-sm sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-muted-foreground">Tipo de certificado</p>
                    <p className="font-medium">{ssl?.cert_type ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Emisor</p>
                    <p className="font-medium">{ssl?.cert_brand ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Dominios</p>
                    <p className="font-medium break-all">{(ssl?.cert_domains ?? [data.primary_domain]).join(", ")}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Vencimiento</p>
                    <p className="font-medium">{expiryLabel}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between rounded-lg border px-4 py-3">
                  <div>
                    <Label>Forzar HTTPS</Label>
                    <p className="text-xs text-muted-foreground">Redirige HTTP a HTTPS vía Traefik</p>
                  </div>
                  <Switch checked={sslForceHttps} onCheckedChange={setSslForceHttps} />
                </div>

                {ssl?.certificate_pem && (
                  <div className="space-y-2">
                    <Label>Certificado (PEM)</Label>
                    <Textarea readOnly value={ssl.certificate_pem} className="min-h-[160px]" />
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={saving}
                    onClick={() =>
                      saveSsl({
                        ssl_force_https: sslForceHttps,
                        ssl_enabled: true,
                      })
                    }
                  >
                    {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Guardar
                  </Button>
                  <Button
                    variant="outline"
                    disabled={saving}
                    onClick={() =>
                      saveSsl({
                        ssl_enabled: false,
                        ssl_provider: "none",
                      })
                    }
                  >
                    Desactivar SSL
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="letsencrypt" className="mt-4 space-y-4">
                <p className="text-sm text-muted-foreground">
                  Traefik solicitará y renovará automáticamente un certificado Let&apos;s Encrypt para{" "}
                  <span className="font-medium text-foreground">{data.primary_domain}</span>.
                </p>
                <Button
                  disabled={saving}
                  onClick={() =>
                    saveSsl({
                      ssl_provider: "letsencrypt",
                      ssl_enabled: true,
                      ssl_force_https: sslForceHttps,
                    })
                  }
                >
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Usar Let&apos;s Encrypt
                </Button>
              </TabsContent>

              <TabsContent value="custom" className="mt-4 space-y-4">
                <p className="text-sm text-muted-foreground">
                  Pegue la clave privada y el certificado PEM/CRT de Cloudflare u otro proveedor (Origin Certificate,
                  comercial, etc.).
                </p>
                <div className="space-y-2">
                  <Label>Clave privada (KEY)</Label>
                  <Textarea
                    value={sslPrivateKeyPem}
                    onChange={(e) => setSslPrivateKeyPem(e.target.value)}
                    placeholder="-----BEGIN PRIVATE KEY-----"
                    className="min-h-[140px]"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Certificado (CRT / PEM)</Label>
                  <Textarea
                    value={sslCertificatePem}
                    onChange={(e) => setSslCertificatePem(e.target.value)}
                    placeholder="-----BEGIN CERTIFICATE-----"
                    className="min-h-[140px]"
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border px-4 py-3">
                  <Label>Forzar HTTPS</Label>
                  <Switch checked={sslForceHttps} onCheckedChange={setSslForceHttps} />
                </div>
                <Button
                  disabled={saving || !sslPrivateKeyPem.trim() || !sslCertificatePem.trim()}
                  onClick={() =>
                    saveSsl({
                      ssl_provider: "custom",
                      ssl_enabled: true,
                      ssl_certificate_pem: sslCertificatePem,
                      ssl_private_key_pem: sslPrivateKeyPem,
                      ssl_force_https: sslForceHttps,
                    })
                  }
                >
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  Configurar certificado
                </Button>
              </TabsContent>
            </Tabs>
          </div>
        );
      }

      case "runtime": {
        const versions = siteType === "wordpress" ? phpVersions : websiteRuntimeVersions;
        const label =
          siteType === "wordpress"
            ? "Versión PHP"
            : data.runtime === "php"
              ? "Versión PHP"
              : data.runtime === "nodejs"
                ? "Versión Node.js"
                : data.runtime === "python"
                  ? "Versión Python"
                  : "Versión de runtime";

        if (siteType === "website" && data.runtime === "html") {
          return (
            <p className="text-sm text-muted-foreground">
              Los sitios HTML estáticos no requieren selección de versión.
            </p>
          );
        }

        if (versions.length === 0) {
          return (
            <p className="text-sm text-muted-foreground">
              No hay versiones habilitadas en el servidor. Configúrelas en Preparación para producción →
              Runtimes.
            </p>
          );
        }

        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{label}</Label>
              <Select value={runtimeVersion} onValueChange={setRuntimeVersion}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccione versión" />
                </SelectTrigger>
                <SelectContent>
                  {versions.map((v) => (
                    <SelectItem key={v} value={v}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Solo se muestran versiones instaladas/habilitadas en el sistema.
              </p>
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );
      }

      case "nginx":
        return (
          <div className="space-y-4">
            <Label>
              {siteType === "wordpress" ? "nginx/default.conf" : "docker-compose.yml (Traefik routing)"}
            </Label>
            <Textarea
              value={siteType === "wordpress" ? nginxConfig : vhostConfig}
              onChange={(e) =>
                siteType === "wordpress" ? setNginxConfig(e.target.value) : setVhostConfig(e.target.value)
              }
              className="min-h-[360px]"
            />
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "redirect":
        return (
          <div className="space-y-4">
            <Label>Redirects (from → to, one per line)</Label>
            <Textarea
              value={(settings.redirects || [])
                .map((r) => `${r.from} → ${r.to}${r.code ? ` [${r.code}]` : ""}`)
                .join("\n")}
              onChange={(e) => {
                const redirects = e.target.value
                  .split("\n")
                  .map((line) => line.trim())
                  .filter(Boolean)
                  .map((line) => {
                    const codeMatch = line.match(/\s*\[(\d+)\]\s*$/);
                    const code = codeMatch ? parseInt(codeMatch[1], 10) : 301;
                    const clean = codeMatch ? line.replace(/\s*\[\d+\]\s*$/, "") : line;
                    const [from, to] = clean.split(/\s*→\s*|\s*->\s*/);
                    return { from: from?.trim() || "", to: to?.trim() || "", code };
                  })
                  .filter((r) => r.from && r.to);
                updateSettings({ redirects });
              }}
              placeholder="/old → https://example.com/new [301]"
              className="min-h-[200px] font-sans"
            />
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "reverse-proxy":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Enable reverse proxy</Label>
              <Switch
                checked={!!settings.reverse_proxy_enabled}
                onCheckedChange={(v) => updateSettings({ reverse_proxy_enabled: v })}
              />
            </div>
            <div className="space-y-2">
              <Label>Target URL</Label>
              <Input
                value={settings.reverse_proxy_target || ""}
                onChange={(e) => updateSettings({ reverse_proxy_target: e.target.value })}
                placeholder="http://127.0.0.1:3000"
              />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "hotlink":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Hotlink protection</Label>
              <Switch
                checked={!!settings.hotlink_protection}
                onCheckedChange={(v) => updateSettings({ hotlink_protection: v })}
              />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "maintenance":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Maintenance mode</Label>
              <Switch
                checked={!!settings.maintenance_mode}
                onCheckedChange={(v) => updateSettings({ maintenance_mode: v })}
              />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "logs":
        return siteId ? (
          <SiteAccessLogViewer
            siteType={siteType}
            siteId={siteId}
            active={activeSection === "logs"}
          />
        ) : null;

      default:
        return null;
    }
  }

  const title = data
    ? `Site modification [${data.primary_domain}]`
    : "Site modification";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[900px] w-[95vw] max-w-5xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b px-6 py-4 text-left">
          <DialogTitle>{title}</DialogTitle>
          {data && (
            <DialogDescription>
              Time added: {new Date(data.created_at).toLocaleString()}
            </DialogDescription>
          )}
        </DialogHeader>

        {error && (
          <div className="shrink-0 border-b bg-destructive/10 px-6 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <aside className="w-48 shrink-0 border-r bg-muted/20">
            <ScrollArea className="h-full">
              <nav className="flex flex-col p-2">
                {sidebarSections.map((section) => (
                  <button
                    key={`${section.id}-${section.label}`}
                    type="button"
                    onClick={() => setActiveSection(section.id)}
                    className={cn(
                      "rounded-md px-3 py-2 text-left text-sm transition-colors",
                      activeSection === section.id
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    {section.label}
                  </button>
                ))}
              </nav>
            </ScrollArea>
          </aside>

          <div className="min-w-0 flex-1 overflow-auto p-6">{renderContent()}</div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SaveBar({ saving, onSave }: { saving: boolean; onSave: () => void }) {
  return (
    <div className="flex justify-end pt-2">
      <Button onClick={onSave} disabled={saving}>
        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Save
      </Button>
    </div>
  );
}
