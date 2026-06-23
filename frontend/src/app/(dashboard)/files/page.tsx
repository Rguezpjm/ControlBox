"use client";

import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import {
  FolderOpen,
  File,
  Upload,
  FolderPlus,
  Pencil,
  Trash2,
  Archive,
  ArchiveRestore,
  Shield,
  Download,
  ChevronRight,
  Home,
  RefreshCw,
  FileCode,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TableSkeleton } from "@/components/skeletons";
import { filesApi, type FileEntry, type BrowseResult } from "@/lib/files";
import { formatBytes } from "@/lib/utils";
import { ApiError } from "@/lib/api-client";

function FilesContent() {
  const [browse, setBrowse] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editorPath, setEditorPath] = useState("");
  const [editorContent, setEditorContent] = useState("");
  const [editorSaving, setEditorSaving] = useState(false);

  const [mkdirOpen, setMkdirOpen] = useState(false);
  const [newDirName, setNewDirName] = useState("");
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameName, setRenameName] = useState("");
  const [renameTarget, setRenameTarget] = useState("");
  const [permOpen, setPermOpen] = useState(false);
  const [permPath, setPermPath] = useState("");
  const [permMode, setPermMode] = useState("0755");

  const currentPath = browse?.path ?? "";

  const load = useCallback(async (path = "") => {
    setLoading(true);
    setError(null);
    setSelected(new Set());
    try {
      const data = await filesApi.browse(path);
      setBrowse(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load files");
      setBrowse(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function toggleSelect(path: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function openEntry(entry: FileEntry) {
    if (entry.is_dir) load(entry.path);
    else if (entry.editable) openEditor(entry.path);
    else filesApi.download(entry.path, entry.name);
  }

  async function openEditor(path: string) {
    try {
      const data = await filesApi.readContent(path);
      setEditorPath(path);
      setEditorContent(data.content);
      setEditorOpen(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot open file");
    }
  }

  async function saveEditor() {
    setEditorSaving(true);
    try {
      await filesApi.writeContent(editorPath, editorContent);
      setEditorOpen(false);
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setEditorSaving(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    if (!fileList?.length) return;
    try {
      for (const file of Array.from(fileList)) {
        await filesApi.upload(currentPath, file);
      }
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleMkdir(e: React.FormEvent) {
    e.preventDefault();
    const fullPath = currentPath ? `${currentPath}/${newDirName}` : newDirName;
    try {
      await filesApi.mkdir(fullPath);
      setMkdirOpen(false);
      setNewDirName("");
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create folder");
    }
  }

  async function handleRename(e: React.FormEvent) {
    e.preventDefault();
    try {
      await filesApi.rename(renameTarget, renameName);
      setRenameOpen(false);
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rename failed");
    }
  }

  async function handleDelete() {
    if (!selected.size || !confirm(`Delete ${selected.size} item(s)?`)) return;
    try {
      for (const path of selected) {
        await filesApi.delete(path);
      }
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function handleCompress() {
    if (!selected.size) return;
    const name = prompt("Archive name:", "archive.zip") || "archive.zip";
    try {
      await filesApi.compress(Array.from(selected), name, currentPath);
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Compress failed");
    }
  }

  async function handleExtract() {
    const zip = Array.from(selected).find((p) => p.endsWith(".zip"));
    if (!zip) {
      setError("Select a .zip file to extract");
      return;
    }
    try {
      await filesApi.extract(zip, currentPath);
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Extract failed");
    }
  }

  async function openPermissions(path: string) {
    try {
      const data = await filesApi.getPermissions(path);
      setPermPath(path);
      setPermMode(data.mode.replace("0o", "0"));
      setPermOpen(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to read permissions");
    }
  }

  async function savePermissions(e: React.FormEvent) {
    e.preventDefault();
    try {
      await filesApi.setPermissions(permPath, permMode);
      setPermOpen(false);
      await load(currentPath);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to set permissions");
    }
  }

  const breadcrumbs = currentPath ? currentPath.split("/") : [];

  if (loading && !browse) return <TableSkeleton />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="File Manager"
        description="Browse, edit and manage your site files"
      />

      {error && (
        <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
      )}

      <div className="flex flex-wrap gap-2 items-center">
        <Button size="sm" variant="outline" onClick={() => load(currentPath)}>
          <RefreshCw className="h-4 w-4" />
        </Button>
        <Button size="sm" onClick={() => fileInputRef.current?.click()}>
          <Upload className="h-4 w-4" /> Upload
        </Button>
        <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleUpload} />
        <Button size="sm" variant="outline" onClick={() => setMkdirOpen(true)}>
          <FolderPlus className="h-4 w-4" /> New Folder
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={selected.size !== 1}
          onClick={() => {
            const path = Array.from(selected)[0];
            const entry = browse?.entries.find((e) => e.path === path);
            if (entry) {
              setRenameTarget(path);
              setRenameName(entry.name);
              setRenameOpen(true);
            }
          }}
        >
          <Pencil className="h-4 w-4" /> Rename
        </Button>
        <Button size="sm" variant="outline" disabled={!selected.size} onClick={handleCompress}>
          <Archive className="h-4 w-4" /> Compress
        </Button>
        <Button size="sm" variant="outline" disabled={!selected.size} onClick={handleExtract}>
          <ArchiveRestore className="h-4 w-4" /> Extract
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={selected.size !== 1}
          onClick={() => openPermissions(Array.from(selected)[0])}
        >
          <Shield className="h-4 w-4" /> Permissions
        </Button>
        <Button size="sm" variant="destructive" disabled={!selected.size} onClick={handleDelete}>
          <Trash2 className="h-4 w-4" /> Delete
        </Button>
      </div>

      <div className="flex items-center gap-1 text-sm text-muted-foreground flex-wrap">
        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => load("")}>
          <Home className="h-3 w-3" />
        </Button>
        {breadcrumbs.map((part, i) => {
          const path = breadcrumbs.slice(0, i + 1).join("/");
          const label = browse?.path_labels?.[path] ?? part;
          return (
            <span key={path} className="flex items-center gap-1">
              <ChevronRight className="h-3 w-3" />
              <button
                type="button"
                className="hover:text-foreground hover:underline"
                onClick={() => load(path)}
              >
                {label}
              </button>
            </span>
          );
        })}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="w-10 px-3 py-2" />
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">Name</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground hidden sm:table-cell">Size</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground hidden md:table-cell">Permissions</th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {browse?.parent != null && (
                  <tr
                    className="border-b hover:bg-muted/30 cursor-pointer"
                    onClick={() => load(browse.parent || "")}
                  >
                    <td className="px-3 py-2" />
                    <td className="px-3 py-2 font-medium text-muted-foreground">..</td>
                    <td className="hidden sm:table-cell" />
                    <td className="hidden md:table-cell" />
                    <td />
                  </tr>
                )}
                {browse?.entries.map((entry) => (
                  <tr key={entry.path} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border"
                        checked={selected.has(entry.path)}
                        onChange={() => toggleSelect(entry.path)}
                      />
                    </td>
                    <td
                      className="px-3 py-2 cursor-pointer"
                      onClick={() => openEntry(entry)}
                    >
                      <div className="flex items-center gap-2">
                        {entry.is_dir ? (
                          <FolderOpen className="h-4 w-4 text-amber-500" />
                        ) : entry.editable ? (
                          <FileCode className="h-4 w-4 text-blue-500" />
                        ) : (
                          <File className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="font-medium">{entry.display_name || entry.name}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 hidden sm:table-cell text-muted-foreground text-xs">
                      {entry.is_dir ? "—" : formatBytes(entry.size)}
                    </td>
                    <td className="px-3 py-2 hidden md:table-cell font-mono text-xs text-muted-foreground">
                      {entry.permissions}
                    </td>
                    <td className="px-3 py-2 text-right space-x-1">
                      {!entry.is_dir && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => filesApi.download(entry.path, entry.name)}
                        >
                          <Download className="h-3 w-3" />
                        </Button>
                      )}
                      {entry.editable && (
                        <Button variant="ghost" size="sm" onClick={() => openEditor(entry.path)}>
                          <FileCode className="h-3 w-3" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
                {browse?.entries.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-12 text-center text-muted-foreground">
                      Empty directory
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">{editorPath}</DialogTitle>
          </DialogHeader>
          <textarea
            className="flex-1 min-h-[400px] w-full rounded-md border bg-muted/30 p-4 font-mono text-xs leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-ring"
            value={editorContent}
            onChange={(e) => setEditorContent(e.target.value)}
            spellCheck={false}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorOpen(false)}>Cancel</Button>
            <Button onClick={saveEditor} disabled={editorSaving}>
              {editorSaving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={mkdirOpen} onOpenChange={setMkdirOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Folder</DialogTitle></DialogHeader>
          <form onSubmit={handleMkdir} className="space-y-4">
            <div className="space-y-2">
              <Label>Folder name</Label>
              <Input value={newDirName} onChange={(e) => setNewDirName(e.target.value)} required />
            </div>
            <DialogFooter><Button type="submit">Create</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Rename</DialogTitle></DialogHeader>
          <form onSubmit={handleRename} className="space-y-4">
            <div className="space-y-2">
              <Label>New name</Label>
              <Input value={renameName} onChange={(e) => setRenameName(e.target.value)} required />
            </div>
            <DialogFooter><Button type="submit">Rename</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={permOpen} onOpenChange={setPermOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Permissions</DialogTitle></DialogHeader>
          <form onSubmit={savePermissions} className="space-y-4">
            <p className="text-xs font-mono text-muted-foreground">{permPath}</p>
            <div className="space-y-2">
              <Label>Mode (octal)</Label>
              <Input
                value={permMode}
                onChange={(e) => setPermMode(e.target.value)}
                placeholder="0755"
                className="font-mono"
              />
            </div>
            <DialogFooter><Button type="submit">Apply</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function FilesPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <FilesContent />
    </Suspense>
  );
}
