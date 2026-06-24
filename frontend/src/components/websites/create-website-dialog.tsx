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
  const [createFtpAccount, setCreateFtpAccount] = useState(false);
  const [createdFtp, setCreatedFtp] = useState<{ username: string; password: string; home: string } | null>(null);

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

  function resetForm() {
    setName("");
    setDomain("");
    setRuntime("html");
    setDatabaseEngine("none");
    setCreateFtpAccount(false);
    setCreatedFtp(null);
  }

  function handleClose() {
    resetForm();
    onOpenChange(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const site = await websitesApi.create({
        name,
        domain,
        runtime,
        runtime_version: runtimeVersion || null,
        database_engine: databaseEngine,
        ssl_enabled: sslEnabled,
        create_ftp_account: createFtpAccount,
      });
      onCreated();
      if (createFtpAccount && site.ftp_password) {
        setCreatedFtp({
          username: site.ftp_username || "",
          password: site.ftp_password,
          home: site.ftp_home || "",
        });
      } else {
        handleClose();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create website");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : handleClose())}>
      <DialogContent className="sm:max-w-md">
        {createdFtp ? (
          <>
            <DialogHeader>
              <DialogTitle>Website created</DialogTitle>
              <DialogDescription>
                Save these FTP credentials now — the password won&apos;t be shown again.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3">
              <div className="space-y-2 rounded-lg border p-3">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">FTP user</p>
                  <p className="font-mono text-sm break-all">{createdFtp.username}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">FTP password</p>
                  <p className="font-mono text-sm break-all">{createdFtp.password}</p>
                </div>
                {createdFtp.home ? (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">FTP directory</p>
                    <p className="font-mono text-sm break-all">{createdFtp.home}</p>
                  </div>
                ) : null}
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigator.clipboard?.writeText(`${createdFtp.username} / ${createdFtp.password}`)}
                >
                  Copy
                </Button>
                <Button type="button" onClick={handleClose}>Done</Button>
              </DialogFooter>
            </div>
          </>
        ) : (
        <>
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

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Create FTP account</p>
              <p className="text-xs text-muted-foreground">
                Auto-create an FTP/SFTP account for this site after deployment.
              </p>
            </div>
            <Switch checked={createFtpAccount} onCheckedChange={setCreateFtpAccount} />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Provisioning..." : "Create Website"}
            </Button>
          </DialogFooter>
        </form>
        </>
        )}
      </DialogContent>
    </Dialog>
  );
}
