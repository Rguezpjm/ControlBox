export const APP_BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH || "").replace(/\/$/, "");

export function withBasePath(path: string): string {
  if (!APP_BASE_PATH) {
    return path.startsWith("/") ? path : `/${path}`;
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${APP_BASE_PATH}${normalized}`;
}

/** Archivos en `/public` para `<img>`, favicons y HTML estático. No usar con `next/image` (importar el PNG). */
export function publicAsset(path: string): string {
  return withBasePath(path);
}
