"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, Plus, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateDatabaseDialog } from "@/components/databases/create-database-dialog";
import { ManageDatabaseDialog } from "@/components/databases/manage-database-dialog";
import { CreateSupabaseProjectDialog } from "@/components/supabase/create-project-dialog";
import { ManageSupabaseProjectDialog } from "@/components/supabase/manage-project-dialog";
import { ProductionSetupDialog } from "@/components/platform/production-setup-dialog";
import { ensureSupabaseService } from "@/lib/platform";
import { databasesApi, type ManagedDatabase } from "@/lib/databases";
import { supabaseApi, type SupabaseProject, type SupabaseServiceStatus } from "@/lib/supabase";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    running: "running",
    completed: "running",
    stopped: "stopped",
    suspended: "stopped",
    pending: "pending",
    provisioning: "pending",
    restoring: "pending",
    deleting: "pending",
    error: "error",
    failed: "error",
  };
  return map[status] || "pending";
}

const engineConfig: Record<string, { name: string; color: string; icon: string }> = {
  mysql: { name: "MySQL", color: "bg-blue-500", icon: "M" },
  mariadb: { name: "MariaDB", color: "bg-cyan-500", icon: "Ma" },
  mssql: { name: "Microsoft SQL", color: "bg-red-500", icon: "MS" },
};

const engineTabs = [
  { id: "all", name: "All" },
  { id: "mysql", name: "MySQL" },
  { id: "mariadb", name: "MariaDB" },
  { id: "supabase", name: "Supabase" },
  { id: "mssql", name: "Microsoft SQL" },
];

function DatabasesContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") || "all";

  const [databases, setDatabases] = useState<ManagedDatabase[]>([]);
  const [supabaseProjects, setSupabaseProjects] = useState<SupabaseProject[]>([]);
  const [supabaseStatus, setSupabaseStatus] = useState<SupabaseServiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [supabaseLoading, setSupabaseLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createSupabaseOpen, setCreateSupabaseOpen] = useState(false);
  const [manageDb, setManageDb] = useState<ManagedDatabase | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [manageProject, setManageProject] = useState<SupabaseProject | null>(null);
  const [manageSupabaseOpen, setManageSupabaseOpen] = useState(false);
  const [setupDialogOpen, setSetupDialogOpen] = useState(false);
  const [activatingSupabase, setActivatingSupabase] = useState(false);
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab && engineTabs.some((t) => t.id === tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const loadDatabases = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await databasesApi.list();
      setDatabases(data.filter((db) => db.engine !== "postgresql"));
    } catch (err) {
      setDatabases([]);
      setLoadError(err instanceof Error ? err.message : "Failed to load databases");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSupabase = useCallback(async () => {
    setSupabaseLoading(true);
    setLoadError(null);
    try {
      const [status, projects] = await Promise.all([
        supabaseApi.status(),
        supabaseApi.listProjects(),
      ]);
      setSupabaseStatus(status);
      setSupabaseProjects(projects);
    } catch (err) {
      setSupabaseProjects([]);
      setSupabaseStatus(null);
      setLoadError(err instanceof Error ? err.message : "Failed to load Supabase projects");
    } finally {
      setSupabaseLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDatabases();
  }, [loadDatabases]);

  useEffect(() => {
    if (activeTab === "supabase" || activeTab === "all") {
      void loadSupabase();
    }
  }, [activeTab, loadSupabase]);

  function openManage(db: ManagedDatabase) {
    setManageDb(db);
    setManageOpen(true);
  }

  function filterByEngine(engine: string) {
    if (engine === "all") return databases;
    if (engine === "supabase") return [];
    return databases.filter((db) => db.engine === engine);
  }

  async function activateSupabase() {
    setActivatingSupabase(true);
    try {
      const result = await ensureSupabaseService();
      if (result.success) {
        toast.success("Supabase activado correctamente", { description: result.message });
        await loadSupabase();
      } else {
        toast.error(result.message || "No se pudo activar Supabase");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo activar Supabase");
    } finally {
      setActivatingSupabase(false);
    }
  }

  function renderDatabaseCards(items: ManagedDatabase[]) {
    if (loading && activeTab !== "supabase") return <CardGridSkeleton count={4} />;
    if (items.length === 0) {
      return (
        <p className="text-sm text-muted-foreground col-span-2 text-center py-12">
          No databases yet. Create your first database to get started.
        </p>
      );
    }
    return items.map((db) => {
      const engine = engineConfig[db.engine] || { name: db.engine, color: "bg-gray-500", icon: "?" };
      return (
        <Card key={db.id} className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-start justify-between pb-3">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-xl text-white text-xs font-bold ${engine.color}`}
              >
                {engine.icon}
              </div>
              <div>
                <CardTitle className="text-base">{db.name}</CardTitle>
                <p className="text-xs text-muted-foreground">{engine.name}</p>
              </div>
            </div>
            <StatusBadge status={mapStatus(db.status)} />
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg bg-muted/50 p-2">
                <p className="text-muted-foreground">Size</p>
                <p className="font-medium">{formatBytes(db.size_mb * 1024 * 1024)}</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-2">
                <p className="text-muted-foreground">Max connections</p>
                <p className="font-medium">{db.max_connections}</p>
              </div>
            </div>
            <div className="text-xs text-muted-foreground font-mono">
              {db.host}:{db.port}
            </div>
            <div className="flex gap-2 pt-2 border-t">
              <Button variant="outline" size="sm" className="flex-1" onClick={() => openManage(db)}>
                Manage
              </Button>
            </div>
          </CardContent>
        </Card>
      );
    });
  }

  function renderSupabaseTab() {
    if (supabaseLoading) return <CardGridSkeleton count={3} />;

    return (
      <div className="space-y-4">
        {supabaseStatus && !supabaseStatus.enabled && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm sm:col-span-2">
            <p className="font-medium text-amber-700 dark:text-amber-400">Supabase no disponible</p>
            <p className="text-muted-foreground mt-1">{supabaseStatus.message}</p>
            {supabaseStatus.profile_enabled && (
              <p className="text-muted-foreground mt-2 text-xs">
                El perfil Supabase está guardado en la configuración, pero los contenedores no están en
                ejecución. Pulse el botón para iniciarlos (puede tardar unos minutos la primera vez).
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="secondary"
                className="gap-1.5"
                disabled={activatingSupabase}
                onClick={activateSupabase}
              >
                {activatingSupabase ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Settings2 className="h-3.5 w-3.5" />
                )}
                Activar Supabase
              </Button>
              {!supabaseStatus.profile_enabled && (
                <Button size="sm" variant="outline" onClick={() => setSetupDialogOpen(true)}>
                  Configuración del servidor
                </Button>
              )}
            </div>
            <p className="text-muted-foreground mt-3 text-xs">
              También puede ejecutar <code className="font-mono">controlbox repair</code> en el VPS.
              Supabase requiere MinIO (Backups).
            </p>
          </div>
        )}

        {supabaseStatus?.enabled && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm">
            <p className="font-medium text-emerald-600 dark:text-emerald-400">Supabase Self-Hosted</p>
            <p className="text-muted-foreground mt-1">
              PostgreSQL projects with Auth, Storage, Realtime and RLS — connected to{" "}
              <span className="font-mono">{supabaseStatus.host}:{supabaseStatus.port}</span>
            </p>
          </div>
        )}

        {supabaseProjects.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-12">
            No Supabase projects yet. Create your first project to get PostgreSQL + Supabase APIs.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {supabaseProjects.map((project) => (
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
                  {project.error_message && (
                    <p className="text-xs text-destructive rounded border border-destructive/30 bg-destructive/5 p-2">
                      {project.error_message}
                    </p>
                  )}
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
                      setManageSupabaseOpen(true);
                    }}
                  >
                    Manage
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  function renderAllTab() {
    if (loading || supabaseLoading) return <CardGridSkeleton count={4} />;
    const hasAny = databases.length > 0 || supabaseProjects.length > 0;
    if (!hasAny) {
      return (
        <p className="text-sm text-muted-foreground col-span-2 text-center py-12">
          No databases yet. Use MySQL/MariaDB/SQL tabs or create a Supabase project.
        </p>
      );
    }
    return (
      <>
        {renderDatabaseCards(databases)}
        {supabaseProjects.map((project) => (
          <Card key={project.id} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-start justify-between pb-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500 text-white text-xs font-bold">
                  S
                </div>
                <div>
                  <CardTitle className="text-base">{project.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">Supabase · {project.project_ref}</p>
                </div>
              </div>
              <StatusBadge status={mapStatus(project.status)} />
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => {
                  setManageProject(project);
                  setManageSupabaseOpen(true);
                }}
              >
                Manage
              </Button>
            </CardContent>
          </Card>
        ))}
      </>
    );
  }

  const isSupabaseTab = activeTab === "supabase";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Databases"
        description="MySQL, MariaDB, SQL Server and Supabase (PostgreSQL) projects"
        action={
          <Button
            onClick={() => (isSupabaseTab ? setCreateSupabaseOpen(true) : setCreateOpen(true))}
            disabled={isSupabaseTab && supabaseStatus !== null && !supabaseStatus.enabled}
          >
            <Plus className="h-4 w-4" />
            {isSupabaseTab ? "Create Supabase Project" : "Create Database"}
          </Button>
        }
      />

      {loadError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {loadError}
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {engineTabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id}>
              {tab.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {engineTabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="mt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              {tab.id === "supabase"
                ? renderSupabaseTab()
                : tab.id === "all"
                  ? renderAllTab()
                  : renderDatabaseCards(filterByEngine(tab.id))}
            </div>
          </TabsContent>
        ))}
      </Tabs>

      <CreateDatabaseDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={loadDatabases} />
      <CreateSupabaseProjectDialog
        open={createSupabaseOpen}
        onOpenChange={setCreateSupabaseOpen}
        onCreated={loadSupabase}
      />
      <ManageDatabaseDialog
        database={manageDb}
        open={manageOpen}
        onOpenChange={setManageOpen}
        onUpdated={loadDatabases}
      />
      <ManageSupabaseProjectDialog
        project={manageProject}
        open={manageSupabaseOpen}
        onOpenChange={setManageSupabaseOpen}
        onUpdated={loadSupabase}
      />
      <ProductionSetupDialog
        open={setupDialogOpen}
        onOpenChange={setSetupDialogOpen}
        onComplete={loadSupabase}
      />
    </div>
  );
}

export default function DatabasesPage() {
  return (
    <Suspense fallback={<CardGridSkeleton />}>
      <DatabasesContent />
    </Suspense>
  );
}
