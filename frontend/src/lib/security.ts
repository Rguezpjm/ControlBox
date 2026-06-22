import { ensureCsrfToken } from "./auth";
import { getDeviceFingerprint } from "./fingerprint";
import { request } from "./api-client";

export interface SecurityOverview {
  blocked_ips: number;
  threats_blocked_24h: number;
  active_sessions: number;
  mfa_enabled_users: number;
  passkeys_count: number;
  security_events_24h: number;
}

export interface SecurityEvent {
  id: string;
  event_type: string;
  severity: string;
  message: string;
  ip_address: string | null;
  user_agent: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SecuritySettings {
  waf_enabled: boolean;
  brute_force_protection: boolean;
  enforce_mfa: boolean;
  malware_scanner: boolean;
}

export interface TrustedDevice {
  id: string;
  label: string;
  fingerprint_hash: string;
  user_agent: string | null;
  ip_address: string | null;
  last_seen_at: string | null;
  created_at: string;
}

export interface Passkey {
  id: string;
  nickname: string;
  transports: string[];
  last_used_at: string | null;
  created_at: string;
}

export interface MfaSetup {
  secret: string;
  otpauth_url: string;
  backup_codes: string[];
}

function authOpts() {
  return { credentials: "include" as const };
}

export const securityApi = {
  overview: () =>
    request<SecurityOverview>("/api/v1/security/overview", authOpts()),

  events: (limit = 50) =>
    request<SecurityEvent[]>(`/api/v1/security/events?limit=${limit}`, authOpts()),

  settings: () =>
    request<SecuritySettings>("/api/v1/security/settings", authOpts()),

  updateSettings: (data: Partial<SecuritySettings>) =>
    request<SecuritySettings>("/api/v1/security/settings", {
      ...authOpts(),
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  blockedIps: () =>
    request<{ ip: string; reason: string; ttl_seconds: number }[]>("/api/v1/security/blocked-ips", authOpts()),

  unblockIp: (ip: string) =>
    request<void>(`/api/v1/security/blocked-ips/${encodeURIComponent(ip)}`, {
      ...authOpts(),
      method: "DELETE",
    }),

  devices: () =>
    request<TrustedDevice[]>("/api/v1/security/devices", authOpts()),

  revokeDevice: (id: string) =>
    request<void>(`/api/v1/security/devices/${id}`, { ...authOpts(), method: "DELETE" }),

  passkeys: () =>
    request<Passkey[]>("/api/v1/security/passkeys", authOpts()),

  mfaSetup: () =>
    request<MfaSetup>("/api/v1/security/mfa/setup", { ...authOpts(), method: "POST" }),

  mfaEnable: (data: { secret: string; code: string; backup_codes: string[] }) =>
    request<void>("/api/v1/security/mfa/enable", {
      ...authOpts(),
      method: "POST",
      body: JSON.stringify(data),
    }),

  mfaDisable: (code: string) =>
    request<void>("/api/v1/security/mfa/disable", {
      ...authOpts(),
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  mfaVerify: (challenge_token: string, code: string) =>
    request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      session_id: string;
    }>("/api/v1/security/mfa/verify", {
      method: "POST",
      credentials: "include",
      body: JSON.stringify({
        challenge_token,
        code,
        device_fingerprint: getDeviceFingerprint(),
      }),
    }),

  csrfToken: () =>
    request<{ csrf_token: string }>("/api/v1/security/csrf-token", authOpts()),

  webauthnRegisterOptions: () =>
    request<PublicKeyCredentialCreationOptions>("/api/v1/security/webauthn/register/options", authOpts()),

  webauthnRegisterVerify: (credential: object, nickname: string) =>
    request<Passkey>("/api/v1/security/webauthn/register/verify", {
      ...authOpts(),
      method: "POST",
      body: JSON.stringify({ credential, nickname }),
    }),

  webauthnLoginOptions: (email: string, tenant_slug?: string) =>
    request<PublicKeyCredentialRequestOptions>("/api/v1/security/webauthn/login/options", {
      method: "POST",
      body: JSON.stringify({ email, tenant_slug }),
    }),

  webauthnLoginVerify: (email: string, credential: object, tenant_slug?: string) =>
    request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      session_id: string;
    }>("/api/v1/security/webauthn/login/verify", {
      method: "POST",
      credentials: "include",
      body: JSON.stringify({
        email,
        credential,
        tenant_slug,
        device_fingerprint: getDeviceFingerprint(),
      }),
    }),
};

export async function registerPasskey(nickname = "Passkey"): Promise<Passkey> {
  const options = await securityApi.webauthnRegisterOptions();
  const credential = await navigator.credentials.create({
    publicKey: parseCreationOptions(options),
  });
  if (!credential) throw new Error("Passkey registration cancelled");
  return securityApi.webauthnRegisterVerify(serializeCredential(credential as PublicKeyCredential), nickname);
}

export async function loginWithPasskey(email: string, tenant_slug?: string) {
  const options = await securityApi.webauthnLoginOptions(email, tenant_slug);
  const credential = await navigator.credentials.get({
    publicKey: parseRequestOptions(options),
  });
  if (!credential) throw new Error("Passkey login cancelled");
  return securityApi.webauthnLoginVerify(
    email,
    serializeCredential(credential as PublicKeyCredential),
    tenant_slug
  );
}

function parseCreationOptions(options: PublicKeyCredentialCreationOptions): PublicKeyCredentialCreationOptions {
  return {
    ...options,
    challenge: base64ToBuffer(options.challenge as unknown as string),
    user: {
      ...options.user,
      id: base64ToBuffer(options.user.id as unknown as string),
    },
    excludeCredentials: options.excludeCredentials?.map((c) => ({
      ...c,
      id: base64ToBuffer(c.id as unknown as string),
    })),
  };
}

function parseRequestOptions(options: PublicKeyCredentialRequestOptions): PublicKeyCredentialRequestOptions {
  return {
    ...options,
    challenge: base64ToBuffer(options.challenge as unknown as string),
    allowCredentials: options.allowCredentials?.map((c) => ({
      ...c,
      id: base64ToBuffer(c.id as unknown as string),
    })),
  };
}

function base64ToBuffer(value: string): ArrayBuffer {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function bufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function serializeCredential(credential: PublicKeyCredential) {
  const response = credential.response as AuthenticatorAttestationResponse & AuthenticatorAssertionResponse;
  const result: Record<string, unknown> = {
    id: credential.id,
    rawId: bufferToBase64(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToBase64(response.clientDataJSON),
    },
  };
  if ("attestationObject" in response) {
    (result.response as Record<string, unknown>).attestationObject = bufferToBase64(response.attestationObject);
  }
  if ("authenticatorData" in response) {
    (result.response as Record<string, unknown>).authenticatorData = bufferToBase64(response.authenticatorData);
  }
  if ("signature" in response) {
    (result.response as Record<string, unknown>).signature = bufferToBase64(response.signature);
  }
  return result;
}
