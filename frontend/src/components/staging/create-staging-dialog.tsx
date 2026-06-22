"use client";

import { useEffect, useState } from "react";
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
import { ApiError } from "@/lib/api-client";
import { stagingApi } from "@/lib/staging";
import { wordpressApi, type WordPressSite } from "@/lib/wordpress";
import { websitesApi, type Website } from "@/lib/websites";

interface CreateStagingDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateStagingDialog({ open, onOpenChange, onCreated }: CreateStagingDialogProps) {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [wpSites, setWpSites] = useState<WordPressSite[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceType, setSourceType] = useState<"website" | "wordpress">("wordpress");
  const [sourceId, setSourceId] = useState("");
  const [domainMode, setDomainMode] = useState<"subdomain" | "random">("subdomain");
  const [name, setName] = useState("");

  useEffect(() => {
    if (open) {
      Promise.all([websitesApi.list(), wordpressApi.list()])
        .then(([w, wp]) => {
          setWebsites(w.filter((s) => s.status === "running"));
          setWpSites(wp.filter((s) => s.status === "running" && !s.is_staging));
        })
        .catch(() => {
          setWebsites([]);
          setWpSites([]);
        });
    }
  }, [open]);

  const sources = sourceType === "wordpress" ? wpSites : websites;

  useEffect(() => {
    if (sources.length > 0) setSourceId(sources[0].id);
    else setSourceId("");
  }, [sourceType, sources]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!sourceId) return;
    setLoading(true);
    setError(null);
    try {
      await stagingApi.create({
        source_type: sourceType,
        source_id: sourceId,
        domain_mode: domainMode,
        name,
      });
      onOpenChange(false);
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create staging");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Staging Environment</DialogTitle>
          <DialogDescription>
            Clone production into an isolated staging environment with separate database and containers.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Source Type</Label>
            <Select value={sourceType} onValueChange={(v) => setSourceType(v as "website" | "wordpress")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="wordpress">WordPress</SelectItem>
                <SelectItem value="website">Website</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Production Site</Label>
            <Select value={sourceId} onValueChange={setSourceId}>
              <SelectTrigger>
                <SelectValue placeholder="Select site" />
              </SelectTrigger>
              <SelectContent>
                {sources.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name} ({s.domain})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Staging Domain</Label>
            <Select value={domainMode} onValueChange={(v) => setDomainMode(v as "subdomain" | "random")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="subdomain">staging.example.com</SelectItem>
                <SelectItem value="random">randomid.staging.example.com</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="stg-name">Name (optional)</Label>
            <Input id="stg-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !sourceId}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Staging
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
