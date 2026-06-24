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
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Complete MFA Setup</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground break-all">{mfaSetup.otpauth_url}</p>
            <p className="text-xs text-muted-foreground">
              Backup codes: {mfaSetup.backup_codes.join(", ")}
            </p>
            <div className="flex gap-2">
              <Input
                placeholder="000000"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                maxLength={6}
              />
              <Button onClick={handleMfaEnable}>Verify & Enable</Button>
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
