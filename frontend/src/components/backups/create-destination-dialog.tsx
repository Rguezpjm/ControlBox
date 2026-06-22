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

interface CreateDestinationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

const DEST_TYPES = [
  { value: "local", label: "Local" },
  { value: "minio", label: "MinIO" },
  { value: "s3", label: "Amazon S3" },
  { value: "r2", label: "Cloudflare R2" },
];

export function CreateDestinationDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateDestinationDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [destType, setDestType] = useState<"local" | "minio" | "s3" | "r2">("local");
  const [bucket, setBucket] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [region, setRegion] = useState("us-east-1");
  const [prefix, setPrefix] = useState("controlbox");
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [localPath, setLocalPath] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await backupsApi.createDestination({
        name,
        destination_type: destType,
        bucket,
        endpoint,
        region,
        prefix,
        local_path: localPath,
        access_key: accessKey,
        secret_key: secretKey,
      });
      onOpenChange(false);
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create destination");
    } finally {
      setLoading(false);
    }
  }

  const isRemote = destType !== "local";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Destination</DialogTitle>
          <DialogDescription>Configure local, MinIO, S3 or Cloudflare R2 storage.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label>Type</Label>
            <Select value={destType} onValueChange={(v) => setDestType(v as typeof destType)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {DEST_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {destType === "local" ? (
            <div className="space-y-2">
              <Label>Local path (optional)</Label>
              <Input value={localPath} onChange={(e) => setLocalPath(e.target.value)} placeholder="/var/lib/controlbox/backups" />
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label>Bucket</Label>
                <Input value={bucket} onChange={(e) => setBucket(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label>Endpoint</Label>
                <Input
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  placeholder={destType === "r2" ? "https://<account>.r2.cloudflarestorage.com" : "http://minio:9000"}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Region</Label>
                  <Input value={region} onChange={(e) => setRegion(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Prefix</Label>
                  <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Access key</Label>
                <Input value={accessKey} onChange={(e) => setAccessKey(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label>Secret key</Label>
                <Input type="password" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} required />
              </div>
            </>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              Add
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
