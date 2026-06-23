"use client";

import { Archive, Database, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SupabaseBucket, SupabaseSchema } from "@/lib/supabase";
import {
  BUCKET_PRESET_CUSTOM,
  BUCKET_PRESETS,
  getBucketPreset,
  getSchemaPreset,
  SCHEMA_PRESET_CUSTOM,
  SCHEMA_PRESETS,
} from "@/components/supabase/storage-presets";

interface SupabaseStorageTabProps {
  schemas: SupabaseSchema[];
  buckets: SupabaseBucket[];
  loading: boolean;
  bucketPresetId: string;
  bucketName: string;
  schemaPresetId: string;
  schemaName: string;
  onBucketPresetChange: (presetId: string) => void;
  onBucketNameChange: (name: string) => void;
  onSchemaPresetChange: (presetId: string) => void;
  onSchemaNameChange: (name: string) => void;
  onCreateBucket: (e: React.FormEvent) => void;
  onCreateSchema: (e: React.FormEvent) => void;
  onDeleteBucket: (bucketId: string) => void;
}

export function SupabaseStorageTab({
  schemas,
  buckets,
  loading,
  bucketPresetId,
  bucketName,
  schemaPresetId,
  schemaName,
  onBucketPresetChange,
  onBucketNameChange,
  onSchemaPresetChange,
  onSchemaNameChange,
  onCreateBucket,
  onCreateSchema,
  onDeleteBucket,
}: SupabaseStorageTabProps) {
  const bucketPreset = getBucketPreset(bucketPresetId);
  const schemaPreset = getSchemaPreset(schemaPresetId);
  const bucketCustom = bucketPresetId === BUCKET_PRESET_CUSTOM;
  const schemaCustom = schemaPresetId === SCHEMA_PRESET_CUSTOM;

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border p-4">
        <div>
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Archive className="h-4 w-4 text-muted-foreground" />
            Storage buckets
          </h4>
          <p className="text-xs text-muted-foreground mt-1">
            Buckets store files in MinIO (S3). Pick a template or enter a custom name.
          </p>
        </div>

        <form onSubmit={onCreateBucket} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="bucket-preset">Template</Label>
            <Select value={bucketPresetId} onValueChange={onBucketPresetChange}>
              <SelectTrigger id="bucket-preset">
                <SelectValue placeholder="Select a bucket template" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={BUCKET_PRESET_CUSTOM}>Custom name…</SelectItem>
                {BUCKET_PRESETS.map((preset) => (
                  <SelectItem key={preset.id} value={preset.id}>
                    {preset.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {bucketPreset && (
              <p className="text-xs text-muted-foreground">{bucketPreset.description}</p>
            )}
            {bucketCustom && (
              <p className="text-xs text-muted-foreground">
                Use lowercase letters, numbers, and hyphens (2–48 characters).
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="bucket-name">Bucket name</Label>
            <Input
              id="bucket-name"
              placeholder="e.g. uploads"
              value={bucketName}
              onChange={(e) => onBucketNameChange(e.target.value)}
              disabled={!bucketCustom}
              required
            />
            {!bucketCustom && bucketPreset && (
              <p className="text-xs text-muted-foreground">
                {bucketPreset.public ? "Public bucket" : "Private bucket"} · max{" "}
                {bucketPreset.fileSizeLimitMb} MB per file
              </p>
            )}
          </div>

          <Button type="submit" size="sm" disabled={loading || !bucketName.trim()}>
            <Archive className="h-4 w-4" />
            Create bucket
          </Button>
        </form>

        <div className="space-y-2 pt-2 border-t">
          <p className="text-xs font-medium text-muted-foreground">Existing buckets</p>
          {buckets.length === 0 ? (
            <p className="text-sm text-muted-foreground">No buckets yet.</p>
          ) : (
            buckets.map((b) => (
              <div key={b.id} className="flex items-center justify-between rounded border px-3 py-2 text-sm">
                <div>
                  <span className="font-medium">{b.name}</span>
                  <span className="text-muted-foreground ml-2">
                    {b.public ? "public" : "private"}
                  </span>
                </div>
                <Button size="sm" variant="ghost" onClick={() => onDeleteBucket(b.id)} disabled={loading}>
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="space-y-3 rounded-lg border p-4">
        <div>
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Database className="h-4 w-4 text-muted-foreground" />
            PostgreSQL schemas
          </h4>
          <p className="text-xs text-muted-foreground mt-1">
            Schemas organize tables. <code className="font-mono">public</code> is created by default.
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Current schemas</p>
          {schemas.map((s) => (
            <div key={s.id} className="rounded border px-3 py-2 text-sm">
              <span className="font-medium">{s.name}</span>
              {s.is_default && (
                <span className="text-muted-foreground ml-2">(default)</span>
              )}
            </div>
          ))}
        </div>

        <form onSubmit={onCreateSchema} className="space-y-3 pt-2 border-t">
          <div className="space-y-1.5">
            <Label htmlFor="schema-preset">Template</Label>
            <Select value={schemaPresetId} onValueChange={onSchemaPresetChange}>
              <SelectTrigger id="schema-preset">
                <SelectValue placeholder="Select a schema template" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={SCHEMA_PRESET_CUSTOM}>Custom name…</SelectItem>
                {SCHEMA_PRESETS.map((preset) => (
                  <SelectItem key={preset.id} value={preset.id}>
                    {preset.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {schemaPreset && (
              <p className="text-xs text-muted-foreground">{schemaPreset.description}</p>
            )}
            {schemaCustom && (
              <p className="text-xs text-muted-foreground">
                Reserved: public, auth, storage, extensions, graphql_public.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="schema-name">Schema name</Label>
            <Input
              id="schema-name"
              placeholder="e.g. app"
              value={schemaName}
              onChange={(e) => onSchemaNameChange(e.target.value)}
              disabled={!schemaCustom}
              required
            />
          </div>

          <Button type="submit" size="sm" disabled={loading || !schemaName.trim()}>
            Create schema
          </Button>
        </form>
      </section>
    </div>
  );
}

export function applyBucketPreset(presetId: string): { name: string; presetId: string } {
  if (presetId === BUCKET_PRESET_CUSTOM) {
    return { name: "", presetId };
  }
  const preset = getBucketPreset(presetId);
  return { name: preset?.name ?? "", presetId };
}

export function applySchemaPreset(presetId: string): { name: string; presetId: string } {
  if (presetId === SCHEMA_PRESET_CUSTOM) {
    return { name: "", presetId };
  }
  const preset = getSchemaPreset(presetId);
  return { name: preset?.name ?? "", presetId };
}
