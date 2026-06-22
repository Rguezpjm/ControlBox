"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { backupsApi, type BackupDestination } from "@/lib/backups";
import { ApiError } from "@/lib/api-client";

interface CreateScheduleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  destinations: BackupDestination[];
  onCreated: () => void;
}

const SOURCE_TYPES = [
  { value: "websites", label: "Websites" },
  { value: "databases", label: "Databases" },
  { value: "dns", label: "DNS" },
  { value: "configurations", label: "Configurations" },
];

export function CreateScheduleDialog({
  open,
  onOpenChange,
  destinations,
  onCreated,
}: CreateScheduleDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("websites");
  const [resourceId, setResourceId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [cron, setCron] = useState("0 3 * * *");
  const [maxVersions, setMaxVersions] = useState("10");
  const [retentionDays, setRetentionDays] = useState("30");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!destinationId) {
      setError("Select a destination");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await backupsApi.createSchedule({
        name,
        source_type: sourceType,
        resource_id: resourceId || undefined,
        destination_id: destinationId,
        cron_expression: cron,
        max_versions: parseInt(maxVersions, 10) || 10,
        retention_days: parseInt(retentionDays, 10) || 30,
      });
      onOpenChange(false);
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create schedule");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Schedule Backup</DialogTitle>
          <DialogDescription>Automate backups with cron scheduling and version retention.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Schedule name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label>Source type</Label>
            <Select value={sourceType} onValueChange={setSourceType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {SOURCE_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Resource ID (optional)</Label>
            <Input value={resourceId} onChange={(e) => setResourceId(e.target.value)} className="font-mono text-xs" />
          </div>
          <div className="space-y-2">
            <Label>Destination</Label>
            <Select value={destinationId} onValueChange={setDestinationId}>
              <SelectTrigger><SelectValue placeholder="Select destination" /></SelectTrigger>
              <SelectContent>
                {destinations.map((d) => (
                  <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Cron expression</Label>
            <Input value={cron} onChange={(e) => setCron(e.target.value)} className="font-mono text-xs" />
            <p className="text-xs text-muted-foreground">Default: daily at 03:00 UTC</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Max versions</Label>
              <Input type="number" value={maxVersions} onChange={(e) => setMaxVersions(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Retention (days)</Label>
              <Input type="number" value={retentionDays} onChange={(e) => setRetentionDays(e.target.value)} />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading || destinations.length === 0}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              Schedule
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
