"use client";

import { Shield, Trash2 } from "lucide-react";
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
import type { SupabaseRlsPolicy, SupabaseSchema } from "@/lib/supabase";
import {
  getRlsPreset,
  RLS_ACTIONS,
  RLS_PRESET_CUSTOM,
  RLS_PRESETS,
  RLS_ROLES,
  type RlsAction,
} from "@/components/supabase/rls-presets";

interface SupabaseRlsTabProps {
  policies: SupabaseRlsPolicy[];
  schemas: SupabaseSchema[];
  loading: boolean;
  presetId: string;
  policyName: string;
  tableName: string;
  schemaName: string;
  action: RlsAction;
  roleName: string;
  usingExpression: string;
  checkExpression: string;
  onPresetChange: (presetId: string) => void;
  onPolicyNameChange: (value: string) => void;
  onTableNameChange: (value: string) => void;
  onSchemaNameChange: (value: string) => void;
  onActionChange: (value: RlsAction) => void;
  onRoleNameChange: (value: string) => void;
  onUsingExpressionChange: (value: string) => void;
  onCheckExpressionChange: (value: string) => void;
  onCreate: (e: React.FormEvent) => void;
  onDelete: (policyId: string) => void;
}

export function SupabaseRlsTab({
  policies,
  schemas,
  loading,
  presetId,
  policyName,
  tableName,
  schemaName,
  action,
  roleName,
  usingExpression,
  checkExpression,
  onPresetChange,
  onPolicyNameChange,
  onTableNameChange,
  onSchemaNameChange,
  onActionChange,
  onRoleNameChange,
  onUsingExpressionChange,
  onCheckExpressionChange,
  onCreate,
  onDelete,
}: SupabaseRlsTabProps) {
  const preset = getRlsPreset(presetId);
  const isCustom = presetId === RLS_PRESET_CUSTOM;

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border p-4">
        <div>
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            Row Level Security (RLS)
          </h4>
          <p className="text-xs text-muted-foreground mt-1">
            RLS controls which rows each user can read or write in Postgres. Pick a template for
            common Supabase Auth patterns, or define a custom SQL rule.
          </p>
        </div>

        <form onSubmit={onCreate} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="rls-preset">Security template</Label>
            <Select value={presetId} onValueChange={onPresetChange}>
              <SelectTrigger id="rls-preset">
                <SelectValue placeholder="Select an RLS template" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={RLS_PRESET_CUSTOM}>Custom policy…</SelectItem>
                {RLS_PRESETS.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {preset && (
              <p className="text-xs text-muted-foreground">{preset.description}</p>
            )}
            {preset?.hint && (
              <p className="text-xs text-amber-600 dark:text-amber-500">{preset.hint}</p>
            )}
            {isCustom && (
              <p className="text-xs text-muted-foreground">
                Define who can access the table and under what condition. The table must already
                exist; RLS is enabled automatically when you add a policy.
              </p>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="rls-policy-name">Policy name</Label>
              <Input
                id="rls-policy-name"
                placeholder="e.g. users_own_data"
                value={policyName}
                onChange={(e) => onPolicyNameChange(e.target.value)}
                disabled={!isCustom}
                required
              />
              <p className="text-xs text-muted-foreground">
                Internal identifier (stored as cb_{policyName || "name"} in Postgres).
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="rls-schema">Schema</Label>
              <Select
                value={schemaName}
                onValueChange={onSchemaNameChange}
                disabled={!isCustom}
              >
                <SelectTrigger id="rls-schema">
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
            <Label htmlFor="rls-table">Table</Label>
            <Input
              id="rls-table"
              placeholder="e.g. profiles"
              value={tableName}
              onChange={(e) => onTableNameChange(e.target.value)}
              disabled={!isCustom}
              required
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="rls-action">Operation</Label>
              <Select
                value={action}
                onValueChange={(v) => onActionChange(v as RlsAction)}
                disabled={!isCustom}
              >
                <SelectTrigger id="rls-action">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RLS_ACTIONS.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item === "ALL" ? "ALL (SELECT, INSERT, UPDATE, DELETE)" : item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="rls-role">Applies to role</Label>
              <Select
                value={roleName}
                onValueChange={onRoleNameChange}
                disabled={!isCustom}
              >
                <SelectTrigger id="rls-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RLS_ROLES.map((role) => (
                    <SelectItem key={role.value} value={role.value}>
                      {role.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="rls-using">USING expression</Label>
            <Input
              id="rls-using"
              className="font-mono text-xs"
              placeholder="auth.uid() = user_id"
              value={usingExpression}
              onChange={(e) => onUsingExpressionChange(e.target.value)}
              disabled={!isCustom}
              required
            />
            <p className="text-xs text-muted-foreground">
              SQL condition for reading/updating existing rows. Use{" "}
              <code className="font-mono">auth.uid()</code> for the logged-in user&apos;s ID.
            </p>
          </div>

          {(isCustom || checkExpression) && (
            <div className="space-y-1.5">
              <Label htmlFor="rls-check">WITH CHECK expression (optional)</Label>
              <Input
                id="rls-check"
                className="font-mono text-xs"
                placeholder="auth.uid() = user_id"
                value={checkExpression}
                onChange={(e) => onCheckExpressionChange(e.target.value)}
                disabled={!isCustom}
              />
              <p className="text-xs text-muted-foreground">
                Extra check on INSERT/UPDATE. Leave empty if USING is enough.
              </p>
            </div>
          )}

          {!isCustom && preset && (
            <div className="rounded-md bg-muted/50 px-3 py-2 text-xs font-mono text-muted-foreground break-all">
              FOR {preset.action} TO {preset.roleName} USING ({preset.usingExpression})
              {preset.checkExpression ? ` WITH CHECK (${preset.checkExpression})` : ""}
            </div>
          )}

          <Button
            type="submit"
            size="sm"
            disabled={loading || !policyName.trim() || !tableName.trim() || !usingExpression.trim()}
          >
            <Shield className="h-4 w-4" />
            Apply policy
          </Button>
        </form>
      </section>

      <section className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Active policies</p>
        {policies.length === 0 ? (
          <p className="text-sm text-muted-foreground rounded-lg border border-dashed p-4 text-center">
            No policies yet. Without RLS, authenticated users may access all rows — add a template
            to restrict access per user or role.
          </p>
        ) : (
          policies.map((p) => (
            <div
              key={p.id}
              className="flex items-start justify-between gap-3 rounded border px-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-muted-foreground font-mono truncate">
                  {p.schema_name}.{p.table_name} · {p.action} · {p.role_name}
                </p>
                <p className="text-xs text-muted-foreground font-mono mt-0.5 truncate">
                  USING ({p.using_expression})
                  {p.check_expression ? ` CHECK (${p.check_expression})` : ""}
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onDelete(p.id)} disabled={loading}>
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
