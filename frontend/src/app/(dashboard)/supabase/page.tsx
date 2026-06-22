"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateSupabaseProjectDialog } from "@/components/supabase/create-project-dialog";
import { ManageSupabaseProjectDialog } from "@/components/supabase/manage-project-dialog";
import { supabaseApi, type SupabaseProject } from "@/lib/supabase";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    suspended: "stopped",
    pending: "pending",
    error: "error",
  };
  return map[status] || "pending";
}

function SupabaseContent() {
  const [projects, setProjects] = useState<SupabaseProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [manageProject, setManageProject] = useState<SupabaseProject | null>(null);
  const [manageOpen, setManageOpen] = useState(false);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await supabaseApi.listProjects();
      setProjects(data);
    } catch {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  if (loading) return <CardGridSkeleton count={3} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supabase"
        description="Manage projects on the global Supabase Self-Hosted instance"
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Project
          </Button>
        }
      />

      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm">
        <p className="font-medium text-emerald-600 dark:text-emerald-400">Single Global Instance</p>
        <p className="text-muted-foreground mt-1">
          All tenant projects share one Supabase Self-Hosted installation. Each project gets an isolated
          PostgreSQL database, user, API keys, storage buckets and RLS policies.
        </p>
      </div>

      {projects.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-12">
          No Supabase projects yet. Create your first project to get started.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card key={project.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="flex flex-row items-start justify-between pb-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500 text-white text-xs font-bold">
                    S
                  </div>
                  <div>
                    <CardTitle className="text-base">{project.name}</CardTitle>
                    <p className="text-xs text-muted-foreground font-mono">{project.project_ref}</p>
                  </div>
                </div>
                <StatusBadge status={mapStatus(project.status)} />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg bg-muted/50 p-2">
                    <p className="text-muted-foreground">DB Size</p>
                    <p className="font-medium">{formatBytes(project.database_size_mb * 1024 * 1024)}</p>
                  </div>
                  <div className="rounded-lg bg-muted/50 p-2">
                    <p className="text-muted-foreground">Storage</p>
                    <p className="font-medium">{formatBytes(project.storage_used_mb * 1024 * 1024)}</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground font-mono truncate">
                  {project.database_user}@{project.database_name}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setManageProject(project);
                    setManageOpen(true);
                  }}
                >
                  Manage
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateSupabaseProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={loadProjects}
      />

      <ManageSupabaseProjectDialog
        project={manageProject}
        open={manageOpen}
        onOpenChange={setManageOpen}
        onUpdated={loadProjects}
      />
    </div>
  );
}

export default function SupabasePage() {
  return (
    <Suspense fallback={<CardGridSkeleton />}>
      <SupabaseContent />
    </Suspense>
  );
}
