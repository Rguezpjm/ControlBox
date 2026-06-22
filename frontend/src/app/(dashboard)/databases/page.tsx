"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CardGridSkeleton } from "@/components/skeletons";
import { CreateDatabaseDialog } from "@/components/databases/create-database-dialog";
import { ManageDatabaseDialog } from "@/components/databases/manage-database-dialog";
import { databasesApi, type ManagedDatabase } from "@/lib/databases";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    running: "running",
    completed: "running",
    stopped: "stopped",
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
  postgresql: { name: "PostgreSQL", color: "bg-indigo-500", icon: "P" },
  mssql: { name: "Microsoft SQL", color: "bg-red-500", icon: "MS" },
};

const engineTabs = [
  { id: "all", name: "All" },
  { id: "mysql", name: "MySQL" },
  { id: "mariadb", name: "MariaDB" },
  { id: "postgresql", name: "PostgreSQL" },
  { id: "mssql", name: "Microsoft SQL" },
];

function DatabasesContent() {
  const [databases, setDatabases] = useState<ManagedDatabase[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [manageDb, setManageDb] = useState<ManagedDatabase | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("all");

  const loadDatabases = useCallback(async () => {
    setLoading(true);
    try {
      const data = await databasesApi.list();
      setDatabases(data);
    } catch {
      setDatabases([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDatabases();
  }, [loadDatabases]);

  function openManage(db: ManagedDatabase) {
    setManageDb(db);
    setManageOpen(true);
  }

  function filterByEngine(engine: string) {
    if (engine === "all") return databases;
    return databases.filter((db) => db.engine === engine);
  }

  function renderCards(items: ManagedDatabase[]) {
    if (loading) return <CardGridSkeleton count={4} />;
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
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => openManage(db)}
              >
                Manage
              </Button>
            </div>
          </CardContent>
        </Card>
      );
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Databases"
        description="Manage MySQL, MariaDB, PostgreSQL and Microsoft SQL Server databases"
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Database
          </Button>
        }
      />

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
              {renderCards(filterByEngine(tab.id))}
            </div>
          </TabsContent>
        ))}
      </Tabs>

      <CreateDatabaseDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={loadDatabases}
      />

      <ManageDatabaseDialog
        database={manageDb}
        open={manageOpen}
        onOpenChange={setManageOpen}
        onUpdated={loadDatabases}
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
