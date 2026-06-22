"use client";

import { useState } from "react";
import { Loader2, Copy, Check } from "lucide-react";
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
import { ftpApi } from "@/lib/ftp";
import { ApiError } from "@/lib/api-client";

interface CreateFtpAccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateFtpAccountDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateFtpAccountDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdPassword, setCreatedPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [username, setUsername] = useState("");
  const [homeDirectory, setHomeDirectory] = useState("");
  const [quotaMb, setQuotaMb] = useState("0");
  const [maxFiles, setMaxFiles] = useState("0");

  function resetForm() {
    setUsername("");
    setHomeDirectory("");
    setQuotaMb("0");
    setMaxFiles("0");
    setError(null);
    setCreatedPassword(null);
    setCopied(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await ftpApi.create({
        username,
        home_directory: homeDirectory,
        quota_mb: parseInt(quotaMb, 10) || 0,
        max_files: parseInt(maxFiles, 10) || 0,
      });
      setCreatedPassword(result.password);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create FTP account");
    } finally {
      setLoading(false);
    }
  }

  function handleClose(next: boolean) {
    if (!next) resetForm();
    onOpenChange(next);
  }

  async function copyPassword() {
    if (!createdPassword) return;
    await navigator.clipboard.writeText(createdPassword);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create FTP Account</DialogTitle>
          <DialogDescription>
            Provision a new PureFTPD virtual user with directory and quota limits.
          </DialogDescription>
        </DialogHeader>

        {createdPassword ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Account created. Save the password — it will not be shown again.
            </p>
            <div className="flex items-center gap-2 rounded-lg border bg-muted/50 p-3">
              <code className="flex-1 text-xs font-mono break-all">{createdPassword}</code>
              <Button variant="ghost" size="sm" onClick={copyPassword}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            <DialogFooter>
              <Button onClick={() => handleClose(false)}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ftp-username">Username</Label>
              <Input
                id="ftp-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="myuser"
                required
                minLength={2}
                maxLength={31}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ftp-directory">Home directory</Label>
              <Input
                id="ftp-directory"
                value={homeDirectory}
                onChange={(e) => setHomeDirectory(e.target.value)}
                placeholder="public_html"
              />
              <p className="text-xs text-muted-foreground">Relative to your site root. Empty = site root.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="ftp-quota">Quota (MB)</Label>
                <Input
                  id="ftp-quota"
                  type="number"
                  min={0}
                  value={quotaMb}
                  onChange={(e) => setQuotaMb(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ftp-max-files">Max files</Label>
                <Input
                  id="ftp-max-files"
                  type="number"
                  min={0}
                  value={maxFiles}
                  onChange={(e) => setMaxFiles(e.target.value)}
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleClose(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                Create
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
