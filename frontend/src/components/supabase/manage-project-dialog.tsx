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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  applyBucketPreset,
  applySchemaPreset,
  SupabaseStorageTab,
} from "@/components/supabase/storage-tab";
import {
  BUCKET_PRESET_CUSTOM,
  getBucketPreset,
  SCHEMA_PRESET_CUSTOM,
} from "@/components/supabase/storage-presets";
import { SupabaseRealtimeTab } from "@/components/supabase/realtime-tab";
import {
  applyRealtimePreset,
  getRealtimePreset,
  REALTIME_PRESET_CUSTOM,
} from "@/components/supabase/realtime-presets";
import { SupabaseRlsTab } from "@/components/supabase/rls-tab";
import {
  applyRlsPreset,
  getRlsPreset,
  RLS_PRESET_CUSTOM,
  type RlsAction,
} from "@/components/supabase/rls-presets";
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
  const [bucketPresetId, setBucketPresetId] = useState(BUCKET_PRESET_CUSTOM);
  const [schemaPresetId, setSchemaPresetId] = useState(SCHEMA_PRESET_CUSTOM);
  const [realtimePresetId, setRealtimePresetId] = useState(REALTIME_PRESET_CUSTOM);
  const [newChannelName, setNewChannelName] = useState("");
  const [newChannelTable, setNewChannelTable] = useState("");
  const [newChannelSchema, setNewChannelSchema] = useState("public");
  const [rlsPresetId, setRlsPresetId] = useState(RLS_PRESET_CUSTOM);
  const [newPolicyName, setNewPolicyName] = useState("");
  const [newPolicyTable, setNewPolicyTable] = useState("");
  const [newPolicySchema, setNewPolicySchema] = useState("public");
  const [newPolicyAction, setNewPolicyAction] = useState<RlsAction>("ALL");
  const [newPolicyRole, setNewPolicyRole] = useState("authenticated");
  const [newPolicyUsing, setNewPolicyUsing] = useState("true");
  const [newPolicyCheck, setNewPolicyCheck] = useState("");

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
    if (!project || !newSchema.trim()) return;
    setLoading(true);
    try {
      await supabaseApi.createSchema(project.id, newSchema.trim());
      setNewSchema("");
      setSchemaPresetId(SCHEMA_PRESET_CUSTOM);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create schema");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBucket(e: React.FormEvent) {
    e.preventDefault();
    if (!project || !newBucket.trim()) return;
    const preset = getBucketPreset(bucketPresetId);
    setLoading(true);
    try {
      await supabaseApi.createBucket(project.id, newBucket.trim(), {
        public: preset?.public ?? false,
        file_size_limit_mb: preset?.fileSizeLimitMb ?? 50,
      });
      setNewBucket("");
      setBucketPresetId(BUCKET_PRESET_CUSTOM);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create bucket");
    } finally {
      setLoading(false);
    }
  }

  function handleBucketPresetChange(presetId: string) {
    const next = applyBucketPreset(presetId);
    setBucketPresetId(next.presetId);
    setNewBucket(next.name);
  }

  function handleSchemaPresetChange(presetId: string) {
    const next = applySchemaPreset(presetId);
    setSchemaPresetId(next.presetId);
    setNewSchema(next.name);
  }

  function handleRealtimePresetChange(presetId: string) {
    const next = applyRealtimePreset(presetId);
    setRealtimePresetId(next.presetId);
    setNewChannelName(next.channelName);
    setNewChannelTable(next.tableName);
    setNewChannelSchema(next.schemaName);
  }

  async function handleCreateChannel(e: React.FormEvent) {
    e.preventDefault();
    if (!project || !newChannelName.trim() || !newChannelTable.trim()) return;
    const preset = getRealtimePreset(realtimePresetId);
    setLoading(true);
    try {
      await supabaseApi.createRealtimeChannel(project.id, {
        name: newChannelName.trim(),
        table_name: newChannelTable.trim(),
        schema_name: newChannelSchema.trim() || "public",
        events: preset?.events,
      });
      setNewChannelName("");
      setNewChannelTable("");
      setNewChannelSchema("public");
      setRealtimePresetId(REALTIME_PRESET_CUSTOM);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create channel");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteChannel(channelId: string) {
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.deleteRealtimeChannel(project.id, channelId);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete channel");
    } finally {
      setLoading(false);
    }
  }

  function handleRlsPresetChange(presetId: string) {
    const next = applyRlsPreset(presetId);
    setRlsPresetId(next.presetId);
    setNewPolicyName(next.policyName);
    setNewPolicyTable(next.tableName);
    setNewPolicySchema(next.schemaName);
    setNewPolicyAction(next.action);
    setNewPolicyRole(next.roleName);
    setNewPolicyUsing(next.usingExpression);
    setNewPolicyCheck(next.checkExpression);
  }

  async function handleCreatePolicy(e: React.FormEvent) {
    e.preventDefault();
    if (!project || !newPolicyName.trim() || !newPolicyTable.trim()) return;
    const preset = getRlsPreset(rlsPresetId);
    setLoading(true);
    try {
      await supabaseApi.createRlsPolicy(project.id, {
        name: newPolicyName.trim(),
        table_name: newPolicyTable.trim(),
        schema_name: newPolicySchema.trim() || "public",
        action: preset?.action ?? newPolicyAction,
        role_name: preset?.roleName ?? newPolicyRole,
        using_expression: preset?.usingExpression ?? newPolicyUsing.trim(),
        check_expression:
          (preset?.checkExpression ?? newPolicyCheck.trim()) || null,
      });
      setNewPolicyName("");
      setNewPolicyTable("");
      setNewPolicySchema("public");
      setNewPolicyAction("ALL");
      setNewPolicyRole("authenticated");
      setNewPolicyUsing("true");
      setNewPolicyCheck("");
      setRlsPresetId(RLS_PRESET_CUSTOM);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create policy");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeletePolicy(policyId: string) {
    if (!project) return;
    setLoading(true);
    try {
      await supabaseApi.deleteRlsPolicy(project.id, policyId);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete policy");
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

          <TabsContent value="storage" className="mt-4">
            <SupabaseStorageTab
              schemas={schemas}
              buckets={buckets}
              loading={loading}
              bucketPresetId={bucketPresetId}
              bucketName={newBucket}
              schemaPresetId={schemaPresetId}
              schemaName={newSchema}
              onBucketPresetChange={handleBucketPresetChange}
              onBucketNameChange={setNewBucket}
              onSchemaPresetChange={handleSchemaPresetChange}
              onSchemaNameChange={setNewSchema}
              onCreateBucket={handleCreateBucket}
              onCreateSchema={handleCreateSchema}
              onDeleteBucket={(bucketId) => {
                if (!project) return;
                void supabaseApi.deleteBucket(project.id, bucketId).then(loadData);
              }}
            />
          </TabsContent>

          <TabsContent value="realtime" className="mt-4">
            <SupabaseRealtimeTab
              channels={channels}
              schemas={schemas}
              loading={loading}
              presetId={realtimePresetId}
              channelName={newChannelName}
              tableName={newChannelTable}
              schemaName={newChannelSchema}
              onPresetChange={handleRealtimePresetChange}
              onChannelNameChange={setNewChannelName}
              onTableNameChange={setNewChannelTable}
              onSchemaNameChange={setNewChannelSchema}
              onCreate={handleCreateChannel}
              onDelete={handleDeleteChannel}
            />
          </TabsContent>

          <TabsContent value="rls" className="mt-4">
            <SupabaseRlsTab
              policies={policies}
              schemas={schemas}
              loading={loading}
              presetId={rlsPresetId}
              policyName={newPolicyName}
              tableName={newPolicyTable}
              schemaName={newPolicySchema}
              action={newPolicyAction}
              roleName={newPolicyRole}
              usingExpression={newPolicyUsing}
              checkExpression={newPolicyCheck}
              onPresetChange={handleRlsPresetChange}
              onPolicyNameChange={setNewPolicyName}
              onTableNameChange={setNewPolicyTable}
              onSchemaNameChange={setNewPolicySchema}
              onActionChange={setNewPolicyAction}
              onRoleNameChange={setNewPolicyRole}
              onUsingExpressionChange={setNewPolicyUsing}
              onCheckExpressionChange={setNewPolicyCheck}
              onCreate={handleCreatePolicy}
              onDelete={handleDeletePolicy}
            />
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
