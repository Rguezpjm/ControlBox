"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import {
  Plus,
  Users,
  Mail,
  History,
  Shield,
  MoreHorizontal,
  UserX,
  RefreshCw,
  Trash2,
  KeyRound,
  Fingerprint,
  Monitor,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { InviteMemberDialog } from "@/components/team/invite-member-dialog";
import {
  teamApi,
  type TeamActivity,
  type TeamInvitation,
  type TeamMember,
  type TeamRole,
} from "@/lib/team";

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function TeamContent() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [invitations, setInvitations] = useState<TeamInvitation[]>([]);
  const [roles, setRoles] = useState<TeamRole[]>([]);
  const [activity, setActivity] = useState<TeamActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [m, i, r, a] = await Promise.all([
        teamApi.listMembers(),
        teamApi.listInvitations(),
        teamApi.listRoles(),
        teamApi.listActivity(),
      ]);
      setMembers(m);
      setInvitations(i.filter((inv) => inv.status === "pending"));
      setRoles(r);
      setActivity(a);
    } catch {
      setMembers([]);
      setInvitations([]);
      setRoles([]);
      setActivity([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function handleRoleChange(memberId: string, slug: string) {
    await teamApi.updateRole(memberId, slug);
    loadAll();
  }

  async function handleSuspend(memberId: string) {
    await teamApi.suspend(memberId);
    loadAll();
  }

  async function handleRemove(memberId: string) {
    await teamApi.remove(memberId);
    loadAll();
  }

  async function handleResend(invitationId: string) {
    await teamApi.resendInvitation(invitationId);
    loadAll();
  }

  async function handleRevoke(invitationId: string) {
    await teamApi.revokeInvitation(invitationId);
    loadAll();
  }

  const invitableRoles = roles.filter((r) => r.slug !== "owner");

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center text-muted-foreground">
        Loading team data...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Team Members"
        description="Manage collaborators, roles, invitations and audit history."
        action={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Invite Member
          </Button>
        }
      />

      <Tabs defaultValue="members" className="space-y-4">
        <TabsList>
          <TabsTrigger value="members">
            <Users className="mr-2 h-4 w-4" />
            Members
          </TabsTrigger>
          <TabsTrigger value="invitations">
            <Mail className="mr-2 h-4 w-4" />
            Invitations
          </TabsTrigger>
          <TabsTrigger value="permissions">
            <Shield className="mr-2 h-4 w-4" />
            Permissions
          </TabsTrigger>
          <TabsTrigger value="history">
            <History className="mr-2 h-4 w-4" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="members">
          <Card>
            <CardHeader>
              <CardTitle>Active Members</CardTitle>
              <CardDescription>
                Collaborators with assigned roles and security status.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {members.map((member) => (
                <div
                  key={member.id}
                  className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium">{member.full_name || member.email}</p>
                    <p className="text-xs text-muted-foreground">{member.email}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      {member.mfa_enabled && (
                        <span className="inline-flex items-center gap-1">
                          <KeyRound className="h-3 w-3" /> MFA
                        </span>
                      )}
                      {member.passkey_count > 0 && (
                        <span className="inline-flex items-center gap-1">
                          <Fingerprint className="h-3 w-3" /> {member.passkey_count} passkeys
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1">
                        <Monitor className="h-3 w-3" /> {member.session_count} sessions
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {member.team_role_slug === "owner" ? (
                      <Badge>{member.team_role_name}</Badge>
                    ) : (
                      <Select
                        value={member.team_role_slug}
                        onValueChange={(slug) => handleRoleChange(member.id, slug)}
                      >
                        <SelectTrigger className="w-[180px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {invitableRoles.map((role) => (
                            <SelectItem key={role.slug} value={role.slug}>
                              {role.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    <Badge variant={member.status === "active" ? "default" : "secondary"}>
                      {member.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(member.joined_at)}
                    </span>
                    {member.team_role_slug !== "owner" && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleSuspend(member.id)}>
                            <UserX className="mr-2 h-4 w-4" />
                            Suspend
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => handleRemove(member.id)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Remove
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="invitations">
          <Card>
            <CardHeader>
              <CardTitle>Pending Invitations</CardTitle>
              <CardDescription>Email invitations awaiting activation.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {invitations.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No pending invitations.
                </p>
              ) : (
                invitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="flex flex-col gap-2 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="font-medium">{inv.email}</p>
                      <p className="text-xs text-muted-foreground">
                        Expires {formatDate(inv.expires_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{inv.team_role_name}</Badge>
                      <Button variant="ghost" size="icon" onClick={() => handleResend(inv.id)}>
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleRevoke(inv.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="permissions">
          <div className="grid gap-4 md:grid-cols-2">
            {roles.map((role) => (
              <Card key={role.slug}>
                <CardHeader>
                  <CardTitle className="text-base">{role.name}</CardTitle>
                  <CardDescription>{role.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-1">
                    {role.permissions.slice(0, 12).map((perm) => (
                      <Badge key={perm} variant="secondary" className="text-xs">
                        {perm}
                      </Badge>
                    ))}
                    {role.permissions.length > 12 && (
                      <Badge variant="outline" className="text-xs">
                        +{role.permissions.length - 12} more
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Activity History</CardTitle>
              <CardDescription>Team-related actions and audit events.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {activity.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No activity yet.</p>
              ) : (
                activity.map((entry) => (
                  <div key={entry.id} className="rounded-lg border p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs">{entry.action}</span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(entry.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 text-muted-foreground">
                      {entry.resource_type}
                      {entry.resource_id ? ` / ${entry.resource_id.slice(0, 8)}` : ""}
                      {entry.ip_address ? ` · ${entry.ip_address}` : ""}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <InviteMemberDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onInvited={loadAll}
      />
    </div>
  );
}

export default function TeamPage() {
  return (
    <Suspense fallback={<div className="p-6">Loading...</div>}>
      <TeamContent />
    </Suspense>
  );
}
