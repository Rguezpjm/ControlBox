"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2, Trash2, KeyRound, Copy, Check, Shield, ScrollText } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/shared/status-badge";
import { ftpApi, type FtpAccount, type FtpLogEntry } from "@/lib/ftp";
import { ApiError } from "@/lib/api-client";
import { formatBytes } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    suspended: "stopped",
    pending: "pending",
    error: "error",
  };
  return map[status] || "pending";
}

interface ManageFtpAccountDialogProps {
  account: FtpAccount | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function ManageFtpAccountDialog({
  account,
  open,
  onOpenChange,
  onUpdated,
}: ManageFtpAccountDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [logs, setLogs] = useState<FtpLogEntry[]>([]);

  const [homeDirectory, setHomeDirectory] = useState("");
  const [quotaMb, setQuotaMb] = useState("0");
  const [maxFiles, setMaxFiles] = useState("0");

  const loadLogs = useCallback(async () => {
    if (!account) return;
    try {
      const data = await ftpApi.accountLogs(account.id, 50);
      setLogs(data);
    } catch {
      setLogs([]);
    }
  }, [account]);

  useEffect(() => {
    if (open && account) {
      setHomeDirectory(account.home_directory);
      setQuotaMb(String(account.quota_mb));
      setMaxFiles(String(account.max_files));
      setNewPassword(null);
      setCopied(false);
      setError(null);
      loadLogs();
    }
  }, [open, account, loadLogs]);

  async function handleChangePassword() {
    if (!account) return;
    setLoading(true);
    setError(null);
    try {
      const result = await ftpApi.changePassword(account.id);
      setNewPassword(result.password);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to change password");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetDirectory() {
    if (!account) return;
    setLoading(true);
    setError(null);
    try {
      await ftpApi.setDirectory(account.id, homeDirectory);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update directory");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetQuota() {
    if (!account) return;
    setLoading(true);
    setError(null);
    try {
      await ftpApi.setQuota(account.id, parseInt(quotaMb, 10) || 0, parseInt(maxFiles, 10) || 0);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update quota");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleStatus() {
    if (!account) return;
    setLoading(true);
    setError(null);
    const next = account.status === "active" ? "suspended" : "active";
    try {
      const result = await ftpApi.setStatus(account.id, next);
      if (result.password) setNewPassword(result.password);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update status");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!account || !confirm("Delete this FTP account permanently?")) return;
    setLoading(true);
    setError(null);
    try {
      await ftpApi.delete(account.id);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete account");
    } finally {
      setLoading(false);
    }
  }

  async function copyPassword() {
    if (!newPassword) return;
    await navigator.clipboard.writeText(newPassword);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!account) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <DialogTitle className="font-mono">{account.username}</DialogTitle>
              <DialogDescription className="font-mono text-xs">
                {account.system_username}
              </DialogDescription>
            </div>
            <StatusBadge status={mapStatus(account.status)} />
          </div>
        </DialogHeader>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {newPassword && (
          <div className="flex items-center gap-2 rounded-lg border bg-muted/50 p-3">
            <code className="flex-1 text-xs font-mono break-all">{newPassword}</code>
            <Button variant="ghost" size="sm" onClick={copyPassword}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        )}

        <Tabs defaultValue="settings">
          <TabsList className="w-full">
            <TabsTrigger value="settings" className="flex-1">Settings</TabsTrigger>
            <TabsTrigger value="logs" className="flex-1">Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="settings" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Home directory</Label>
              <div className="flex gap-2">
                <Input
                  value={homeDirectory}
                  onChange={(e) => setHomeDirectory(e.target.value)}
                  placeholder="public_html"
                />
                <Button variant="outline" onClick={handleSetDirectory} disabled={loading}>
                  Save
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Quota (MB)</Label>
                <Input
                  type="number"
                  min={0}
                  value={quotaMb}
                  onChange={(e) => setQuotaMb(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Max files</Label>
                <Input
                  type="number"
                  min={0}
                  value={maxFiles}
                  onChange={(e) => setMaxFiles(e.target.value)}
                />
              </div>
            </div>
            <Button variant="outline" className="w-full" onClick={handleSetQuota} disabled={loading}>
              Update quota
            </Button>

            <div className="flex gap-2 pt-2 border-t">
              <Button variant="outline" className="flex-1" onClick={handleChangePassword} disabled={loading}>
                <KeyRound className="h-4 w-4" />
                Reset password
              </Button>
              <Button variant="outline" className="flex-1" onClick={handleToggleStatus} disabled={loading}>
                <Shield className="h-4 w-4" />
                {account.status === "active" ? "Suspend" : "Activate"}
              </Button>
            </div>

            <Button variant="destructive" className="w-full" onClick={handleDelete} disabled={loading}>
              <Trash2 className="h-4 w-4" />
              Delete account
            </Button>
          </TabsContent>

          <TabsContent value="logs" className="mt-4">
            {logs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No log entries found.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {logs.map((log, i) => (
                  <div key={i} className="rounded-lg border p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium capitalize">{log.action}</span>
                      <span className="text-muted-foreground">
                        {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                      </span>
                    </div>
                    {log.path && <p className="font-mono text-muted-foreground truncate">{log.path}</p>}
                    <div className="flex gap-3 text-muted-foreground mt-1">
                      {log.bytes_transferred > 0 && <span>{formatBytes(log.bytes_transferred)}</span>}
                      {log.ip_address && <span>{log.ip_address}</span>}
                      <span className="capitalize">{log.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Button variant="ghost" size="sm" className="w-full mt-2" onClick={loadLogs}>
              <ScrollText className="h-4 w-4" />
              Refresh logs
            </Button>
          </TabsContent>
        </Tabs>

        {loading && (
          <div className="flex justify-center py-2">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
