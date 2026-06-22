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
import { cn } from "@/lib/utils";
import {
  siteModificationApi,
  type SiteModification,
  type SiteSettings,
  type SiteType,
} from "@/lib/site-modification";
import { ApiError } from "@/lib/api-client";

type SectionId =
  | "domains"
  | "directory"
  | "limit-access"
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
  { id: "limit-access", label: "Limit access", types: ["website", "wordpress"] },
  { id: "url-rewrite", label: "URL rewrite", types: ["website", "wordpress"] },
  { id: "default-document", label: "Default document", types: ["website", "wordpress"] },
  { id: "config", label: "Config", types: ["website", "wordpress"] },
  { id: "ssl", label: "SSL", types: ["website", "wordpress"] },
  { id: "runtime", label: "PHP version", types: ["wordpress"] },
  { id: "runtime", label: "Runtime", types: ["website"] },
  { id: "nginx", label: "Web Server", types: ["wordpress"] },
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
  const [runtimeVersion, setRuntimeVersion] = useState("");
  const [activeSection, setActiveSection] = useState<SectionId>("domains");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newDomainsText, setNewDomainsText] = useState("");
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);

  const sidebarSections = useMemo(() => sectionsForType(siteType), [siteType]);

  const syncFromData = useCallback((mod: SiteModification) => {
    setData(mod);
    setSettings(mod.settings || {});
    setVhostConfig(mod.vhost_config || "");
    setNginxConfig(mod.nginx_config || "");
    setSslEnabled(mod.ssl_enabled);
    setRuntimeVersion(mod.php_version || mod.runtime_version || "");
  }, []);

  const load = useCallback(async () => {
    if (!siteId) return;
    setLoading(true);
    setError(null);
    try {
      const mod = await siteModificationApi.get(siteType, siteId);
      syncFromData(mod);
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

  async function handleSave(sectionSettings?: Partial<SiteSettings>) {
    if (!siteId) return;
    setSaving(true);
    setError(null);
    try {
      const mergedSettings = sectionSettings ? { ...settings, ...sectionSettings } : settings;
      const payload = {
        settings: mergedSettings,
        vhost_config: activeSection === "config" ? vhostConfig : undefined,
        nginx_config: activeSection === "nginx" ? nginxConfig : undefined,
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
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Document root</Label>
              <Input
                value={settings.document_root || data.document_root}
                onChange={(e) => updateSettings({ document_root: e.target.value })}
              />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "limit-access":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Password protect site</Label>
              <Switch
                checked={!!settings.limit_access_enabled}
                onCheckedChange={(v) => updateSettings({ limit_access_enabled: v })}
              />
            </div>
            <div className="space-y-2">
              <Label>Auth user (htpasswd)</Label>
              <Input
                value={settings.limit_access_user || ""}
                onChange={(e) => updateSettings({ limit_access_user: e.target.value })}
                placeholder="admin"
              />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

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

      case "ssl":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label>SSL enabled</Label>
                <p className="text-xs text-muted-foreground">Status: {data.ssl_status}</p>
              </div>
              <Switch checked={sslEnabled} onCheckedChange={setSslEnabled} />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "runtime":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{siteType === "wordpress" ? "PHP version" : "Runtime version"}</Label>
              <Input
                value={runtimeVersion}
                onChange={(e) => setRuntimeVersion(e.target.value)}
                placeholder={siteType === "wordpress" ? "8.2" : "8.3"}
              />
            </div>
            <SaveBar saving={saving} onSave={() => handleSave()} />
          </div>
        );

      case "nginx":
        return (
          <div className="space-y-4">
            <Label>nginx/default.conf</Label>
            <Textarea
              value={nginxConfig}
              onChange={(e) => setNginxConfig(e.target.value)}
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
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Access log (last lines)</Label>
              <Textarea readOnly value={data.access_log || "(empty)"} className="min-h-[160px]" />
            </div>
            <div className="space-y-2">
              <Label>Error log (last lines)</Label>
              <Textarea readOnly value={data.error_log || "(empty)"} className="min-h-[160px]" />
            </div>
            <Button variant="outline" size="sm" onClick={load} disabled={loading}>
              Refresh logs
            </Button>
          </div>
        );

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
