"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Inbox, Mail, Plus, Trash2, ExternalLink, Server } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

function EmailList({
  services,
  onSelect,
  onCreate,
}: {
  services: TenantMailService[];
  onSelect: (id: string) => void;
  onCreate: () => void;
}) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Email"
        description="Tenant email services — manage multiple domains"
        action={
          <Button onClick={onCreate}>
            <Plus className="h-4 w-4 mr-2" />
            Create Tenant Email
          </Button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {services.map((svc) => (
          <Card
            key={svc.id}
            className="cursor-pointer transition-colors hover:border-primary/50"
            onClick={() => onSelect(svc.id)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Server className="h-4 w-4 text-muted-foreground" />
                    {svc.name}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">{svc.mail_domain}</p>
                </div>
                <StatusBadge status={mapStatus(svc.status)} />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                Created {new Date(svc.created_at).toLocaleDateString()}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function EmailDetail({
  service,
  onBack,
  onUpdated,
}: {
  service: TenantMailService;
  onBack: () => void;
  onUpdated: () => void;
}) {
  const [overview, setOverview] = useState<MailOverview | null>(null);
  const [accounts, setAccounts] = useState<MailAccount[]>([]);
  const [createMailboxOpen, setCreateMailboxOpen] = useState(false);

  const loadDetail = useCallback(async () => {
    if (service.status !== "active") return;
    try {
      const [overviewData, accountData] = await Promise.all([
        mailApi.overviewById(service.id),
        mailApi.listAccountsById(service.id),
      ]);
      setOverview(overviewData);
      setAccounts(accountData);
    } catch {
      setOverview(null);
      setAccounts([]);
    }
  }, [service.id, service.status]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  async function handleDeleteAccount(id: string) {
    if (!window.confirm("Delete this mailbox?")) return;
    await mailApi.deleteAccountById(service.id, id);
    await loadDetail();
  }

  const isActive = service.status === "active";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to tenants
        </button>
      </div>
      <PageHeader
        title={`${service.name} — ${service.mail_domain}`}
        description={`Manage mailboxes and configuration for this tenant`}
        action={
          isActive ? (
            <Button onClick={() => setCreateMailboxOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create mailbox
            </Button>
          ) : undefined
        }
      />

      {!isActive && <MailServiceSetup service={service} onUpdated={onUpdated} />}

      {isActive && overview && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard title="Accounts" value={overview.accounts_count} icon={Mail} />
            <StatCard
              title="Storage used"
              value={formatBytes(overview.total_used_mb * 1024 * 1024)}
              description={`of ${formatBytes(overview.total_quota_mb * 1024 * 1024)} quota`}
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

      <CreateMailboxDialog
        open={createMailboxOpen}
        onOpenChange={setCreateMailboxOpen}
        service={service}
        onCreated={() => { void loadDetail(); }}
      />
    </div>
  );
}

function EmailContent() {
  const [services, setServices] = useState<TenantMailService[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [selectedService, setSelectedService] = useState<TenantMailService | null>(null);
  const [initialLoad, setInitialLoad] = useState(true);
  const [createTenantOpen, setCreateTenantOpen] = useState(false);

  const loadServices = useCallback(async () => {
    try {
      const data = await mailApi.listServices();
      setServices(data);
      if (data.length === 0) {
        setSelectedServiceId(null);
        setSelectedService(null);
      }
    } catch {
      setServices([]);
    } finally {
      setInitialLoad(false);
    }
  }, []);

  const loadSelectedService = useCallback(async () => {
    if (!selectedServiceId) return;
    try {
      const data = await mailApi.getServiceById(selectedServiceId);
      setSelectedService(data);
    } catch {
      setSelectedService(null);
    }
  }, [selectedServiceId]);

  useEffect(() => {
    void loadServices();
  }, [loadServices]);

  useEffect(() => {
    void loadSelectedService();
  }, [loadSelectedService]);

  function handleSelectService(id: string) {
    setSelectedServiceId(id);
  }

  function handleBackToList() {
    setSelectedServiceId(null);
    setSelectedService(null);
    void loadServices();
  }

  function handleCreated() {
    void loadServices();
    setCreateTenantOpen(false);
  }

  function handleUpdated() {
    if (selectedServiceId) {
      void loadSelectedService();
    } else {
      void loadServices();
    }
  }

  if (initialLoad) return <TableSkeleton />;

  if (services.length === 0 && !selectedServiceId) {
    return (
      <div className="space-y-6">
        <PageHeader title="Email" description="Tenant email services — manage multiple domains" />
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
              <Mail className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold">No tenant email configured</h3>
            <p className="mt-2 max-w-lg text-sm text-muted-foreground">
              Create a tenant email service for your organization. You can manage multiple email
              tenants, each with its own domain and mail server configuration.
            </p>
            <Button className="mt-6" onClick={() => setCreateTenantOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Tenant Email
            </Button>
          </CardContent>
        </Card>
        <CreateTenantMailDialog open={createTenantOpen} onOpenChange={setCreateTenantOpen} onCreated={handleCreated} />
      </div>
    );
  }

  if (selectedServiceId && selectedService) {
    return (
      <>
        <EmailDetail service={selectedService} onBack={handleBackToList} onUpdated={handleUpdated} />
        <CreateTenantMailDialog open={createTenantOpen} onOpenChange={setCreateTenantOpen} onCreated={handleCreated} />
      </>
    );
  }

  return (
    <>
      <EmailList services={services} onSelect={handleSelectService} onCreate={() => setCreateTenantOpen(true)} />
      <CreateTenantMailDialog open={createTenantOpen} onOpenChange={setCreateTenantOpen} onCreated={handleCreated} />
    </>
  );
}

export default function EmailPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <EmailContent />
    </Suspense>
  );
}
