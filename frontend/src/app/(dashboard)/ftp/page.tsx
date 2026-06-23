"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { Plus, FolderOpen, ScrollText, Settings } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TableSkeleton } from "@/components/skeletons";
import { CreateFtpAccountDialog } from "@/components/ftp/create-ftp-account-dialog";
import { FtpServiceSettings } from "@/components/ftp/ftp-service-settings";
import { ManageFtpAccountDialog } from "@/components/ftp/manage-ftp-account-dialog";
import { ftpApi, type FtpAccount, type FtpLogEntry, type FtpServiceStatus } from "@/lib/ftp";
import { formatDistanceToNow } from "date-fns";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    suspended: "stopped",
    pending: "pending",
    error: "error",
    running: "running",
    stopped: "stopped",
  };
  return map[status] || "pending";
}

function FtpContent() {
  const [accounts, setAccounts] = useState<FtpAccount[]>([]);
  const [logs, setLogs] = useState<FtpLogEntry[]>([]);
  const [serviceStatus, setServiceStatus] = useState<FtpServiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [manageAccount, setManageAccount] = useState<FtpAccount | null>(null);
  const [manageOpen, setManageOpen] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [accountsData, logsData, statusData] = await Promise.all([
        ftpApi.list(),
        ftpApi.logs(100),
        ftpApi.status(),
      ]);
      setAccounts(accountsData);
      setLogs(logsData);
      setServiceStatus(statusData);
    } catch {
      setAccounts([]);
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function openManage(account: FtpAccount) {
    setManageAccount(account);
    setManageOpen(true);
  }

  if (loading) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="FTP Manager"
        description="FTP, FTPS y SFTP — cuentas, cuotas y logs de transferencia"
        action={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setSettingsOpen(true)}>
              <Settings className="h-4 w-4" />
            </Button>
            <Button onClick={() => setCreateOpen(true)} disabled={!serviceStatus?.enabled || !serviceStatus?.running}>
              <Plus className="h-4 w-4" />
              Create Account
            </Button>
          </div>
        }
      />

      <Tabs defaultValue="accounts">
        <TabsList>
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
          <TabsTrigger value="logs">Transfer Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="accounts" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Username</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Directory</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">Quota</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden lg:table-cell">Last Login</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                      <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                          No FTP accounts yet. Create your first account to get started.
                        </td>
                      </tr>
                    ) : (
                      accounts.map((account) => (
                        <tr key={account.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-4 w-4 text-muted-foreground" />
                              <span className="font-medium font-mono text-xs">{account.username}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                            /{account.home_directory || ""}
                          </td>
                          <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                            {account.quota_mb > 0 ? `${account.quota_mb} MB` : "Unlimited"}
                          </td>
                          <td className="px-4 py-3 hidden lg:table-cell text-muted-foreground text-xs">
                            {account.last_login_at
                              ? formatDistanceToNow(new Date(account.last_login_at), { addSuffix: true })
                              : "Never"}
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={mapStatus(account.status)} />
                          </td>
                          <td className="px-4 py-3 text-right space-x-1">
                            <Button variant="ghost" size="sm" onClick={() => openManage(account)}>
                              Manage
                            </Button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Time</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">User</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Action</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">Path</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden lg:table-cell">Size</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                          <ScrollText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          No transfer logs available.
                        </td>
                      </tr>
                    ) : (
                      logs.map((log, i) => (
                        <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                            {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">{log.username}</td>
                          <td className="px-4 py-3 capitalize text-xs">{log.action}</td>
                          <td className="px-4 py-3 hidden md:table-cell font-mono text-xs text-muted-foreground truncate max-w-[200px]">
                            {log.path || "—"}
                          </td>
                          <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                            {log.bytes_transferred > 0 ? formatBytes(log.bytes_transferred) : "—"}
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">{log.ip_address || "—"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <CreateFtpAccountDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={loadData}
      />

      <ManageFtpAccountDialog
        account={manageAccount}
        open={manageOpen}
        onOpenChange={setManageOpen}
        onUpdated={loadData}
      />

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>FTP Service Settings</DialogTitle>
          </DialogHeader>
          <FtpServiceSettings serviceStatus={serviceStatus} onUpdated={loadData} inModal />
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function FtpPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <FtpContent />
    </Suspense>
  );
}
