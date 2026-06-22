"use client";

import { useState, useEffect, useMemo } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { websitesApi, type WebsiteOptions } from "@/lib/websites";
import { ApiError } from "@/lib/api-client";

interface CreateWebsiteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateWebsiteDialog({ open, onOpenChange, onCreated }: CreateWebsiteDialogProps) {
  const [options, setOptions] = useState<WebsiteOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [runtime, setRuntime] = useState("html");
  const [runtimeVersion, setRuntimeVersion] = useState("");
  const [databaseEngine, setDatabaseEngine] = useState("none");
  const [sslEnabled, setSslEnabled] = useState(true);

  useEffect(() => {
    if (open) {
      websitesApi.options()
        .then(setOptions)
        .catch(() => setOptions(null));
    }
  }, [open]);

  const selectedRuntime = options?.runtimes.find((r) => r.runtime === runtime);
  const versions = useMemo(() => selectedRuntime?.versions || [], [selectedRuntime]);

  useEffect(() => {
    if (selectedRuntime) {
      setRuntimeVersion(selectedRuntime.default_version || versions[0] || "");
    }
  }, [runtime, selectedRuntime, versions]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await websitesApi.create({
        name,
        domain,
        runtime,
        runtime_version: runtimeVersion || null,
        database_engine: databaseEngine,
        ssl_enabled: sslEnabled,
      });
      onOpenChange(false);
      setName("");
      setDomain("");
      setRuntime("html");
      setDatabaseEngine("none");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create website");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Website</DialogTitle>
          <DialogDescription>
            Deploy a new site with Docker, SSL, monitoring and database auto-configured.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Site Name</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="My Website" required />
          </div>

          <div className="space-y-2">
            <Label htmlFor="domain">Domain</Label>
            <Input id="domain" value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="app.example.com" required />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Runtime</Label>
              <Select value={runtime} onValueChange={setRuntime}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {options?.runtimes.map((r) => (
                    <SelectItem key={r.runtime} value={r.runtime}>{r.label}</SelectItem>
                  )) || (
                    <>
                      <SelectItem value="html">HTML Static</SelectItem>
                      <SelectItem value="php">PHP</SelectItem>
                      <SelectItem value="nodejs">Node.js</SelectItem>
                      <SelectItem value="python">Python</SelectItem>
                      <SelectItem value="flutter">Flutter Web</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>

            {versions.length > 0 && (
              <div className="space-y-2">
                <Label>Version</Label>
                <Select value={runtimeVersion} onValueChange={setRuntimeVersion}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {versions.map((v) => (
                      <SelectItem key={v} value={v}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label>Database</Label>
            <Select value={databaseEngine} onValueChange={setDatabaseEngine}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {options?.databases.map((d) => (
                  <SelectItem key={d.engine} value={d.engine}>{d.label}</SelectItem>
                )) || (
                  <>
                    <SelectItem value="none">None</SelectItem>
                    <SelectItem value="mysql">MySQL</SelectItem>
                    <SelectItem value="supabase">Supabase (PostgreSQL)</SelectItem>
                    <SelectItem value="mssql">Microsoft SQL Server</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Database credentials are provisioned automatically and injected into the container.
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">SSL (Let&apos;s Encrypt)</p>
              <p className="text-xs text-muted-foreground">Auto-configured via Traefik</p>
            </div>
            <Switch checked={sslEnabled} onCheckedChange={setSslEnabled} />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Provisioning..." : "Create Website"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
