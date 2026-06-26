import { request } from "@/lib/api-client";

export interface TeamMember {
  id: string;
  tenant_id: string;
  user_id: string;
  email: string;
  full_name: string;
  team_role_slug: string;
  team_role_name: string;
  status: string;
  invited_by: string | null;
  joined_at: string | null;
  last_active_at: string | null;
  mfa_enabled: boolean;
  passkey_count: number;
  session_count: number;
  created_at: string;
}

export interface TeamInvitation {
  id: string;
  tenant_id: string;
  email: string;
  team_role_slug: string;
  team_role_name: string;
  status: string;
  invited_by: string | null;
  expires_at: string;
  accepted_at: string | null;
  message: string;
  created_at: string;
}

export interface TeamRole {
  id: string;
  slug: string;
  name: string;
  description: string;
  level: number;
  permissions: string[];
}

export interface TeamActivity {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface InviteMemberPayload {
  email: string;
  team_role_slug: string;
  message?: string;
  tenant_id?: string;
  sender_user_id?: string;
}

export interface LiteUser {
  id: string;
  email: string;
  full_name: string;
}

export interface AcceptInvitationPayload {
  token: string;
  full_name: string;
  password: string;
}

export const teamApi = {
  listTenants: () => request<{ id: string; name: string; slug: string }[]>("/api/v1/identity/tenants"),
  listTenantUsers: (tenantId: string) =>
    request<LiteUser[]>(`/api/v1/identity/tenants/${tenantId}/lite-users`),
  listMembers: () => request<TeamMember[]>("/api/v1/team/members"),
  listInvitations: () => request<TeamInvitation[]>("/api/v1/team/invitations"),
  listRoles: () => request<TeamRole[]>("/api/v1/team/roles"),
  listActivity: (limit = 50, offset = 0) =>
    request<TeamActivity[]>(`/api/v1/team/activity?limit=${limit}&offset=${offset}`),
  invite: (data: InviteMemberPayload) =>
    request<{ invitation: TeamInvitation; invite_url: string }>("/api/v1/team/invitations", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  resendInvitation: (id: string) =>
    request<{ invitation: TeamInvitation; invite_url: string }>(
      `/api/v1/team/invitations/${id}/resend`,
      { method: "POST" }
    ),
  revokeInvitation: (id: string) =>
    request<void>(`/api/v1/team/invitations/${id}`, { method: "DELETE" }),
  updateRole: (memberId: string, team_role_slug: string) =>
    request<TeamMember>(`/api/v1/team/members/${memberId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ team_role_slug }),
    }),
  suspend: (memberId: string) =>
    request<TeamMember>(`/api/v1/team/members/${memberId}/suspend`, { method: "POST" }),
  remove: (memberId: string) =>
    request<void>(`/api/v1/team/members/${memberId}`, { method: "DELETE" }),
  previewInvitation: (token: string) =>
    request<TeamInvitation>(`/api/v1/team/invitations/preview?token=${encodeURIComponent(token)}`),
  acceptInvitation: (data: AcceptInvitationPayload) =>
    request<TeamMember>("/api/v1/team/invitations/accept", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
