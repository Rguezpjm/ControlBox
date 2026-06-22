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
import { mailApi } from "@/lib/mail";
import { ApiError } from "@/lib/api-client";

interface CreateTenantMailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateTenantMailDialog({ open, onOpenChange, onCreated }: CreateTenantMailDialogProps) {
  const [name, setName] = useState("");
  const [mailDomain, setMailDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await mailApi.createService({ name, mail_domain: mailDomain });
      onOpenChange(false);
      setName("");
      setMailDomain("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create tenant email");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Tenant Email</DialogTitle>
          <DialogDescription>
            Set up email for your organization (Microsoft 365-style). You will configure the mail server connection next.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="mail-org">Organization name</Label>
            <Input
              id="mail-org"
              placeholder="Acme Corp"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mail-domain">Primary mail domain</Label>
            <Input
              id="mail-domain"
              placeholder="example.com"
              value={mailDomain}
              onChange={(e) => setMailDomain(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
