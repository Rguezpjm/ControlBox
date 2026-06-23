"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatBytes } from "@/lib/utils";
import type { SupabaseProject } from "@/lib/supabase";
import type { ResourceStatus } from "@/types";

interface SupabaseProjectCardProps {
  project: SupabaseProject;
  status: ResourceStatus;
  onManage: () => void;
  compact?: boolean;
}

export function SupabaseProjectCard({
  project,
  status,
  onManage,
  compact = false,
}: SupabaseProjectCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow flex flex-col">
      <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500 text-xs font-bold text-white">
          S
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="truncate text-base leading-tight">{project.name}</CardTitle>
            <div className="shrink-0">
              <StatusBadge status={status} />
            </div>
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground" title={project.project_ref}>
            {compact ? `Supabase · ${project.project_ref}` : project.project_ref}
          </p>
        </div>
      </CardHeader>

      {!compact && (
        <CardContent className="mt-auto space-y-3">
          {project.error_message && (
            <p className="rounded border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
              {project.error_message}
            </p>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-muted/50 p-2.5">
              <p className="text-muted-foreground">DB Size</p>
              <p className="font-medium">{formatBytes(project.database_size_mb * 1024 * 1024)}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5">
              <p className="text-muted-foreground">Storage</p>
              <p className="font-medium">{formatBytes(project.storage_used_mb * 1024 * 1024)}</p>
            </div>
          </div>

          <div className="space-y-1 rounded-lg bg-muted/30 px-2.5 py-2 text-xs">
            <p className="truncate font-mono text-muted-foreground" title={project.database_name}>
              DB: {project.database_name}
            </p>
            <p className="truncate font-mono text-muted-foreground" title={project.database_user}>
              User: {project.database_user}
            </p>
          </div>

          <div className="flex gap-2 border-t pt-3">
            <Button variant="outline" size="sm" className="flex-1" onClick={onManage}>
              Manage
            </Button>
          </div>
        </CardContent>
      )}

      {compact && (
        <CardContent className="mt-auto pt-0">
          <div className="flex gap-2 border-t pt-3">
            <Button variant="outline" size="sm" className="flex-1" onClick={onManage}>
              Manage
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
