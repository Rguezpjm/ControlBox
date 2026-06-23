"use client";

import { Radio, Trash2 } from "lucide-react";
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
import type { SupabaseRealtimeChannel, SupabaseSchema } from "@/lib/supabase";
import {
  getRealtimePreset,
  REALTIME_PRESET_CUSTOM,
  REALTIME_PRESETS,
} from "@/components/supabase/realtime-presets";

interface SupabaseRealtimeTabProps {
  channels: SupabaseRealtimeChannel[];
  schemas: SupabaseSchema[];
  loading: boolean;
  presetId: string;
  channelName: string;
  tableName: string;
  schemaName: string;
  onPresetChange: (presetId: string) => void;
  onChannelNameChange: (value: string) => void;
  onTableNameChange: (value: string) => void;
  onSchemaNameChange: (value: string) => void;
  onCreate: (e: React.FormEvent) => void;
  onDelete: (channelId: string) => void;
}

export function SupabaseRealtimeTab({
  channels,
  schemas,
  loading,
  presetId,
  channelName,
  tableName,
  schemaName,
  onPresetChange,
  onChannelNameChange,
  onTableNameChange,
  onSchemaNameChange,
  onCreate,
  onDelete,
}: SupabaseRealtimeTabProps) {
  const preset = getRealtimePreset(presetId);
  const isCustom = presetId === REALTIME_PRESET_CUSTOM;

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border p-4">
        <div>
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Radio className="h-4 w-4 text-muted-foreground" />
            Realtime channels
          </h4>
          <p className="text-xs text-muted-foreground mt-1">
            Subscribe clients to Postgres changes via Supabase Realtime. Each channel watches one
            table for INSERT, UPDATE, and/or DELETE events.
          </p>
        </div>

        <form onSubmit={onCreate} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="realtime-preset">Use case template</Label>
            <Select value={presetId} onValueChange={onPresetChange}>
              <SelectTrigger id="realtime-preset">
                <SelectValue placeholder="Select a realtime template" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={REALTIME_PRESET_CUSTOM}>Custom table…</SelectItem>
                {REALTIME_PRESETS.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {preset && (
              <p className="text-xs text-muted-foreground">{preset.description}</p>
            )}
            {isCustom && (
              <p className="text-xs text-muted-foreground">
                Enter the Postgres table you already created. Realtime only works if the table
                exists and replication is enabled for it.
              </p>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="realtime-channel">Channel name</Label>
              <Input
                id="realtime-channel"
                placeholder="e.g. messages"
                value={channelName}
                onChange={(e) => onChannelNameChange(e.target.value)}
                disabled={!isCustom}
                required
              />
              <p className="text-xs text-muted-foreground">
                Identifier used in your client:{" "}
                <code className="font-mono">supabase.channel(&apos;{channelName || "name"}&apos;)</code>
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="realtime-schema">Schema</Label>
              <Select
                value={schemaName}
                onValueChange={onSchemaNameChange}
                disabled={!isCustom}
              >
                <SelectTrigger id="realtime-schema">
                  <SelectValue placeholder="Schema" />
                </SelectTrigger>
                <SelectContent>
                  {schemas.map((s) => (
                    <SelectItem key={s.id} value={s.name}>
                      {s.name}
                      {s.is_default ? " (default)" : ""}
                    </SelectItem>
                  ))}
                  {schemas.length === 0 && (
                    <SelectItem value="public">public (default)</SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="realtime-table">Table to watch</Label>
            <Input
              id="realtime-table"
              placeholder="e.g. messages"
              value={tableName}
              onChange={(e) => onTableNameChange(e.target.value)}
              disabled={!isCustom}
              required
            />
            {!isCustom && preset && (
              <p className="text-xs text-muted-foreground">
                Events: {preset.events.join(", ")} on{" "}
                <code className="font-mono">
                  {preset.schemaName}.{preset.tableName}
                </code>
              </p>
            )}
          </div>

          <Button
            type="submit"
            size="sm"
            disabled={loading || !channelName.trim() || !tableName.trim()}
          >
            <Radio className="h-4 w-4" />
            Enable realtime
          </Button>
        </form>
      </section>

      <section className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Active channels</p>
        {channels.length === 0 ? (
          <p className="text-sm text-muted-foreground rounded-lg border border-dashed p-4 text-center">
            No channels yet. Pick a template above — your app will receive live updates when rows
            change in the selected table.
          </p>
        ) : (
          channels.map((c) => (
            <div
              key={c.id}
              className="flex items-start justify-between gap-3 rounded border px-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <p className="font-medium">{c.name}</p>
                <p className="text-xs text-muted-foreground font-mono truncate">
                  {c.schema_name}.{c.table_name}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Events: {(c.events?.length ? c.events : ["INSERT", "UPDATE", "DELETE"]).join(", ")}
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onDelete(c.id)} disabled={loading}>
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
