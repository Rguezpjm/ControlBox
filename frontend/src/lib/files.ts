import { ensureCsrfToken, getAuthHeaders } from "@/lib/auth";
import { ApiError, request } from "@/lib/api-client";
import { API_BASE } from "@/lib/api-base";

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  permissions: string;
  modified_at: string;
  extension: string | null;
  editable: boolean;
}

export interface BrowseResult {
  path: string;
  parent: string | null;
  entries: FileEntry[];
}

export interface FileContent {
  path: string;
  content: string;
  extension: string;
}

export interface FilePermissions {
  path: string;
  mode: string;
  readable: boolean;
  writable: boolean;
  executable: boolean;
}

function authRequest<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  return request<T>(endpoint, init);
}

export const filesApi = {
  browse: (path = "") =>
    authRequest<BrowseResult>(`/api/v1/files/browse?path=${encodeURIComponent(path)}`),
  readContent: (path: string) =>
    authRequest<FileContent>(`/api/v1/files/content?path=${encodeURIComponent(path)}`),
  writeContent: (path: string, content: string) =>
    authRequest<FileEntry>("/api/v1/files/content", {
      method: "PUT",
      body: JSON.stringify({ path, content }),
    }),
  upload: async (directory: string, file: File) => {
    await ensureCsrfToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(
      `${API_BASE}/api/v1/files/upload?directory=${encodeURIComponent(directory)}`,
      {
        method: "POST",
        credentials: "include",
        headers: getAuthHeaders(),
        body: form,
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.error || "Upload failed", res.status);
    }
    return res.json() as Promise<FileEntry>;
  },
  downloadUrl: (path: string) =>
    `${API_BASE}/api/v1/files/download?path=${encodeURIComponent(path)}`,
  download: async (path: string, filename: string) => {
    await ensureCsrfToken();
    const res = await fetch(`${API_BASE}/api/v1/files/download?path=${encodeURIComponent(path)}`, {
      credentials: "include",
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new ApiError("Download failed", res.status);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
  mkdir: (path: string) =>
    authRequest<FileEntry>("/api/v1/files/mkdir", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  rename: (path: string, new_name: string) =>
    authRequest<FileEntry>("/api/v1/files/rename", {
      method: "POST",
      body: JSON.stringify({ path, new_name }),
    }),
  delete: (path: string) =>
    authRequest<void>(`/api/v1/files?path=${encodeURIComponent(path)}`, { method: "DELETE" }),
  compress: (paths: string[], archive_name: string, dest_dir = "") =>
    authRequest<FileEntry>("/api/v1/files/compress", {
      method: "POST",
      body: JSON.stringify({ paths, archive_name, dest_dir }),
    }),
  extract: (archive_path: string, dest_dir = "") =>
    authRequest<BrowseResult>("/api/v1/files/extract", {
      method: "POST",
      body: JSON.stringify({ archive_path, dest_dir }),
    }),
  getPermissions: (path: string) =>
    authRequest<FilePermissions>(`/api/v1/files/permissions?path=${encodeURIComponent(path)}`),
  setPermissions: (path: string, mode: string) =>
    authRequest<FilePermissions>("/api/v1/files/permissions", {
      method: "PUT",
      body: JSON.stringify({ path, mode }),
    }),
};

export { ApiError };
