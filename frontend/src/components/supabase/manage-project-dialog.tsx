"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Loader2,
  Trash2,
  KeyRound,
  Pause,
  Play,
  Copy,
  Check,
  ExternalLink,
  Archive,
  Shield,
  Radio,
  Database,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  supabaseApi,
  type SupabaseProject,
  type SupabaseCredentials,
  type SupabaseUsage,
  type SupabaseSchema,
  type SupabaseBucket,
  type SupabaseRealtimeChannel,
  type SupabaseRlsPolicy,
} from "@/lib/supabase";
import { ApiError } from "@/lib/api-client";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    suspended: "stopped",
    pending: "pending",
    error: "error",
    deleting: "pending",
  };
  return map[status] || "pending";
}

interface ManageSupabaseProjectDialogProps {
  project: SupabaseProject | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function ManageSupabaseProjectDialog({
  project,
  open,
  onOpenChange,
  onUpdated,
}: ManageSupabaseProjectDialogProps) {
  const [credentials, setCredentials] = useState<SupabaseCredentials | null>(null);
  const [usage, setUsage] = useState<SupabaseUsage | null>(null);
  const [schemas, setSchemas] = useState<SupabaseSchema[]>([]);
  const [buckets, setBuckets] = useState<SupabaseBucket[]>([]);
  const [channels, setChannels] = useState<SupabaseRealtimeChannel[]>([]);
  const [policies, setPolicies] = useState<SupabaseRlsPolicy[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const [newSchema, setNewSchema] = useState("");
  const [newBucket, setNewBucket] = useState("");
  const [newChannelName, setNewChannelName] = useState("");
  const [newChannelTable, setNewChannelTable] = useState("");
  const [newPolicyName, setNewPolicyName] = useState("");
  const [newPolicyTable, setNewPolicyTable] = useState("");

  const loadData = useCallback(async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      const [creds, usageData, schemasData, bucketsData, channelsData, policiesData] =
        await Promise.all([
          supabaseApi.getCredentials(project.id),
          supabaseApi.getUsage(project.id),
          supabaseApi.listSchemas(project.id),
          supabaseApi.listBuckets(project.id),
          supabaseApi.listRealtimeChannels(project.id),
          supabaseApi.listRlsPolicies(project.id),
        ]);
      setCredentials(creds);
      setUsage(usageData);
      setSchemas(schemasData);
      setBuckets(bucketsData);
      setChannels(channelsData);
      setPolicies(policiesData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [project]);

  useEffect(() => {
    if (open && project) loadData();
  }, [open, project, loadData]);

  function copyText(text: string, key: string) {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  }

  async function handleSuspend() {
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.suspendProject(project.id);
      onUpdated();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to suspend");
    } finally {
      setLoading(false);
    }
  }

  async function handleResume() {
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.resumeProject(project.id);
      onUpdated();
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to resume");
    } finally {
      setLoading(false);
    }
  }

  async function handleRotateKeys() {
    if (!project) return;
    setLoading(true);
    try {
      const creds = await supabaseApi.rotateKeys(project.id);
      setCredentials(creds);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to rotate keys");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!project || !confirm("Delete this Supabase project and all resources?")) return;
    setLoading(true);
    try {
      await supabaseApi.deleteProject(project.id);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateSchema(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.createSchema(project.id, newSchema);
      setNewSchema("");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create schema");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBucket(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.createBucket(project.id, newBucket);
      setNewBucket("");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create bucket");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateChannel(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.createRealtimeChannel(project.id, {
        name: newChannelName,
        table_name: newChannelTable,
      });
      setNewChannelName("");
      setNewChannelTable("");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create channel");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreatePolicy(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.createRlsPolicy(project.id, {
        name: newPolicyName,
        table_name: newPolicyTable,
      });
      setNewPolicyName("");
      setNewPolicyTable("");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create policy");
    } finally {
      setLoading(false);
    }
  }

  if (!project) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {project.name}
            <StatusBadge status={mapStatus(project.status)} />
          </DialogTitle>
          <DialogDescription>
            {project.project_ref} · Global Supabase Self-Hosted
          </DialogDescription>
        </DialogHeader>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Tabs defaultValue="credentials">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="credentials">Credentials</TabsTrigger>
            <TabsTrigger value="usage">Usage</TabsTrigger>
            <TabsTrigger value="storage">Storage</TabsTrigger>
            <TabsTrigger value="realtime">Realtime</TabsTrigger>
            <TabsTrigger value="rls">RLS</TabsTrigger>
          </TabsList>

          <TabsContent value="credentials" className="space-y-4 mt-4">
            {loading && !credentials ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : credentials ? (
              <div className="space-y-3 text-sm">
                {[
                  { label: "Database", value: credentials.database_name, key: "db" },
                  { label: "User", value: credentials.database_user, key: "user" },
                  { label: "Password", value: credentials.database_password, key: "pass", secret: true, toggle: true },
                  { label: "Connection URL", value: credentials.connection_url, key: "url", mono: true },
                  { label: "Anon Key", value: credentials.anon_key, key: "anon", mono: true },
                  { label: "Service Role Key", value: credentials.service_role_key, key: "service", mono: true },
                  { label: "API URL", value: credentials.api_url, key: "api" },
                ].map((field) => (
                  <div key={field.key} className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground mb-1">{field.label}</p>
                    <div className="flex items-start gap-2">
                      <span className={`flex-1 break-all ${field.mono ? "font-mono text-xs" : "font-medium"}`}>
                        {field.secret && !showPassword ? "••••••••••••" : field.value}
                      </span>
                      {field.toggle && (
                        <Button size="sm" variant="ghost" onClick={() => setShowPassword(!showPassword)}>
                          {showPassword ? "Hide" : "Show"}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyText(field.value, field.key)}
                      >
                        {copied === field.key ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                      </Button>
                    </div>
                  </div>
                ))}
                <div className="flex gap-2 pt-2">
                  <Button size="sm" variant="outline" onClick={handleRotateKeys} disabled={loading}>
                    <KeyRound className="h-4 w-4" />
                    Rotate Keys
                  </Button>
                  {credentials.studio_url && (
                    <Button size="sm" variant="outline" asChild>
                      <a href={credentials.studio_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4" />
                        Studio
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            ) : null}
          </TabsContent>

          <TabsContent value="usage" className="mt-4">
            {usage ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {[
                  { label: "Database Size", value: formatBytes(usage.database_size_mb * 1024 * 1024) },
                  { label: "Storage Used", value: formatBytes(usage.storage_used_mb * 1024 * 1024) },
                  { label: "Buckets", value: usage.buckets_count },
                  { label: "Schemas", value: usage.schemas_count },
                  { label: "Realtime Channels", value: usage.realtime_channels_count },
                  { label: "RLS Policies", value: usage.rls_policies_count },
                ].map((item) => (
                  <div key={item.label} className="rounded-lg bg-muted/50 p-3 text-center">
                    <p className="text-xs text-muted-foreground">{item.label}</p>
                    <p className="text-lg font-semibold">{item.value}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            )}
          </TabsContent>

          <TabsContent value="storage" className="space-y-4 mt-4">
            <form onSubmit={handleCreateBucket} className="flex gap-2">
              <Input
                placeholder="bucket-name"
                value={newBucket}
                onChange={(e) => setNewBucket(e.target.value)}
                required
              />
              <Button type="submit" size="sm" disabled={loading}>
                <Archive className="h-4 w-4" />
                Add Bucket
              </Button>
            </form>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Database className="h-3 w-3" /> Schemas
              </p>
              {schemas.map((s) => (
                <div key={s.id} className="flex justify-between rounded border p-2 text-sm">
                  <span>{s.name}{s.is_default ? " (default)" : ""}</span>
                </div>
              ))}
            </div>
            <form onSubmit={handleCreateSchema} className="flex gap-2">
              <Input placeholder="schema_name" value={newSchema} onChange={(e) => setNewSchema(e.target.value)} />
              <Button type="submit" size="sm" disabled={loading}>Add Schema</Button>
            </form>
            <div className="space-y-2">
              {buckets.map((b) => (
                <div key={b.id} className="flex justify-between rounded border p-2 text-sm">
                  <span>{b.name} {b.public && "(public)"}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => project && supabaseApi.deleteBucket(project.id, b.id).then(loadData)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
              {buckets.length === 0 && <p className="text-sm text-muted-foreground">No buckets yet</p>}
            </div>
          </TabsContent>

          <TabsContent value="realtime" className="space-y-4 mt-4">
            <form onSubmit={handleCreateChannel} className="flex flex-wrap gap-2">
              <Input placeholder="channel name" value={newChannelName} onChange={(e) => setNewChannelName(e.target.value)} required />
              <Input placeholder="table name" value={newChannelTable} onChange={(e) => setNewChannelTable(e.target.value)} required />
              <Button type="submit" size="sm" disabled={loading}>
                <Radio className="h-4 w-4" /> Add
              </Button>
            </form>
            {channels.map((c) => (
              <div key={c.id} className="flex justify-between rounded border p-2 text-sm">
                <span>{c.name} → {c.schema_name}.{c.table_name}</span>
                <Button size="sm" variant="ghost" onClick={() => supabaseApi.deleteRealtimeChannel(project.id, c.id).then(loadData)}>
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
            {channels.length === 0 && <p className="text-sm text-muted-foreground">No channels yet</p>}
          </TabsContent>

          <TabsContent value="rls" className="space-y-4 mt-4">
            <form onSubmit={handleCreatePolicy} className="flex flex-wrap gap-2">
              <Input placeholder="policy name" value={newPolicyName} onChange={(e) => setNewPolicyName(e.target.value)} required />
              <Input placeholder="table name" value={newPolicyTable} onChange={(e) => setNewPolicyTable(e.target.value)} required />
              <Button type="submit" size="sm" disabled={loading}>
                <Shield className="h-4 w-4" /> Add
              </Button>
            </form>
            {policies.map((p) => (
              <div key={p.id} className="rounded border p-2 text-sm">
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-muted-foreground">{p.schema_name}.{p.table_name} · {p.action}</p>
                <Button size="sm" variant="ghost" className="mt-1" onClick={() => supabaseApi.deleteRlsPolicy(project.id, p.id).then(loadData)}>
                  <Trash2 className="h-3 w-3" /> Remove
                </Button>
              </div>
            ))}
            {policies.length === 0 && <p className="text-sm text-muted-foreground">No policies yet</p>}
          </TabsContent>
        </Tabs>

        <div className="flex gap-2 pt-4 border-t">
          {project.status === "active" ? (
            <Button variant="outline" size="sm" onClick={handleSuspend} disabled={loading}>
              <Pause className="h-4 w-4" /> Suspend
            </Button>
          ) : project.status === "suspended" ? (
            <Button variant="outline" size="sm" onClick={handleResume} disabled={loading}>
              <Play className="h-4 w-4" /> Resume
            </Button>
          ) : null}
          <Button variant="destructive" size="sm" onClick={handleDelete} disabled={loading}>
            <Trash2 className="h-4 w-4" /> Delete Project
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
