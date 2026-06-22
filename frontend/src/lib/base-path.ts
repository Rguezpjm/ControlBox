export const APP_BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH || "").replace(/\/$/, "");

export function withBasePath(path: string): string {
  if (!APP_BASE_PATH) {
    return path.startsWith("/") ? path : `/${path}`;
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${APP_BASE_PATH}${normalized}`;
}
