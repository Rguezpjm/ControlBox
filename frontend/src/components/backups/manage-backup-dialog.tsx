"use client";

import { useState, useEffect } from "react";
import { Loader2, RotateCcw, Trash2, History } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { StatusBadge } from "@/components/shared/status-badge";
import { backupsApi, type BackupJob } from "@/lib/backups";
import { ApiError } from "@/lib/api-client";
import { formatBytes } from "@/lib/utils";
import { format } from "date-fns";
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

interface ManageBackupDialogProps {
  job: BackupJob | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function ManageBackupDialog({
  job,
  open,
  onOpenChange,
  onUpdated,
}: ManageBackupDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [versions, setVersions] = useState<BackupJob[]>([]);

  useEffect(() => {
    if (open && job) {
      backupsApi.listVersions(job.id).then(setVersions).catch(() => setVersions([]));
      setError(null);
    }
  }, [open, job]);

  if (!job) return null;

  async function handleRestore() {
    if (!job || !confirm("Restore this backup? Current data may be overwritten.")) return;
    setLoading(true);
    setError(null);
    try {
      await backupsApi.restoreJob(job.id);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Restore failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!job || !confirm("Delete this backup permanently?")) return;
    setLoading(true);
    try {
      await backupsApi.deleteJob(job.id);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload() {
    if (!job) return;
    try {
      const result = await backupsApi.download(job.id);
      if (result.download_url) {
        window.open(result.download_url, "_blank");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download unavailable for local storage");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <DialogTitle>{job.name}</DialogTitle>
              <DialogDescription className="capitalize">{job.source_type} · v{job.version_number}</DialogDescription>
            </div>
            <StatusBadge status={mapStatus(job.status)} />
          </div>
        </DialogHeader>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-muted-foreground text-xs">Size</p>
            <p className="font-medium">{formatBytes(job.size_bytes)}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-muted-foreground text-xs">Resource</p>
            <p className="font-medium truncate">{job.resource_name || "—"}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-3 col-span-2">
            <p className="text-muted-foreground text-xs">Checksum</p>
            <p className="font-mono text-xs truncate">{job.checksum || "—"}</p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={handleRestore}
            disabled={loading || job.status !== "completed" || job.source_type === "configurations"}
          >
            <RotateCcw className="h-4 w-4" />
            Restore
          </Button>
          <Button variant="outline" className="flex-1" onClick={handleDownload} disabled={job.status !== "completed"}>
            Download
          </Button>
          <Button variant="destructive" size="icon" onClick={handleDelete} disabled={loading}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center gap-2 text-sm font-medium">
            <History className="h-4 w-4" />
            Version history
          </div>
          {versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No other versions.</p>
          ) : (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {versions.map((v) => (
                <div key={v.id} className="flex items-center justify-between text-xs rounded border p-2">
                  <span>v{v.version_number} · {v.name}</span>
                  <span className="text-muted-foreground">
                    {v.completed_at ? format(new Date(v.completed_at), "MMM d, HH:mm") : "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {loading && (
          <div className="flex justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
