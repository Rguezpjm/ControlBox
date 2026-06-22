"use client";

import { useState, useEffect } from "react";
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
import { Switch } from "@/components/ui/switch";
import { wordpressApi, type WordPressOptions } from "@/lib/wordpress";
import { ApiError } from "@/lib/api-client";

interface CreateWordPressDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateWordPressDialog({ open, onOpenChange, onCreated }: CreateWordPressDialogProps) {
  const [options, setOptions] = useState<WordPressOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [adminUser, setAdminUser] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [phpVersion, setPhpVersion] = useState("8.3");
  const [sslEnabled, setSslEnabled] = useState(true);

  useEffect(() => {
    if (open) {
      wordpressApi.options()
        .then((opts) => {
          setOptions(opts);
          setPhpVersion(opts.php_versions[opts.php_versions.length - 1] || "8.3");
        })
        .catch(() => setOptions(null));
    }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await wordpressApi.create({
        name,
        domain,
        admin_user: adminUser,
        admin_password: adminPassword,
        admin_email: adminEmail,
        php_version: phpVersion,
        ssl_enabled: sslEnabled,
      });
      onOpenChange(false);
      setName("");
      setDomain("");
      setAdminPassword("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to deploy WordPress");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Deploy WordPress</DialogTitle>
          <DialogDescription>
            One-click WordPress with Docker, MySQL, Nginx, PHP-FPM and Let&apos;s Encrypt SSL.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="wp-name">Site Name</Label>
              <Input id="wp-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="wp-domain">Domain</Label>
              <Input
                id="wp-domain"
                placeholder="blog.example.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wp-admin">Admin Username</Label>
              <Input id="wp-admin" value={adminUser} onChange={(e) => setAdminUser(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wp-php">PHP Version</Label>
              <Select value={phpVersion} onValueChange={setPhpVersion}>
                <SelectTrigger id="wp-php">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(options?.php_versions || ["8.2", "8.3"]).map((v) => (
                    <SelectItem key={v} value={v}>
                      PHP {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="wp-password">Admin Password</Label>
              <Input
                id="wp-password"
                type="password"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="wp-email">Admin Email</Label>
              <Input
                id="wp-email"
                type="email"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <Label>SSL (Let&apos;s Encrypt)</Label>
              <p className="text-xs text-muted-foreground">Traefik auto-certificate via certresolver</p>
            </div>
            <Switch checked={sslEnabled} onCheckedChange={setSslEnabled} />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Deploy WordPress
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
