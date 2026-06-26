"use client";

import { useCallback, useEffect, useState } from "react";
import { Shield, ShieldAlert, Lock, AlertTriangle, Eye, Ban, KeyRound } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TableSkeleton } from "@/components/skeletons";
import {
  securityApi,
  registerPasskey,
  type SecurityEvent,
  type SecuritySettings,
  type VulnerabilityAssessment,
} from "@/lib/security";
import { VulnerabilitySummaryModal } from "@/components/security/vulnerability-summary-modal";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

const severityColors: Record<string, string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-warning/15 text-warning",
  high: "bg-destructive/15 text-destructive",
  critical: "bg-destructive text-destructive-foreground",
};

export default function SecurityPage() {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState({ blocked_ips: 0, threats_blocked_24h: 0, active_sessions: 0, security_events_24h: 0 });
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [settings, setSettings] = useState<SecuritySettings>({
    waf_enabled: true,
    brute_force_protection: true,
    enforce_mfa: false,
    malware_scanner: false,
    web_vuln_scan: false,
  });
  const [mfaSetup, setMfaSetup] = useState<{ secret: string; otpauth_url: string; backup_codes: string[] } | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [assessment, setAssessment] = useState<VulnerabilityAssessment | null>(null);
  const [summaryOpen, setSummaryOpen] = useState(false);

  const loadAssessment = useCallback(async () => {
    try {
      setAssessment(await securityApi.vulnerabilities());
    } catch {
      /* ignore */
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [ov, ev, st] = await Promise.all([
        securityApi.overview(),
        securityApi.events(20),
        securityApi.settings(),
      ]);
      setOverview(ov);
      setEvents(ev);
      setSettings(st);
      loadAssessment();
    } catch {
      toast.error("Failed to load security data");
    } finally {
      setLoading(false);
    }
  }, [loadAssessment]);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleSetting(key: keyof SecuritySettings, value: boolean) {
    const updated = { ...settings, [key]: value };
    setSettings(updated);
    try {
      await securityApi.updateSettings({ [key]: value });
      toast.success("Security settings updated");
    } catch {
      setSettings(settings);
      toast.error("Failed to update settings");
    }
  }

  async function handleRegisterPasskey() {
    try {
      await registerPasskey("ControlBox Passkey");
      toast.success("Passkey registered");
      load();
    } catch {
      toast.error("Passkey registration failed");
    }
  }

  async function handleMfaSetup() {
    try {
      const setup = await securityApi.mfaSetup();
      setMfaSetup(setup);
      toast.success("Scan the OTP URI with your authenticator app");
    } catch {
      toast.error("MFA setup failed");
    }
  }

  async function handleMfaEnable() {
    if (!mfaSetup) return;
    try {
      await securityApi.mfaEnable({
        secret: mfaSetup.secret,
        code: mfaCode,
        backup_codes: mfaSetup.backup_codes,
      });
      setMfaSetup(null);
      setMfaCode("");
      toast.success("MFA enabled");
    } catch {
      toast.error("Invalid verification code");
    }
  }

  if (loading) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Security"
        description="WAF, MFA, passkeys, and threat monitoring"
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setSummaryOpen(true)}>
              <ShieldAlert className="mr-2 h-4 w-4" />
              Vulnerabilidades
            </Button>
            <Button variant="outline" size="sm" onClick={handleMfaSetup}>
              <Lock className="mr-2 h-4 w-4" />
              Enable MFA
            </Button>
            <Button variant="outline" size="sm" onClick={handleRegisterPasskey}>
              <KeyRound className="mr-2 h-4 w-4" />
              Add Passkey
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Blocked IPs" value={overview.blocked_ips} icon={Ban} />
        <StatCard title="Threats (24h)" value={overview.threats_blocked_24h} icon={Shield} />
        <StatCard title="Active Sessions" value={overview.active_sessions} icon={Lock} />
        <StatCard title="Security Events" value={overview.security_events_24h} icon={AlertTriangle} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Security Events</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No security events recorded yet.</p>
            ) : (
              events.map((event) => (
                <div key={event.id} className="flex items-start gap-3 rounded-lg border p-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Eye className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge className={severityColors[event.severity] || severityColors.low} variant="outline">
                        {event.severity}
                      </Badge>
                      <Badge variant="outline" className="capitalize">{event.event_type.replace(/_/g, " ")}</Badge>
                    </div>
                    <p className="mt-1 text-sm">{event.message}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                      {event.ip_address && ` · ${event.ip_address}`}
                    </p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Security Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { id: "waf_enabled" as const, label: "Web Application Firewall", desc: "Block malicious requests" },
              { id: "brute_force_protection" as const, label: "Brute Force Protection", desc: "Auto-block failed logins" },
              { id: "malware_scanner" as const, label: "Malware Scanner", desc: "Daily file scans" },
              { id: "web_vuln_scan" as const, label: "Vulnerability Web Scan", desc: "NMAP, WPScan, nuclei, Gobuster sobre los dominios" },
              { id: "enforce_mfa" as const, label: "Enforce MFA", desc: "Require for all users" },
            ].map((setting) => (
              <div key={setting.id} className="flex items-center justify-between">
                <div>
                  <Label htmlFor={setting.id} className="text-sm font-medium">{setting.label}</Label>
                  <p className="text-xs text-muted-foreground">{setting.desc}</p>
                </div>
                <Switch
                  id={setting.id}
                  checked={settings[setting.id]}
                  onCheckedChange={(v) => toggleSetting(setting.id, v)}
                />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {mfaSetup && (
        <Card className="border-primary/20 shadow-md">
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-primary">Complete MFA Setup</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              <div className="flex flex-col items-center justify-center p-6 border rounded-xl bg-muted/30">
                <div className="bg-white p-3 rounded-lg shadow-sm border border-muted">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(
                      mfaSetup.otpauth_url
                    )}`}
                    alt="MFA QR Code"
                    className="w-48 h-48 shrink-0 select-none"
                    loading="lazy"
                  />
                </div>
                <p className="mt-3 text-xs text-muted-foreground text-center max-w-[220px]">
                  Escanea este código QR con tu aplicación de autenticación (Google, Microsoft, etc.)
                </p>
              </div>

              <div className="space-y-4 flex flex-col justify-between">
                <div className="space-y-3">
                  <div className="space-y-1">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Manual Secret Key
                    </Label>
                    <p className="font-mono text-sm break-all select-all bg-muted p-2 rounded-lg border">
                      {mfaSetup.secret}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Backup Codes (Guardar en un lugar seguro)
                    </Label>
                    <div className="grid grid-cols-2 gap-2 font-mono text-xs text-muted-foreground bg-muted p-2 rounded-lg border">
                      {mfaSetup.backup_codes.map((code) => (
                        <div key={code} className="bg-background px-2 py-1 rounded text-center border shadow-xs select-all">
                          {code}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-2 border-t pt-4">
                  <Label htmlFor="mfa-verification-code">Verification Code</Label>
                  <div className="flex gap-2">
                    <Input
                      id="mfa-verification-code"
                      placeholder="000000"
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value)}
                      maxLength={6}
                      className="font-mono text-center text-lg tracking-widest"
                    />
                    <Button onClick={handleMfaEnable} className="px-6">
                      Verify & Enable
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <VulnerabilitySummaryModal
        open={summaryOpen}
        onOpenChange={setSummaryOpen}
        assessment={assessment}
        onRefresh={loadAssessment}
      />
    </div>
  );
}
