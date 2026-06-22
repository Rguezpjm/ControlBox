"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Copy,
  ExternalLink,
  Loader2,
  Shield,
} from "lucide-react";
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
import {
  wordpressApi,
  type WordPressDeployCredentials,
  type WordPressOptions,
  type WordPressProvisionStep,
} from "@/lib/wordpress";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface CreateWordPressDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

type Phase = "form" | "deploying" | "success" | "error";

function CredentialRow({
  label,
  value,
  secret,
  mono,
}: {
  label: string;
  value: string;
  secret?: boolean;
  mono?: boolean;
}) {
  const [visible, setVisible] = useState(!secret);
  const [copied, setCopied] = useState(false);

  async function copyValue() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          readOnly
          value={visible ? value : "••••••••••••"}
          className={cn("h-9 text-sm", mono && "font-mono text-xs")}
        />
        {secret ? (
          <Button type="button" variant="outline" size="sm" onClick={() => setVisible((v) => !v)}>
            {visible ? "Hide" : "Show"}
          </Button>
        ) : null}
        <Button type="button" variant="outline" size="icon" className="shrink-0" onClick={copyValue}>
          <Copy className="h-4 w-4" />
        </Button>
      </div>
      {copied ? <p className="text-xs text-emerald-600">Copied</p> : null}
    </div>
  );
}

