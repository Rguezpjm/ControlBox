"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { mailApi, type TenantMailService } from "@/lib/mail";
import { ApiError } from "@/lib/api-client";

interface CreateMailboxDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  service: TenantMailService;
  onCreated: () => void;
}

export function CreateMailboxDialog({ open, onOpenChange, service, onCreated }: CreateMailboxDialogProps) {
  const [localPart, setLocalPart] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [quotaMb, setQuotaMb] = useState(String(service.default_quota_mb));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdPassword, setCreatedPassword] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await mailApi.createAccountById(service.id, {
        local_part: localPart,
        display_name: displayName,
        password: password || undefined,
        quota_mb: Number(quotaMb) || service.default_quota_mb,
      });
      setCreatedPassword(result.password);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create mailbox");
    } finally {
      setLoading(false);
    }
  }

  function handleClose(next: boolean) {
    if (!next) {
      setLocalPart("");
      setDisplayName("");
      setPassword("");
      setQuotaMb(String(service.default_quota_mb));
      setCreatedPassword(null);
      setError(null);
    }
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create mailbox</DialogTitle>
          <DialogDescription>
            New user on <strong>{service.mail_domain}</strong>
          </DialogDescription>
        </DialogHeader>

        {createdPassword ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Mailbox created. Save this password — it will not be shown again.
            </p>
            <div className="rounded-lg border bg-muted/40 p-3 font-mono text-sm break-all">{createdPassword}</div>
            <DialogFooter>
              <Button onClick={() => handleClose(false)}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Email address</Label>
              <div className="flex items-center gap-1">
                <Input
                  value={localPart}
                  onChange={(e) => setLocalPart(e.target.value)}
                  placeholder="john"
                  required
                />
                <span className="text-sm text-muted-foreground whitespace-nowrap">@{service.mail_domain}</span>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Display name</Label>
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="John Doe" />
            </div>
            <div className="space-y-2">
              <Label>Password (optional — auto-generated if empty)</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} />
            </div>
            <div className="space-y-2">
              <Label>Quota (MB)</Label>
              <Input type="number" min={100} value={quotaMb} onChange={(e) => setQuotaMb(e.target.value)} />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleClose(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create mailbox
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
