import { APP_BASE_PATH } from "./base-path";

/** Browser calls go through the panel proxy (/api → api:8000), respecting basePath. */
const explicitApiUrl = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
export const API_BASE = explicitApiUrl || APP_BASE_PATH;
