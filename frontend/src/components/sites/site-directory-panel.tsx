"use client";

import { useMemo, useState } from "react";
import { FolderOpen, Loader2, Plus, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  siteModificationApi,
  type SiteModification,
  type SiteSettings,
  type SiteType,
  type SubdirectoryBinding,
} from "@/lib/site-modification";
import { SiteDirectoryPickerDialog } from "@/components/sites/site-directory-picker-dialog";
import { ApiError } from "@/lib/api-client";

function pickerPathToDocumentRoot(
  sitePath: string,
  siteFilesPath: string,
  pickedPath: string
): string {
  const base = siteFilesPath.replace(/\\/g, "/").replace(/\/$/, "");
  const pick = pickedPath.replace(/\\/g, "/").replace(/\/$/, "");
  const root = sitePath.replace(/\\/g, "/").replace(/\/$/, "");
  if (!base) return `${root}/${pick}`.replace(/\/+/g, "/");
  if (pick === base) return root;
  if (pick.startsWith(`${base}/`)) {
    return `${root}/${pick.slice(base.length + 1)}`.replace(/\/+/g, "/");
  }
  return pick;
}

function DashedRule() {
  return <div className="border-t border-dashed border-border/80" />;
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-muted-foreground">{children}</p>;
}

interface SiteDirectoryPanelProps {
  siteType: SiteType;
  siteId: string;
  data: SiteModification;
  onUpdated: (mod: SiteModification) => void;
  onError: (message: string | null) => void;
}

