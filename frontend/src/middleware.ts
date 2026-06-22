import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { APP_BASE_PATH, withBasePath } from "@/lib/base-path";

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

export function middleware(request: NextRequest) {
  const rawPath = request.nextUrl.pathname;

  if (
    !APP_BASE_PATH &&
    (rawPath === LEGACY_PANEL_PREFIX || rawPath.startsWith(`${LEGACY_PANEL_PREFIX}/`))
  ) {
    const url = request.nextUrl.clone();
    url.pathname = rawPath.slice(LEGACY_PANEL_PREFIX.length) || "/";
    return NextResponse.redirect(url);
  }

  const pathname = stripBasePath(rawPath);

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  if (pathname.startsWith("/_next") || pathname.startsWith("/api") || pathname.includes(".")) {
    return NextResponse.next();
  }

  const accessCookie = request.cookies.get("cb_access")?.value;
  if (!accessCookie) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = withBasePath("/login");
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|logo.png).*)"],
};
