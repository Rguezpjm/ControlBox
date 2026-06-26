"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { Inbox, Mail, Plus, Trash2, ExternalLink } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TableSkeleton } from "@/components/skeletons";
import { CreateTenantMailDialog } from "@/components/mail/create-tenant-mail-dialog";
import { MailServiceSetup } from "@/components/mail/mail-service-setup";
import { CreateMailboxDialog } from "@/components/mail/create-mailbox-dialog";
import { mailApi, type MailAccount, type MailOverview, type TenantMailService } from "@/lib/mail";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    suspended: "stopped",
    pending: "pending",
    error: "error",
    configuring: "pending",
  };
  return map[status] || "pending";
}

function EmailContent() {
  const [overview, setOverview] = useState<MailOverview | null>(null);
  const [service, setService] = useState<TenantMailService | null>(null);
  const [accounts, setAccounts] = useState<MailAccount[]>([]);
  const [initialLoad, setInitialLoad] = useState(true);
  const [createTenantOpen, setCreateTenantOpen] = useState(false);
  const [createMailboxOpen, setCreateMailboxOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const [overviewData, serviceData] = await Promise.all([
        mailApi.overview(),
        mailApi.getService(),
      ]);
      setOverview(overviewData);
      setService(serviceData);

      if (serviceData?.status === "active") {
        const accountData = await mailApi.listAccounts();
        setAccounts(accountData);
      } else {
        setAccounts([]);
      }
    } catch {
      setOverview(null);
      setService(null);
      setAccounts([]);
    } finally {
      setInitialLoad(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleDeleteAccount(id: string) {
    if (!window.confirm("Delete this mailbox?")) return;
    await mailApi.deleteAccount(id);
    await load();
  }

  if (initialLoad) return <TableSkeleton />;

  if (!service) {
    return (
      <div className="space-y-6">
        <PageHeader title="Email" description="Tenant email — Microsoft 365-style organization mail" />
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
              <Mail className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold">No tenant email configured</h3>
            <p className="mt-2 max-w-lg text-sm text-muted-foreground">
              Create a tenant email service for your organization. You will configure DNS and mail server
              connection before adding mailboxes — no demo or sample accounts are created automatically.
            </p>
            <Button className="mt-6" onClick={() => setCreateTenantOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Tenant Email
            </Button>
          </CardContent>
        </Card>
        <CreateTenantMailDialog open={createTenantOpen} onOpenChange={setCreateTenantOpen} onCreated={load} />
      </div>
    );
  }

  const isActive = service.status === "active";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Email"
        description={`Tenant mail for ${service.mail_domain}`}
        action={
          isActive ? (
            <Button onClick={() => setCreateMailboxOpen(true)}>
              <Plus className="h-4 w-4" />
              Create mailbox
            </Button>
          ) : undefined
        }
      />

      {!isActive && <MailServiceSetup service={service} onUpdated={load} />}

      {isActive && overview && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard title="Accounts" value={overview.accounts_count} icon={Mail} />
            <StatCard
              title="Storage used"
              value={formatBytes(overview.total_used_mb * 1024 * 1024)}
              description={`of ${formatBytes(overview.total_quota_mb * 1024 * 1024)} tenant quota`}
              icon={Inbox}
            />
            <StatCard
              title="Service status"
              value="Connected"
              description={
                service.connection_verified_at
                  ? `Verified ${new Date(service.connection_verified_at).toLocaleDateString()}`
                  : "Mail server connected"
              }
              icon={Mail}
            />
          </div>

          <Card>
            <CardContent className="p-0">
              {accounts.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  No mailboxes yet. Create your first user mailbox for this tenant.
                </p>
              ) : (
                <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3">
                  {accounts.map((account) => {
                    const pct = account.quota_mb > 0 ? (account.used_mb / account.quota_mb) * 100 : 0;
                    return (
                      <div key={account.id} className="rounded-xl border p-4 space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-medium text-sm">{account.email_address}</p>
                            <p className="text-xs text-muted-foreground">{account.display_name}</p>
                          </div>
                          <StatusBadge status={mapStatus(account.status)} />
                        </div>
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>Quota</span>
                            <span>
                              {account.used_mb} MB / {account.quota_mb} MB ({pct.toFixed(0)}%)
                            </span>
                          </div>
                          <Progress value={Math.min(pct, 100)} className="h-1.5" />
                        </div>
                        <div className="flex gap-2">
                          {service.webmail_url && (
                            <Button variant="outline" size="sm" className="flex-1" asChild>
                              <a href={service.webmail_url} target="_blank" rel="noreferrer">
                                <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                                Webmail
                              </a>
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive"
                            onClick={() => void handleDeleteAccount(account.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <CreateTenantMailDialog open={createTenantOpen} onOpenChange={setCreateTenantOpen} onCreated={load} />
      {service && (
        <CreateMailboxDialog
          open={createMailboxOpen}
          onOpenChange={setCreateMailboxOpen}
          service={service}
          onCreated={load}
        />
      )}
    </div>
  );
}

export default function EmailPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <EmailContent />
    </Suspense>
  );
}
