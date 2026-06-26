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
import { teamApi, type LiteUser, type TeamRole } from "@/lib/team";

interface InviteMemberDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: () => void;
}

export function InviteMemberDialog({ open, onOpenChange, onInvited }: InviteMemberDialogProps) {
  const [roles, setRoles] = useState<TeamRole[]>([]);
  const [tenants, setTenants] = useState<{ id: string; name: string }[]>([]);
  const [tenantUsers, setTenantUsers] = useState<LiteUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingTenants, setLoadingTenants] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [roleSlug, setRoleSlug] = useState("");
  const [message, setMessage] = useState("");
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [selectedSenderUserId, setSelectedSenderUserId] = useState("");

  useEffect(() => {
    if (open) {
      setError(null);
      setSelectedTenantId("");
      setSelectedSenderUserId("");
      setTenantUsers([]);

      teamApi.listRoles().then((data) => {
        const invitable = data.filter((r) => r.slug !== "owner");
        setRoles(invitable);
        if (invitable.length > 0) setRoleSlug(invitable[0].slug);
      }).catch(() => setRoles([]));

      setLoadingTenants(true);
      teamApi.listTenants().then((data) => {
        setTenants(data);
      }).catch(() => setTenants([]))
      .finally(() => setLoadingTenants(false));
    }
  }, [open]);

  useEffect(() => {
    if (!selectedTenantId) {
      setTenantUsers([]);
      setSelectedSenderUserId("");
      return;
    }
    setLoadingUsers(true);
    setSelectedSenderUserId("");
    teamApi.listTenantUsers(selectedTenantId).then((data) => {
      setTenantUsers(data);
    }).catch(() => setTenantUsers([]))
    .finally(() => setLoadingUsers(false));
  }, [selectedTenantId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await teamApi.invite({
        email,
        team_role_slug: roleSlug,
        message,
        tenant_id: selectedTenantId || undefined,
        sender_user_id: selectedSenderUserId || undefined,
      });
      onOpenChange(false);
      setEmail("");
      setMessage("");
      onInvited();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send invitation");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Invite Team Member</DialogTitle>
          <DialogDescription>
            Send an email invitation with a specific role and permissions.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Select value={roleSlug} onValueChange={setRoleSlug}>
              <SelectTrigger>
                <SelectValue placeholder="Select role" />
              </SelectTrigger>
              <SelectContent>
                {roles.map((role) => (
                  <SelectItem key={role.slug} value={role.slug}>
                    {role.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Tenant (optional)</Label>
            <Select
              value={selectedTenantId}
              onValueChange={setSelectedTenantId}
              disabled={loadingTenants}
            >
              <SelectTrigger>
                <SelectValue placeholder={loadingTenants ? "Loading tenants..." : "All tenants"} />
              </SelectTrigger>
              <SelectContent>
                {tenants.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedTenantId && (
            <div className="space-y-2">
              <Label>Sender user (optional)</Label>
              <Select
                value={selectedSenderUserId}
                onValueChange={setSelectedSenderUserId}
                disabled={loadingUsers}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={loadingUsers ? "Loading users..." : "Select sender"}
                  />
                </SelectTrigger>
                <SelectContent>
                  {tenantUsers.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.full_name} ({u.email})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="invite-message">Message (optional)</Label>
            <textarea
              id="invite-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !email || !roleSlug}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Send Invitation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
