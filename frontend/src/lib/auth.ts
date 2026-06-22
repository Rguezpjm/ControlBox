import { API_BASE } from "./api-base";

const CSRF_COOKIE = "cb_csrf";

let csrfToken: string | null = null;

export function getCsrfFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${CSRF_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function ensureCsrfToken(force = false): Promise<string | null> {
  if (!force) {
    const fromCookie = getCsrfFromCookie();
    if (fromCookie) {
      csrfToken = fromCookie;
      return csrfToken;
    }
    if (csrfToken) return csrfToken;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/security/csrf-token`, {
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { csrf_token?: string };
    const token = data.csrf_token ?? getCsrfFromCookie();
    csrfToken = token ?? null;
    return csrfToken;
  } catch {
    return getCsrfFromCookie();
  }
}

export function clearCsrfToken() {
  csrfToken = null;
}

export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = csrfToken ?? getCsrfFromCookie();
  if (token) headers["X-CSRF-Token"] = token;
  return headers;
}

export function setTokens(_access: string, _refresh: string) {
  clearCsrfToken();
}

export function clearTokens() {
  clearCsrfToken();
}

export async function primeCsrfAfterLogin() {
  clearCsrfToken();
  await ensureCsrfToken(true);
}

export async function logoutApi() {
  await fetch(`${API_BASE}/api/v1/identity/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: getAuthHeaders(),
  });
  clearTokens();
}
