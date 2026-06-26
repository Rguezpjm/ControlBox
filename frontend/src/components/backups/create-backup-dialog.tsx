"use client";

import { useState, useEffect } from "react";
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
import { websitesApi, type Website } from "@/lib/websites";
import { databasesApi, type ManagedDatabase } from "@/lib/databases";
import { dnsApi, type DnsZone } from "@/lib/dns";

interface CreateBackupDialogProps {
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

export function CreateBackupDialog({
  open,
  onOpenChange,
  destinations,
  onCreated,
}: CreateBackupDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("websites");
  const [resourceId, setResourceId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [maxVersions, setMaxVersions] = useState("10");

  const [websites, setWebsites] = useState<Website[]>([]);
  const [databases, setDatabases] = useState<ManagedDatabase[]>([]);
  const [dnsZones, setDnsZones] = useState<DnsZone[]>([]);
  const [loadingResources, setLoadingResources] = useState(false);

  useEffect(() => {
    if (!open) return;
    
    async function loadResources() {
      setLoadingResources(true);
      try {
        const [webs, dbs, zones] = await Promise.all([
          websitesApi.list().catch(() => []),
          databasesApi.list().catch(() => []),
          dnsApi.listZones().catch(() => []),
        ]);
        setWebsites(webs);
        setDatabases(dbs);
        setDnsZones(zones);
      } catch (err) {
        console.error("Failed to load resources for backup dialog", err);
      } finally {
        setLoadingResources(false);
      }
    }
    
    loadResources();
  }, [open]);

  useEffect(() => {
    setResourceId("");
  }, [sourceType]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!destinationId) {
      setError("Select a destination");
      return;
    }
    if ((sourceType === "websites" || sourceType === "databases") && !resourceId) {
      setError(`Please select a ${sourceType === "websites" ? "website" : "database"}`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await backupsApi.createJob({
        name: name || undefined,
        source_type: sourceType,
        resource_id: (resourceId && resourceId !== "all-zones") ? resourceId : undefined,
        destination_id: destinationId,
        max_versions: parseInt(maxVersions, 10) || 10,
      });
      onOpenChange(false);
      setName("");
      setResourceId("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create backup");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Backup</DialogTitle>
          <DialogDescription>Run an on-demand backup to a configured destination.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Name (optional)</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="manual-backup" />
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
          {sourceType !== "configurations" && (
            <div className="space-y-2">
              <Label>
                Resource
                {sourceType === "dns" && " (optional)"}
              </Label>
              {loadingResources ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Loading resources…
                </div>
              ) : sourceType === "websites" ? (
                <Select value={resourceId} onValueChange={setResourceId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select website" />
                  </SelectTrigger>
                  <SelectContent>
                    {websites.map((w) => (
                      <SelectItem key={w.id} value={w.id}>
                        {w.name} ({w.domain})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : sourceType === "databases" ? (
                <Select value={resourceId} onValueChange={setResourceId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select database" />
                  </SelectTrigger>
                  <SelectContent>
                    {databases.map((db) => (
                      <SelectItem key={db.id} value={db.id}>
                        {db.name} ({db.engine})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : sourceType === "dns" ? (
                <Select value={resourceId} onValueChange={setResourceId}>
                  <SelectTrigger>
                    <SelectValue placeholder="All DNS Zones" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all-zones">All DNS Zones (Default)</SelectItem>
                    {dnsZones.map((z) => (
                      <SelectItem key={z.id} value={z.id}>
                        {z.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
            </div>
          )}
          <div className="space-y-2">
            <Label>Destination</Label>
            <Select value={destinationId} onValueChange={setDestinationId}>
              <SelectTrigger><SelectValue placeholder="Select destination" /></SelectTrigger>
              <SelectContent>
                {destinations.map((d) => (
                  <SelectItem key={d.id} value={d.id}>{d.name} ({d.destination_type})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Max versions</Label>
            <Input type="number" min={1} max={100} value={maxVersions} onChange={(e) => setMaxVersions(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading || destinations.length === 0}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