export function CreateWordPressDialog({ open, onOpenChange, onCreated }: CreateWordPressDialogProps) {
  const [options, setOptions] = useState<WordPressOptions | null>(null);
  const [phase, setPhase] = useState<Phase>("form");
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<WordPressProvisionStep[]>([]);
  const [credentials, setCredentials] = useState<WordPressDeployCredentials | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const siteIdRef = useRef<string | null>(null);

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [adminUser, setAdminUser] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [dbName, setDbName] = useState("");
  const [dbUser, setDbUser] = useState("");
  const [dbPassword, setDbPassword] = useState("");
  const [phpVersion, setPhpVersion] = useState("8.3");
  const [sslEnabled, setSslEnabled] = useState(true);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const resetDialog = useCallback(() => {
    stopPolling();
    setPhase("form");
    setError(null);
    setSteps([]);
    setCredentials(null);
    siteIdRef.current = null;
  }, [stopPolling]);

  useEffect(() => {
    if (open) {
      wordpressApi.options()
        .then((opts) => {
          setOptions(opts);
          setPhpVersion(opts.php_versions[opts.php_versions.length - 1] || "8.3");
        })
        .catch(() => setOptions(null));
    } else {
      resetDialog();
    }
  }, [open, resetDialog]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const pollProvision = useCallback(
    (siteId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const status = await wordpressApi.provisionStatus(siteId);
          setSteps(status.steps);
          if (status.status === "running" && status.credentials) {
            stopPolling();
            setCredentials({
              ...status.credentials,
            });
            setPhase("success");
            onCreated();
          } else if (status.status === "error") {
            stopPolling();
            setError(status.error_message || "WordPress deployment failed");
            setPhase("error");
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    },
    [onCreated, stopPolling]
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPhase("deploying");
    setError(null);
    setSteps([{ step: "queued", message: "Deployment queued…", at: new Date().toISOString() }]);
    try {
      const site = await wordpressApi.create({
        name,
        domain,
        admin_user: adminUser,
        admin_password: adminPassword,
        admin_email: adminEmail,
        php_version: phpVersion,
        ssl_enabled: sslEnabled,
        db_name: dbName.trim() || undefined,
        db_user: dbUser.trim() || undefined,
        db_password: dbPassword.trim() || undefined,
      });
      siteIdRef.current = site.id;
      try {
        const initial = await wordpressApi.provisionStatus(site.id);
        setSteps(initial.steps.length ? initial.steps : steps);
      } catch {
        /* polling will retry */
      }
      pollProvision(site.id);
    } catch (err) {
      if (err instanceof ApiError) {
        const hint =
          err.status === 500
            ? " Check: docker ps | grep -E 'worker|docker-proxy|mysql' and run controlbox repair."
            : "";
        setError(`${err.message}${hint}`);
      } else {
        setError("Failed to deploy WordPress. Check your connection and try again.");
      }
      setPhase("error");
    }
  }

  function handleClose() {
    onOpenChange(false);
    if (phase === "success") {
      setName("");
      setDomain("");
      setAdminPassword("");
      setDbName("");
      setDbUser("");
      setDbPassword("");
    }
  }

  const loginUrl =
    credentials?.login_url ||
    (sslEnabled ? `https://${domain}/wp-admin` : `http://${domain}/wp-admin`);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        {phase === "form" ? (
          <>
            <DialogHeader>
              <DialogTitle>Deploy WordPress</DialogTitle>
              <DialogDescription>
                One-click WordPress with Docker, MySQL, Nginx, PHP-FPM and Let&apos;s Encrypt SSL.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="wp-name">Site Name</Label>
                  <Input id="wp-name" value={name} onChange={(e) => setName(e.target.value)} required />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="wp-domain">Domain</Label>
                  <Input
                    id="wp-domain"
                    placeholder="blog.example.com"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wp-admin">Admin Username</Label>
                  <Input id="wp-admin" value={adminUser} onChange={(e) => setAdminUser(e.target.value)} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wp-php">PHP Version</Label>
                  <Select value={phpVersion} onValueChange={setPhpVersion}>
                    <SelectTrigger id="wp-php">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(options?.php_versions || ["8.2", "8.3"]).map((v) => (
                        <SelectItem key={v} value={v}>
                          PHP {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="wp-password">Admin Password</Label>
                  <Input
                    id="wp-password"
                    type="password"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    minLength={8}
                    required
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="wp-email">Admin Email</Label>
                  <Input
                    id="wp-email"
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="space-y-3 rounded-lg border p-4">
                <div>
                  <p className="text-sm font-medium">MySQL database</p>
                  <p className="text-xs text-muted-foreground">
                    Optional. Lowercase letters, numbers and underscore. Leave empty to auto-generate.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="wp-db-name">Database name</Label>
                    <Input
                      id="wp-db-name"
                      placeholder="myblog"
                      value={dbName}
                      onChange={(e) => setDbName(e.target.value.toLowerCase())}
                      pattern="[a-z][a-z0-9_]*"
                      title="Start with a letter; use lowercase letters, numbers or _"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="wp-db-user">Database user</Label>
                    <Input
                      id="wp-db-user"
                      placeholder="wpuser"
                      value={dbUser}
                      onChange={(e) => setDbUser(e.target.value.toLowerCase())}
                      pattern="[a-z][a-z0-9_]*"
                      title="Start with a letter; use lowercase letters, numbers or _"
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="wp-db-password">Database password</Label>
                    <Input
                      id="wp-db-password"
                      type="password"
                      placeholder="Auto-generated if empty"
                      value={dbPassword}
                      onChange={(e) => setDbPassword(e.target.value)}
                      minLength={8}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <Label>SSL (Let&apos;s Encrypt)</Label>
                  <p className="text-xs text-muted-foreground">Traefik auto-certificate via certresolver</p>
                </div>
                <Switch checked={sslEnabled} onCheckedChange={setSslEnabled} />
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit">
                  Deploy WordPress
                </Button>
              </DialogFooter>
            </form>
          </>
        ) : null}

        {phase === "deploying" ? (
          <>
            <DialogHeader>
              <DialogTitle>Deploying WordPress</DialogTitle>
              <DialogDescription>
                Creating database, containers and WordPress install for <strong>{domain}</strong>
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
              {steps.map((step, index) => (
                <div key={`${step.step}-${index}`} className="flex items-start gap-3 text-sm">
                  {index === steps.length - 1 ? (
                    <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-emerald-600" />
                  ) : (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  )}
                  <p className={cn(index === steps.length - 1 && "font-medium")}>{step.message}</p>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {phase === "success" && credentials ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-emerald-600">
                <CheckCircle2 className="h-5 w-5" />
                WordPress deployed
              </DialogTitle>
              <DialogDescription>
                Save these credentials now. The database password is shown here after deployment.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Shield className="h-4 w-4 text-emerald-600" />
                  WordPress admin access
                </div>
                <CredentialRow label="Login URL" value={loginUrl} mono />
                <CredentialRow label="Admin user" value={adminUser} />
                <CredentialRow label="Admin password" value={adminPassword} secret />
                <Button asChild variant="default" className="w-full bg-emerald-600 hover:bg-emerald-600/90">
                  <a href={loginUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Open WordPress admin
                  </a>
                </Button>
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">MySQL database</p>
                <CredentialRow label="Database name" value={credentials.db_name} mono />
                <CredentialRow label="Database user" value={credentials.db_user} mono />
                <CredentialRow label="Database password" value={credentials.db_password} secret mono />
                {credentials.db_host ? (
                  <CredentialRow label="Database host" value={credentials.db_host} mono />
                ) : null}
              </div>
            </div>

            <DialogFooter>
              <Button onClick={handleClose}>Done</Button>
            </DialogFooter>
          </>
        ) : null}

        {phase === "error" ? (
          <>
            <DialogHeader>
              <DialogTitle>Deployment failed</DialogTitle>
              <DialogDescription>The WordPress site could not be deployed.</DialogDescription>
            </DialogHeader>

            {steps.length > 0 ? (
              <div className="space-y-2 rounded-lg border bg-muted/20 p-4 text-sm">
                {steps.map((step, index) => (
                  <p key={`${step.step}-${index}`}>{step.message}</p>
                ))}
              </div>
            ) : null}

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Close
              </Button>
              <Button onClick={() => setPhase("form")}>Try again</Button>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
