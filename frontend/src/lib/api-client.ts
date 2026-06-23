import { API_BASE } from "./api-base";
import { APP_BASE_PATH } from "./base-path";

import { clearCsrfToken, ensureCsrfToken, getAuthHeaders } from "./auth";

interface RequestOptions extends RequestInit {
  credentials?: RequestCredentials;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function redirectToLoginFromBrowser() {
  if (typeof window === "undefined") return;
  let currentPath = window.location.pathname;
  if (APP_BASE_PATH) {
    while (currentPath === APP_BASE_PATH || currentPath.startsWith(`${APP_BASE_PATH}/`)) {
      currentPath = currentPath.slice(APP_BASE_PATH.length) || "/";
    }
  }
  const current = `${currentPath}${window.location.search}`;
  const loginPath = `${APP_BASE_PATH}/login?redirect=${encodeURIComponent(current)}`;
  window.location.assign(loginPath);
}

function parseErrorPayload(text: string, status: number): { message: string; code?: string } {
  try {
    const parsed = JSON.parse(text) as {
      error?: string;
      code?: string;
      detail?: unknown;
      message?: string;
    };

    if (typeof parsed.error === "string" && parsed.error) {
      return { message: parsed.error, code: parsed.code };
    }

    if (typeof parsed.detail === "string" && parsed.detail) {
      return { message: parsed.detail, code: parsed.code };
    }

    if (Array.isArray(parsed.detail)) {
      const parts = parsed.detail
        .map((item) => {
          if (typeof item === "object" && item && "msg" in item) {
            return String((item as { msg?: string }).msg || "");
          }
          return "";
        })
        .filter(Boolean);
      if (parts.length) {
        return { message: parts.join(". "), code: parsed.code ?? "validation_error" };
      }
    }

    if (typeof parsed.message === "string" && parsed.message) {
      return { message: parsed.message, code: parsed.code };
    }
  } catch {
    // non-JSON body (HTML 404/502 from proxy)
  }

  if (status === 401) {
    return { message: "Session expired. Please sign in again.", code: "unauthorized" };
  }
  if (status === 404) {
    return { message: "API route not found. Rebuild panel and check PANEL_BASE_PATH.", code: "not_found" };
  }
  if (status === 502 || status === 503) {
    return { message: "Panel API unavailable. Run: controlbox repair", code: "bad_gateway" };
  }
  if (status === 403) {
    return { message: text.includes("CSRF") ? "CSRF validation failed" : "Request blocked.", code: "forbidden" };
  }
  if (status === 409) {
    return { message: "This domain or resource is already in use.", code: "conflict" };
  }
  if (status === 422) {
    return { message: "Invalid form data. Check all fields and try again.", code: "validation_error" };
  }
  if (status === 500) {
    return { message: "Server error. Run controlbox repair on the VPS and check API logs.", code: "internal_error" };
  }
  return { message: `Request failed (HTTP ${status})`, code: undefined };
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        clearCsrfToken();
        await ensureCsrfToken(true);
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        };
        const response = await fetch(`${API_BASE}/api/v1/identity/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers,
          body: JSON.stringify({}),
        });
        if (response.ok) {
          await ensureCsrfToken(true);
        }
        return response.ok;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

async function buildHeaders(init: RequestInit): Promise<HeadersInit> {
  await ensureCsrfToken();
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders(),
    ...(init.headers || {}),
  };
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { ...init } = options;
  const method = (init.method || "GET").toUpperCase();
  const isMutation = !["GET", "HEAD", "OPTIONS"].includes(method);

  async function doFetch() {
    const headers = await buildHeaders(init);
    return fetch(`${API_BASE}${endpoint}`, {
      ...init,
      credentials: "include",
      headers,
    });
  }

  let response = await doFetch();

  if (response.status === 401 && !endpoint.includes("/auth/")) {
    const refreshed = await refreshSession();
    if (refreshed) response = await doFetch();
  }

  if (response.status === 403 && isMutation && !endpoint.includes("/auth/")) {
    clearCsrfToken();
    await ensureCsrfToken(true);
    response = await doFetch();
  }

  if (!response.ok) {
    if (response.status === 401 && !endpoint.includes("/auth/")) {
      clearCsrfToken();
      redirectToLoginFromBrowser();
    }
    const text = await response.text();
    const { message, code } = parseErrorPayload(text, response.status);
    throw new ApiError(message, response.status, code);
  }

  if (response.status === 204) return {} as T;

  const text = await response.text();
  if (!text) return {} as T;
  return JSON.parse(text) as T;
}

export interface LoginResponse {
  access_token?: string;
  refresh_token?: string | null;
  token_type?: string;
  session_id?: string;
  mfa_required?: boolean;
  challenge_token?: string;
  methods?: string[];
  csrf_token?: string;
}

export const api = {
  auth: {
    login: (data: { email: string; password: string; tenant_slug?: string; device_fingerprint?: string }) =>
      request<LoginResponse>("/api/v1/identity/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    me: () => request("/api/v1/identity/auth/me"),
    logout: () => request("/api/v1/identity/auth/logout", { method: "POST" }),
    refresh: () =>
      request<{ access_token: string }>("/api/v1/identity/auth/refresh", {
        method: "POST",
        body: JSON.stringify({}),
      }),
  },
  health: () => request<{ status: string; version?: string }>("/health"),
};

export { ApiError, request };
