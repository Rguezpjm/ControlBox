"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { Plus, Archive, Clock, HardDrive, RotateCcw } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatCard } from "@/components/dashboard/stat-card";
import { TableSkeleton } from "@/components/skeletons";
import { CreateBackupDialog } from "@/components/backups/create-backup-dialog";
import { CreateDestinationDialog } from "@/components/backups/create-destination-dialog";
import { CreateScheduleDialog } from "@/components/backups/create-schedule-dialog";
import { ManageBackupDialog } from "@/components/backups/manage-backup-dialog";
import {
  backupsApi,
  type BackupJob,
  type BackupSchedule,
  type BackupDestination,
  type BackupStats,
} from "@/lib/backups";
import { formatBytes } from "@/lib/utils";
import { format, formatDistanceToNow } from "date-fns";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    completed: "running",
    running: "pending",
    pending: "pending",
    restoring: "pending",
    failed: "error",
  };
  return map[status] || "pending";
}

function BackupsContent() {
  const [stats, setStats] = useState<BackupStats | null>(null);
  const [jobs, setJobs] = useState<BackupJob[]>([]);
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);
  const [destinations, setDestinations] = useState<BackupDestination[]>([]);
  const [loading, setLoading] = useState(true);

  const [createBackupOpen, setCreateBackupOpen] = useState(false);
  const [createScheduleOpen, setCreateScheduleOpen] = useState(false);
  const [createDestOpen, setCreateDestOpen] = useState(false);
  const [manageJob, setManageJob] = useState<BackupJob | null>(null);
  const [manageOpen, setManageOpen] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, jobsData, schedulesData, destData] = await Promise.all([
        backupsApi.stats(),
        backupsApi.listJobs(),
        backupsApi.listSchedules(),
        backupsApi.listDestinations(),
      ]);
      setStats(statsData);
      setJobs(jobsData);
      setSchedules(schedulesData);
      setDestinations(destData);
    } catch {
      setStats(null);
      setJobs([]);
      setSchedules([]);
      setDestinations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Backups"
        description="Automated and on-demand backups for websites, databases, DNS and configurations"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setCreateDestOpen(true)}>
              <HardDrive className="h-4 w-4" />
              Destination
            </Button>
            <Button variant="outline" onClick={() => setCreateScheduleOpen(true)}>
              <Clock className="h-4 w-4" />
              Schedule
            </Button>
            <Button onClick={() => setCreateBackupOpen(true)}>
              <Plus className="h-4 w-4" />
              Create Backup
            </Button>
          </div>
        }
      />

      {stats && (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard title="Total Backups" value={stats.completed_jobs} icon={Archive} description={`${stats.failed_jobs} failed`} />
          <StatCard title="Storage Used" value={formatBytes(stats.total_size_bytes)} icon={HardDrive} />
          <StatCard
            title="Next Scheduled"
            value={
              stats.next_scheduled_at
                ? formatDistanceToNow(new Date(stats.next_scheduled_at), { addSuffix: true })
                : "None"
            }
            icon={Clock}
            description={`${stats.active_schedules} active schedules`}
          />
        </div>
      )}

      <Tabs defaultValue="jobs">
        <TabsList>
          <TabsTrigger value="jobs">Backups</TabsTrigger>
          <TabsTrigger value="schedules">Schedules</TabsTrigger>
          <TabsTrigger value="destinations">Destinations</TabsTrigger>
        </TabsList>

        <TabsContent value="jobs" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Name</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Type</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">Version</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">Size</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden lg:table-cell">Created</th>
                      <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                          No backups yet. Add a destination and create your first backup.
                        </td>
                      </tr>
                    ) : (
                      jobs.map((job) => (
                        <tr key={job.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">{job.name}</td>
                          <td className="px-4 py-3">
                            <Badge variant="outline" className="capitalize">{job.source_type}</Badge>
                          </td>
                          <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">v{job.version_number}</td>
                          <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">
                            {job.size_bytes > 0 ? formatBytes(job.size_bytes) : "—"}
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={mapStatus(job.status)} />
                          </td>
                          <td className="px-4 py-3 hidden lg:table-cell text-muted-foreground text-xs">
                            {format(new Date(job.created_at), "MMM d, HH:mm")}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={job.status !== "completed"}
                              onClick={() => { setManageJob(job); setManageOpen(true); }}
                            >
                              <RotateCcw className="h-3 w-3" />
                            </Button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="schedules" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Name</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Source</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">Cron</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden lg:table-cell">Next run</th>
                      <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedules.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                          No schedules configured.
                        </td>
                      </tr>
                    ) : (
                      schedules.map((s) => (
                        <tr key={s.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">{s.name}</td>
                          <td className="px-4 py-3 capitalize">{s.source_type}</td>
                          <td className="px-4 py-3 hidden md:table-cell font-mono text-xs">{s.cron_expression}</td>
                          <td className="px-4 py-3">
                            <StatusBadge status={s.is_active ? "running" : "stopped"} />
                          </td>
                          <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                            {s.next_run_at
                              ? formatDistanceToNow(new Date(s.next_run_at), { addSuffix: true })
                              : "—"}
                          </td>
                          <td className="px-4 py-3 text-right space-x-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => backupsApi.runSchedule(s.id).then(loadData)}
                            >
                              Run
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                (s.is_active ? backupsApi.pauseSchedule(s.id) : backupsApi.resumeSchedule(s.id)).then(loadData)
                              }
                            >
                              {s.is_active ? "Pause" : "Resume"}
                            </Button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="destinations" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Name</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Type</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">Target</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                      <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {destinations.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-12 text-center text-muted-foreground">
                          No destinations. Add local, MinIO, S3 or R2 storage.
                        </td>
                      </tr>
                    ) : (
                      destinations.map((d) => (
                        <tr key={d.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">{d.name}</td>
                          <td className="px-4 py-3 uppercase text-xs">{d.destination_type}</td>
                          <td className="px-4 py-3 hidden md:table-cell font-mono text-xs text-muted-foreground truncate max-w-[200px]">
                            {d.destination_type === "local" ? d.local_path || "default" : d.bucket}
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={d.is_active ? "running" : "stopped"} />
                          </td>
                          <td className="px-4 py-3 text-right space-x-1">
                            <Button variant="ghost" size="sm" onClick={() => backupsApi.testDestination(d.id).then(loadData)}>
                              Test
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => backupsApi.deleteDestination(d.id).then(loadData)}>
                              Delete
                            </Button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <CreateBackupDialog
        open={createBackupOpen}
        onOpenChange={setCreateBackupOpen}
        destinations={destinations}
        onCreated={loadData}
      />
      <CreateScheduleDialog
        open={createScheduleOpen}
        onOpenChange={setCreateScheduleOpen}
        destinations={destinations}
        onCreated={loadData}
      />
      <CreateDestinationDialog
        open={createDestOpen}
        onOpenChange={setCreateDestOpen}
        onCreated={loadData}
      />
      <ManageBackupDialog
        job={manageJob}
        open={manageOpen}
        onOpenChange={setManageOpen}
        onUpdated={loadData}
      />
    </div>
  );
}

export default function BackupsPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <BackupsContent />
    </Suspense>
  );
}