export function SiteDirectoryPanel({
  siteType,
  siteId,
  data,
  onUpdated,
  onError,
}: SiteDirectoryPanelProps) {
  const [siteDirectory, setSiteDirectory] = useState(data.document_root);
  const [runningDirectory, setRunningDirectory] = useState(data.running_directory || "/");
  const [openBasedir, setOpenBasedir] = useState(data.open_basedir_enabled !== false);
  const [logsEnabled, setLogsEnabled] = useState(data.logs_enabled !== false);
  const [passwordAccess, setPasswordAccess] = useState(!!data.settings.limit_access_enabled);
  const [authUser, setAuthUser] = useState(data.settings.limit_access_user || "admin");
  const [authPassword, setAuthPassword] = useState("");
  const [bindings, setBindings] = useState<SubdirectoryBinding[]>(
    data.subdirectory_bindings?.length
      ? data.subdirectory_bindings
      : data.settings.subdirectory_bindings || []
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  const [savingField, setSavingField] = useState<string | null>(null);

  const runningOptions = useMemo(() => {
    const options = data.running_directory_options?.length
      ? data.running_directory_options
      : ["/"];
    return Array.from(new Set(options));
  }, [data.running_directory_options]);

  const pickerInitialPath = data.site_files_path || "";

  async function savePatch(
    field: string,
    patch: {
      settings?: SiteSettings;
      document_root?: string;
      logs_enabled?: boolean;
    }
  ) {
    setSavingField(field);
    onError(null);
    try {
      const mod = await siteModificationApi.update(siteType, siteId, patch);
      onUpdated(mod);
      setSiteDirectory(mod.document_root);
      setRunningDirectory(mod.running_directory || "/");
      setOpenBasedir(mod.open_basedir_enabled !== false);
      setLogsEnabled(mod.logs_enabled !== false);
      setPasswordAccess(!!mod.settings.limit_access_enabled);
      setAuthUser(mod.settings.limit_access_user || "admin");
      setBindings(mod.subdirectory_bindings || mod.settings.subdirectory_bindings || []);
      if (patch.settings && !("limit_access_password" in patch.settings)) {
        setAuthPassword("");
      }
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Failed to save directory settings");
    } finally {
      setSavingField(null);
    }
  }

  return (
    <div className="space-y-6">
      <Tabs defaultValue="site-directory" className="w-full">
        <TabsList className="h-auto w-full justify-start rounded-none border-b bg-transparent p-0">
          <TabsTrigger
            value="site-directory"
            className="rounded-none border-b-2 border-transparent px-0 pb-2 mr-6 data-[state=active]:border-emerald-600 data-[state=active]:bg-transparent data-[state=active]:text-emerald-600 data-[state=active]:shadow-none"
          >
            Site directory
          </TabsTrigger>
          <TabsTrigger
            value="subdirectory-binding"
            className="rounded-none border-b-2 border-transparent px-0 pb-2 data-[state=active]:border-emerald-600 data-[state=active]:bg-transparent data-[state=active]:text-emerald-600 data-[state=active]:shadow-none"
          >
            Subdirectory binding
          </TabsTrigger>
        </TabsList>

        <TabsContent value="site-directory" className="mt-6 space-y-6">
          <div className="grid gap-3 md:grid-cols-[140px_1fr_auto] md:items-start">
            <Label className="pt-2.5">Site directory</Label>
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input
                  value={siteDirectory}
                  onChange={(e) => setSiteDirectory(e.target.value)}
                  className="font-mono text-xs"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => setPickerOpen(true)}
                  title="Browse folders"
                >
                  <FolderOpen className="h-4 w-4" />
                </Button>
              </div>
              <FieldHint>
                Some programs need to specify a secondary directory as the working directory.
              </FieldHint>
            </div>
            <Button
              className="bg-emerald-600 hover:bg-emerald-600/90"
              disabled={savingField === "site-directory"}
              onClick={() => savePatch("site-directory", { document_root: siteDirectory })}
            >
              {savingField === "site-directory" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save
            </Button>
          </div>

          <div className="grid gap-3 md:grid-cols-[140px_1fr_auto] md:items-start">
            <Label className="pt-2.5">Running directory</Label>
            <div className="space-y-2">
              <Select value={runningDirectory} onValueChange={setRunningDirectory}>
                <SelectTrigger>
                  <SelectValue placeholder="/" />
                </SelectTrigger>
                <SelectContent>
                  {runningOptions.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldHint>
                Select your working directory and click Save, e.g. ThinkPHP5, Laravel.
              </FieldHint>
            </div>
            <Button
              className="bg-emerald-600 hover:bg-emerald-600/90"
              disabled={savingField === "running-directory"}
              onClick={() =>
                savePatch("running-directory", {
                  settings: { running_directory: runningDirectory },
                })
              }
            >
              {savingField === "running-directory" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save
            </Button>
          </div>

          <DashedRule />

          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label>Anti-XSS attack</Label>
                <FieldHint>(Base directory limit) (open basedir)</FieldHint>
              </div>
              <Switch
                checked={openBasedir}
                onCheckedChange={(checked) => {
                  setOpenBasedir(checked);
                  void savePatch("open-basedir", {
                    settings: { open_basedir_enabled: checked },
                  });
                }}
                disabled={savingField === "open-basedir"}
              />
            </div>

            <div className="flex items-center justify-between gap-4">
              <Label>Write access log</Label>
              <Switch
                checked={logsEnabled}
                onCheckedChange={(checked) => {
                  setLogsEnabled(checked);
                  void savePatch("logs-enabled", {
                    logs_enabled: checked,
                    settings: { logs_enabled: checked },
                  });
                }}
                disabled={savingField === "logs-enabled"}
              />
            </div>
          </div>

          <DashedRule />

          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <Label>Password access</Label>
              <Switch
                checked={passwordAccess}
                onCheckedChange={(checked) => {
                  setPasswordAccess(checked);
                  void savePatch("password-access", {
                    settings: { limit_access_enabled: checked },
                  });
                }}
                disabled={savingField === "password-access"}
              />
            </div>

            {passwordAccess ? (
              <div className="grid gap-3 rounded-lg border bg-muted/20 p-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Auth user</Label>
                  <Input value={authUser} onChange={(e) => setAuthUser(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Password</Label>
                  <Input
                    type="password"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    placeholder="Enter new password"
                  />
                </div>
                <div className="md:col-span-2 flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={savingField === "password-credentials" || !authPassword}
                    onClick={() =>
                      savePatch("password-credentials", {
                        settings: {
                          limit_access_enabled: true,
                          limit_access_user: authUser,
                          limit_access_password: authPassword,
                        },
                      })
                    }
                  >
                    {savingField === "password-credentials" ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    Save credentials
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </TabsContent>

        <TabsContent value="subdirectory-binding" className="mt-6 space-y-4">
          <FieldHint>
            Bind additional domains to subdirectories under the site folder.
          </FieldHint>

          <div className="space-y-3">
            {bindings.map((binding, index) => (
              <div key={`${binding.domain}-${index}`} className="grid gap-2 md:grid-cols-[1fr_180px_auto]">
                <Input
                  placeholder="sub.example.com"
                  value={binding.domain}
                  onChange={(e) => {
                    const next = [...bindings];
                    next[index] = { ...next[index], domain: e.target.value };
                    setBindings(next);
                  }}
                />
                <Select
                  value={binding.directory || "/"}
                  onValueChange={(value) => {
                    const next = [...bindings];
                    next[index] = { ...next[index], directory: value };
                    setBindings(next);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {runningOptions.map((option) => (
                      <SelectItem key={`bind-${option}`} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => setBindings(bindings.filter((_, i) => i !== index))}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setBindings([...bindings, { domain: "", directory: "/" }])}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add binding
            </Button>
            <Button
              className="bg-emerald-600 hover:bg-emerald-600/90"
              size="sm"
              disabled={savingField === "subdirectory-bindings"}
              onClick={() =>
                savePatch("subdirectory-bindings", {
                  settings: { subdirectory_bindings: bindings.filter((b) => b.domain.trim()) },
                })
              }
            >
              {savingField === "subdirectory-bindings" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save bindings
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      <SiteDirectoryPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        initialPath={pickerInitialPath}
        onSelect={(path) => {
          const absolute = pickerPathToDocumentRoot(
            data.site_path || data.document_root,
            data.site_files_path || "",
            path
          );
          setSiteDirectory(absolute);
        }}
      />
    </div>
  );
}
