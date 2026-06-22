"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api-client";
import { primeCsrfAfterLogin, setTokens } from "@/lib/auth";
import { getDeviceFingerprint } from "@/lib/fingerprint";
import { securityApi, loginWithPasskey } from "@/lib/security";

function loginRedirectPath(): string {
  if (typeof window === "undefined") return "/";
  const redirect = new URLSearchParams(window.location.search).get("redirect");
  return redirect && redirect.startsWith("/") ? redirect : "/";
}

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mfaChallenge, setMfaChallenge] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [savedEmail, setSavedEmail] = useState("");
  const [savedTenant, setSavedTenant] = useState<string | undefined>();

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    const email = (form.get("email") as string).trim();
    const tenantRaw = (form.get("tenant") as string).trim();
    const tenant = tenantRaw || undefined;
    setSavedEmail(email);
    setSavedTenant(tenant);
    try {
      const result = await api.auth.login({
        email,
        password: form.get("password") as string,
        tenant_slug: tenant,
        device_fingerprint: getDeviceFingerprint(),
      });
      if (result.mfa_required && result.challenge_token) {
        setMfaChallenge(result.challenge_token);
        return;
      }
      if (result.access_token) {
        setTokens(result.access_token, "");
        await primeCsrfAfterLogin();
      }
      router.push(loginRedirectPath());
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404 && err.message === "Invalid credentials") {
          setError("Invalid credentials");
        } else if (err.status === 404 && err.message === "Tenant not found") {
          setError("Tenant not found. Leave the tenant field empty or use: main");
        } else if (err.status === 422 || err.message === "Validation failed") {
          setError("Check email and password. Leave tenant empty unless your installer specified one.");
        } else if (err.status === 404 && err.message.includes("API route not found")) {
          setError("Cannot reach API through panel. Run: controlbox repair && rebuild panel.");
        } else if (err.status >= 500) {
          setError("Panel API unavailable. Run: controlbox repair");
        } else {
          setError(err.message || "Login failed");
        }
      } else {
        setError("Cannot reach the API. Check that controlbox-api is running.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleMfaVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!mfaChallenge) return;
    setLoading(true);
    setError(null);
    try {
      const tokens = await securityApi.mfaVerify(mfaChallenge, mfaCode);
      setTokens(tokens.access_token, "");
      await primeCsrfAfterLogin();
      router.push("/websites");
    } catch {
      setError("Invalid verification code");
    } finally {
      setLoading(false);
    }
  }

  async function handlePasskeyLogin() {
    const email = savedEmail || (document.getElementById("email") as HTMLInputElement)?.value;
    if (!email) {
      setError("Enter your email first");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const tokens = await loginWithPasskey(email, savedTenant);
      setTokens(tokens.access_token, "");
      await primeCsrfAfterLogin();
      router.push("/websites");
    } catch {
      setError("Passkey login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background" />
      <Card className="relative w-full max-w-md glass">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground font-bold text-lg">
            CB
          </div>
          <CardTitle className="text-2xl">{mfaChallenge ? "Verify MFA" : "Welcome back"}</CardTitle>
          <CardDescription>
            {mfaChallenge ? "Enter your authenticator code" : "Sign in to your ControlBox account"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {mfaChallenge ? (
            <form onSubmit={handleMfaVerify} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="mfa">Authentication code</Label>
                <Input
                  id="mfa"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  placeholder="000000"
                  maxLength={8}
                  required
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Verifying..." : "Verify"}
              </Button>
              <Button type="button" variant="ghost" className="w-full" onClick={() => setMfaChallenge(null)}>
                Back to login
              </Button>
            </form>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" name="email" type="email" placeholder="admin@controlbox.local" required autoComplete="username" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" name="password" type="password" placeholder="••••••••••••" required autoComplete="current-password" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tenant">Tenant (optional)</Label>
                <Input id="tenant" name="tenant" placeholder="main" defaultValue="" autoComplete="off" />
                <p className="text-xs text-muted-foreground">Leave empty for default installs. Do not use example values like &quot;acme&quot;.</p>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Signing in..." : "Sign in"}
              </Button>
              <Button type="button" variant="outline" className="w-full" disabled={loading} onClick={handlePasskeyLogin}>
                Sign in with Passkey
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
