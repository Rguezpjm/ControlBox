"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  Server,
  Eye,
  EyeOff,
  Copy,
  KeyRound,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge } from "@/components/shared/status-badge";
import { mailApi, type DnsRecordHint, type TenantMailService } from "@/lib/mail";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface MailServiceSetupProps {
  service: TenantMailService;
  onUpdated: () => void;
}

const STEPS = [
  { id: "dns", label: "DNS records" },
  { id: "incoming", label: "Incoming mail (IMAP)" },
  { id: "outgoing", label: "Outgoing mail (SMTP)" },
  { id: "verify", label: "Verify connection" },
] as const;

export function MailServiceSetup({ service, onUpdated }: MailServiceSetupProps) {
  const [dnsHints, setDnsHints] = useState<DnsRecordHint[]>([]);
  const [imapHost, setImapHost] = useState(service.imap_host || `mail.${service.mail_domain}`);
  const [imapPort, setImapPort] = useState(String(service.imap_port || 993));
  const [imapSsl, setImapSsl] = useState(service.imap_use_ssl);
  const [smtpHost, setSmtpHost] = useState(service.smtp_host || `mail.${service.mail_domain}`);
  const [smtpPort, setSmtpPort] = useState(String(service.smtp_port || 587));
  const [smtpSsl, setSmtpSsl] = useState(service.smtp_use_ssl);
  const [smtpTls, setSmtpTls] = useState(service.smtp_use_tls);
  const [adminUser, setAdminUser] = useState(service.admin_username || `postmaster@${service.mail_domain}`);
  const [adminPassword, setAdminPassword] = useState("");
  const [webmailUrl, setWebmailUrl] = useState(service.webmail_url || "");
  const [defaultQuota, setDefaultQuota] = useState(String(service.default_quota_mb));
  const [totalQuota, setTotalQuota] = useState(String(service.total_quota_mb));
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [forceActivate, setForceActivate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    mailApi.dnsHints().then(setDnsHints).catch(() => setDnsHints([]));
  }, [service.id]);

  useEffect(() => {
    setImapHost(service.imap_host || `mail.${service.mail_domain}`);
    setSmtpHost(service.smtp_host || `mail.${service.mail_domain}`);
    setAdminUser(service.admin_username || `postmaster@${service.mail_domain}`);
  }, [service]);

  const dnsDone = dnsHints.length > 0;
  const incomingDone = Boolean(imapHost.trim());
  const outgoingDone = Boolean(smtpHost.trim() && adminUser.trim());
  const verified = service.status === "active";

  function generateStrongPassword() {
    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+~`|}{[]:;?><,./-=";
    let newPassword = "";
    const upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const lower = "abcdefghijklmnopqrstuvwxyz";
    const nums = "0123456789";
    const syms = "!@#$%^&*()_+-=";
    newPassword += upper[Math.floor(Math.random() * upper.length)];
    newPassword += lower[Math.floor(Math.random() * lower.length)];
    newPassword += nums[Math.floor(Math.random() * nums.length)];
    newPassword += syms[Math.floor(Math.random() * syms.length)];
    for (let i = 0; i < 12; i++) {
      newPassword += chars[Math.floor(Math.random() * chars.length)];
    }
    newPassword = newPassword.split('').sort(() => 0.5 - Math.random()).join('');
    setAdminPassword(newPassword);
    setShowPassword(true);
  }

  function copyPasswordToClipboard() {
    if (!adminPassword) return;
    navigator.clipboard.writeText(adminPassword);
    setCopied(true);
    toast.success("Password copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  }

  async function saveSettings(shouldRethrow = false) {
    setSaving(true);
    setError(null);
    try {
      await mailApi.updateService({
        imap_host: imapHost,
        imap_port: Number(imapPort),
        imap_use_ssl: imapSsl,
        smtp_host: smtpHost,
        smtp_port: Number(smtpPort),
        smtp_use_ssl: smtpSsl,
        smtp_use_tls: smtpTls,
        admin_username: adminUser,
        admin_password: adminPassword || undefined,
        default_quota_mb: Number(defaultQuota),
        total_quota_mb: Number(totalQuota),
        webmail_url: webmailUrl || undefined,
      });
      if (!shouldRethrow) {
        setAdminPassword("");
      }
      onUpdated();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to save settings";
      setError(msg);
      if (shouldRethrow) throw err;
    } finally {
      setSaving(false);
    }
  }

  async function verifyConnection() {
    setVerifying(true);
    setError(null);
    try {
      await saveSettings(true);
      await mailApi.verifyService(adminPassword || undefined, forceActivate);
      setAdminPassword("");
      onUpdated();
      toast.success("Mail service activated successfully");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Connection verification failed");
      onUpdated();
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Server className="h-4 w-4" />
              {service.name}
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">{service.mail_domain}</p>
          </div>
          <StatusBadge status={service.status === "active" ? "running" : service.status === "error" ? "error" : "pending"} />
        </CardHeader>
        <CardContent>
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-6">
            {STEPS.map((step, index) => {
              const done =
                (step.id === "dns" && dnsDone) ||
                (step.id === "incoming" && incomingDone) ||
                (step.id === "outgoing" && outgoingDone) ||
                (step.id === "verify" && verified);
              return (
                <li
                  key={step.id}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    done && "border-primary/30 bg-primary/5"
                  )}
                >
                  {done ? (
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
                  )}
                  <span>
                    {index + 1}. {step.label}
                  </span>
                </li>
              );
            })}
          </ol>

          {service.error_message && (
            <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {service.error_message}
            </p>
          )}

          <div className="space-y-6">
            <section>
              <h3 className="text-sm font-medium mb-3">1. DNS — point your domain to the mail server</h3>
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-2 text-left">Type</th>
                      <th className="px-3 py-2 text-left">Name</th>
                      <th className="px-3 py-2 text-left">Value</th>
                      <th className="px-3 py-2 text-left hidden md:table-cell">Purpose</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dnsHints.map((row) => (
                      <tr key={`${row.type}-${row.name}`} className="border-b last:border-0">
                        <td className="px-3 py-2 font-medium">{row.type}</td>
                        <td className="px-3 py-2 font-mono">{row.name}</td>
                        <td className="px-3 py-2 font-mono break-all">{row.value}</td>
                        <td className="px-3 py-2 text-muted-foreground hidden md:table-cell">{row.purpose}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3 rounded-lg border p-4">
                <h3 className="text-sm font-medium">2. Incoming mail (IMAP)</h3>
                <div className="space-y-2">
                  <Label>Host</Label>
                  <Input value={imapHost} onChange={(e) => setImapHost(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>Port</Label>
                    <Input value={imapPort} onChange={(e) => setImapPort(e.target.value)} />
                  </div>
                  <div className="flex items-end justify-between rounded-lg border px-3 py-2">
                    <Label>SSL</Label>
                    <Switch checked={imapSsl} onCheckedChange={setImapSsl} />
                  </div>
                </div>
              </div>

              <div className="space-y-3 rounded-lg border p-4">
                <h3 className="text-sm font-medium">3. Outgoing mail (SMTP)</h3>
                <div className="space-y-2">
                  <Label>Host</Label>
                  <Input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>Port</Label>
                    <Input value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label>Admin user</Label>
                    <Input value={adminUser} onChange={(e) => setAdminUser(e.target.value)} />
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center justify-between flex-1 rounded-lg border px-3 py-2">
                    <Label className="text-xs">SMTP SSL</Label>
                    <Switch checked={smtpSsl} onCheckedChange={setSmtpSsl} />
                  </div>
                  <div className="flex items-center justify-between flex-1 rounded-lg border px-3 py-2">
                    <Label className="text-xs">STARTTLS</Label>
                    <Switch checked={smtpTls} onCheckedChange={setSmtpTls} />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Admin password {service.has_admin_password && "(leave blank to keep saved)"}</Label>
                    <button
                      type="button"
                      onClick={generateStrongPassword}
                      className="text-xs text-primary hover:underline flex items-center gap-1 cursor-pointer select-none"
                    >
                      <KeyRound className="h-3 w-3" />
                      Generate strong password
                    </button>
                  </div>
                  <div className="relative flex items-center">
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={adminPassword}
                      onChange={(e) => setAdminPassword(e.target.value)}
                      className="pr-20"
                    />
                    <div className="absolute right-2 flex items-center gap-1">
                      {adminPassword && (
                        <>
                          <button
                            type="button"
                            onClick={copyPasswordToClipboard}
                            className="text-muted-foreground hover:text-foreground p-1 rounded cursor-pointer"
                            title="Copy password"
                          >
                            {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                          </button>
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="text-muted-foreground hover:text-foreground p-1 rounded cursor-pointer"
                            title={showPassword ? "Hide password" : "Show password"}
                          >
                            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>Default mailbox quota (MB)</Label>
                <Input value={defaultQuota} onChange={(e) => setDefaultQuota(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Total tenant quota (MB)</Label>
                <Input value={totalQuota} onChange={(e) => setTotalQuota(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Webmail URL (optional)</Label>
                <Input value={webmailUrl} onChange={(e) => setWebmailUrl(e.target.value)} placeholder="https://webmail.example.com" />
              </div>
            </section>

            {error && <p className="text-sm text-destructive">{error}</p>}

            {!verified && (
              <div
                onClick={() => setForceActivate(!forceActivate)}
                className="flex items-start space-x-3 rounded-lg border border-warning/20 bg-warning/5 p-4 text-warning cursor-pointer select-none"
              >
                <Checkbox
                  id="force-activate"
                  checked={forceActivate}
                  onCheckedChange={(checked) => setForceActivate(!!checked)}
                  onClick={(e) => e.stopPropagation()}
                  className="mt-0.5 border-warning/50"
                />
                <div className="grid gap-1.5 leading-none">
                  <span className="text-sm font-medium leading-none text-warning">
                    Bypass connection validation (Force activation)
                  </span>
                  <p className="text-xs text-muted-foreground">
                    Activate the mail service even if the connection test fails (e.g. DNS propagation delays or local offline testing).
                  </p>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => void saveSettings()} disabled={saving || verified}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save settings
              </Button>
              <Button onClick={() => void verifyConnection()} disabled={verifying || verified}>
                {verifying && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Verify &amp; activate
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
