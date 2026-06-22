"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Loader2,
  Trash2,
  KeyRound,
  UserPlus,
  Archive,
  RotateCcw,
  Copy,
  Check,
} from "lucide-react";
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
import {
  databasesApi,
  type ManagedDatabase,
  type DatabaseUser,
  type DatabaseBackup,
} from "@/lib/databases";
import { ApiError } from "@/lib/api-client";
import { formatBytes } from "@/lib/utils";
import type { ResourceStatus } from "@/types";

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    active: "running",
    running: "running",
    completed: "running",
    stopped: "stopped",
    pending: "pending",
    restoring: "pending",
    deleting: "pending",
    error: "error",
    failed: "error",
  };
  return map[status] || "pending";
}

interface ManageDatabaseDialogProps {
  database: ManagedDatabase | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function ManageDatabaseDialog({
  database,
  open,
  onOpenChange,
  onUpdated,
}: ManageDatabaseDialogProps) {
  const [users, setUsers] = useState<DatabaseUser[]>([]);
  const [backups, setBackups] = useState<DatabaseBackup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [newUsername, setNewUsername] = useState("");
  const [userMaxConn, setUserMaxConn] = useState("10");
  const [dbMaxConn, setDbMaxConn] = useState("50");
  const [backupName, setBackupName] = useState("");

  const loadData = useCallback(async () => {
    if (!database) return;
    setLoading(true);
    setError(null);
    try {
      const [usersData, backupsData] = await Promise.all([
        databasesApi.listUsers(database.id),
        databasesApi.listBackups(database.id),
      ]);
      setUsers(usersData);
      setBackups(backupsData);
      setDbMaxConn(String(database.max_connections));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [database]);

  useEffect(() => {
    if (open && database) {
      loadData();
      setNewPassword(null);
      setCopied(false);
    }
  }, [open, database, loadData]);

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!database) return;
    setLoading(true);
    setError(null);
    try {
      const result = await databasesApi.createUser(database.id, {
        username: newUsername,
        max_connections: parseInt(userMaxConn, 10) || 10,
      });
      setNewPassword(result.password);
      setNewUsername("");
      await loadData();
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create user");
    } finally {
      setLoading(false);
    }
  }

  async function handleChangePassword(userId: string) {
    if (!database) return;
    setLoading(true);
    setError(null);
    try {
      const result = await databasesApi.changePassword(database.id, userId);
      setNewPassword(result.password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to change password");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteUser(userId: string) {
    if (!database) return;
    setLoading(true);
    try {
      await databasesApi.deleteUser(database.id, userId);
      await loadData();
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete user");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetUserConnLimit(userId: string, max: number) {
    if (!database) return;
    setLoading(true);
    try {
      await databasesApi.setUserConnectionLimit(database.id, userId, max);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update limit");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetDbConnLimit(e: React.FormEvent) {
    e.preventDefault();
    if (!database) return;
    setLoading(true);
    try {
      await databasesApi.setConnectionLimit(database.id, parseInt(dbMaxConn, 10) || 50);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update limit");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBackup(e: React.FormEvent) {
    e.preventDefault();
    if (!database) return;
    setLoading(true);
    try {
      await databasesApi.createBackup(database.id, backupName || undefined);
      setBackupName("");
      await loadData();
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create backup");
    } finally {
      setLoading(false);
    }
  }

  async function handleRestore(backupId: string) {
    if (!database) return;
    setLoading(true);
    try {
      await databasesApi.restoreBackup(database.id, backupId);
      await loadData();
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to restore backup");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteBackup(backupId: string) {
    if (!database) return;
    setLoading(true);
    try {
      await databasesApi.deleteBackup(database.id, backupId);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete backup");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteDatabase() {
    if (!database || !confirm("Delete this database and all users?")) return;
    setLoading(true);
    try {
      await databasesApi.delete(database.id);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete database");
    } finally {
      setLoading(false);
    }
  }

  function copyPassword() {
    if (newPassword) {
      navigator.clipboard.writeText(newPassword);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  if (!database) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {database.name}
            <StatusBadge status={mapStatus(database.status)} />
          </DialogTitle>
          <DialogDescription>
            {database.engine} · {database.host}:{database.port} · {database.database_name}
          </DialogDescription>
        </DialogHeader>

        {newPassword && (
          <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
            <p className="font-medium mb-1">Generated password (copy now):</p>
            <div className="flex items-center gap-2 font-mono">
              <span className="flex-1 break-all">{newPassword}</span>
              <Button size="sm" variant="outline" onClick={copyPassword}>
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Tabs defaultValue="users">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="backups">Backups</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="users" className="space-y-4 mt-4">
            <form onSubmit={handleCreateUser} className="flex flex-wrap gap-2 items-end">
              <div className="space-y-1 flex-1 min-w-[120px]">
                <Label htmlFor="new-user">Username</Label>
                <Input
                  id="new-user"
                  placeholder="app_user"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                  pattern="[a-z][a-z0-9_]{1,30}"
                />
              </div>
              <div className="space-y-1 w-24">
                <Label>Max conn.</Label>
                <Input
                  type="number"
                  min={1}
                  max={500}
                  value={userMaxConn}
                  onChange={(e) => setUserMaxConn(e.target.value)}
                />
              </div>
              <Button type="submit" size="sm" disabled={loading}>
                <UserPlus className="h-4 w-4" />
                Add
              </Button>
            </form>

            {loading && users.length === 0 ? (
              <div className="flex justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : users.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No users yet</p>
            ) : (
              <div className="space-y-2">
                {users.map((user) => (
                  <div
                    key={user.id}
                    className="flex items-center justify-between rounded-lg border p-3 text-sm"
                  >
                    <div>
                      <p className="font-medium font-mono">{user.username}</p>
                      <p className="text-xs text-muted-foreground">
                        host: {user.host} · max: {user.max_connections}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleChangePassword(user.id)}
                        disabled={loading}
                      >
                        <KeyRound className="h-3 w-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const val = prompt("Max connections:", String(user.max_connections));
                          if (val) handleSetUserConnLimit(user.id, parseInt(val, 10));
                        }}
                        disabled={loading}
                      >
                        Limit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteUser(user.id)}
                        disabled={loading}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="backups" className="space-y-4 mt-4">
            <form onSubmit={handleCreateBackup} className="flex gap-2 items-end">
              <div className="space-y-1 flex-1">
                <Label htmlFor="backup-name">Backup name (optional)</Label>
                <Input
                  id="backup-name"
                  placeholder="manual-backup"
                  value={backupName}
                  onChange={(e) => setBackupName(e.target.value)}
                />
              </div>
              <Button type="submit" size="sm" disabled={loading}>
                <Archive className="h-4 w-4" />
                Backup
              </Button>
            </form>

            {backups.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No backups yet</p>
            ) : (
              <div className="space-y-2">
                {backups.map((backup) => (
                  <div
                    key={backup.id}
                    className="flex items-center justify-between rounded-lg border p-3 text-sm"
                  >
                    <div>
                      <p className="font-medium">{backup.name}</p>
                      <p className="text-xs text-muted-foreground">
                        <StatusBadge status={mapStatus(backup.status)} /> ·{" "}
                        {formatBytes(backup.size_mb * 1024 * 1024)} ·{" "}
                        {new Date(backup.created_at).toLocaleString()}
                      </p>
                      {backup.error_message && (
                        <p className="text-xs text-destructive mt-1">{backup.error_message}</p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      {backup.status === "completed" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRestore(backup.id)}
                          disabled={loading}
                        >
                          <RotateCcw className="h-3 w-3" />
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteBackup(backup.id)}
                        disabled={loading}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="settings" className="space-y-4 mt-4">
            <form onSubmit={handleSetDbConnLimit} className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="db-max-conn">Database connection limit</Label>
                <Input
                  id="db-max-conn"
                  type="number"
                  min={1}
                  max={1000}
                  value={dbMaxConn}
                  onChange={(e) => setDbMaxConn(e.target.value)}
                />
              </div>
              <Button type="submit" size="sm" disabled={loading}>
                Save limit
              </Button>
            </form>

            {database.error_message && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {database.error_message}
              </div>
            )}

            <div className="pt-4 border-t">
              <Button variant="destructive" size="sm" onClick={handleDeleteDatabase} disabled={loading}>
                <Trash2 className="h-4 w-4" />
                Delete database
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
