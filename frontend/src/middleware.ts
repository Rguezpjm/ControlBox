import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { APP_BASE_PATH } from "@/lib/base-path";

const PUBLIC_PATHS = ["/login", "/register", "/accept-invite"];
/** Legacy default path; redirect to root when panel runs without basePath. */
const LEGACY_PANEL_PREFIX = "/ControlBox_Panel";

function stripBasePath(pathname: string): string {
  if (!APP_BASE_PATH || !pathname.startsWith(APP_BASE_PATH)) {
    return pathname;
  }
  const stripped = pathname.slice(APP_BASE_PATH.length) || "/";
  return stripped.startsWith("/") ? stripped : `/${stripped}`;
}

function base64UrlDecode(input: string): string {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padLength = (4 - (normalized.length % 4)) % 4;
  const padded = normalized + "=".repeat(padLength);
  return atob(padded);
}

function isExpiredJwt(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return true;
    const payloadRaw = base64UrlDecode(parts[1]);
    const payload = JSON.parse(payloadRaw) as { exp?: number };
    if (typeof payload.exp !== "number") return true;
    const now = Math.floor(Date.now() / 1000);
    return payload.exp <= now;
  } catch {
    return true;
  }
}

function redirectRelative(request: NextRequest, relativePath: string): NextResponse {
  const target = relativePath.startsWith("/") ? relativePath : `/${relativePath}`;
  const url = request.nextUrl.clone();
  url.pathname = target;
  url.search = "";
  const [pathnameOnly, search = ""] = target.split("?");
  return new NextResponse(null, {
    status: 307,
    headers: {
      Location: `${pathnameOnly}${search ? `?${search}` : ""}`,
    },
  });
}

export function middleware(request: NextRequest) {
  const rawPath = request.nextUrl.pathname;
  const duplicatedPrefix = APP_BASE_PATH ? `${APP_BASE_PATH}${APP_BASE_PATH}` : "";

  if (
    duplicatedPrefix &&
    (rawPath === duplicatedPrefix || rawPath.startsWith(`${duplicatedPrefix}/`))
  ) {
    const fixedPath = rawPath.slice(APP_BASE_PATH.length) || "/";
    return redirectRelative(request, fixedPath);
  }

  if (
    !APP_BASE_PATH &&
    (rawPath === LEGACY_PANEL_PREFIX || rawPath.startsWith(`${LEGACY_PANEL_PREFIX}/`))
  ) {
    const fixedPath = rawPath.slice(LEGACY_PANEL_PREFIX.length) || "/";
    return redirectRelative(request, fixedPath);
  }

  const pathname = stripBasePath(rawPath);

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  if (pathname.startsWith("/_next") || pathname.startsWith("/api") || pathname.includes(".")) {
    return NextResponse.next();
  }

  const accessCookie = request.cookies.get("cb_access")?.value;
  if (!accessCookie || isExpiredJwt(accessCookie)) {
    const redirectTarget = encodeURIComponent(pathname);
    return redirectRelative(request, `/login?redirect=${redirectTarget}`);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|logo.png).*)"],
};
