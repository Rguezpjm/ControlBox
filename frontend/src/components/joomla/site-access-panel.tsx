"use client";

import { useState } from "react";
import { ExternalLink, KeyRound, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CredentialRow } from "@/components/wordpress/credential-row";
import { joomlaApi, type JoomlaSiteAccessInfo } from "@/lib/joomla";
import { ApiError } from "@/lib/api-client";
import { toast } from "sonner";

interface JoomlaSiteAccessPanelProps {
  siteId: string;
  access: JoomlaSiteAccessInfo | null | undefined;
  siteStatus: string;
  onUpdated?: () => void;
  /** Render only inner content (no Card wrapper) for split layouts */
  embedded?: boolean;
}

export function JoomlaSiteAccessPanel({
  siteId,
  access,
  siteStatus,
  onUpdated,
  embedded = false,
}: JoomlaSiteAccessPanelProps) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const canChangePassword = siteStatus === "running";

  async function handleChangePassword() {
    if (newPassword.length < 8) {
      toast.error("La contraseña debe tener al menos 8 caracteres");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("Las contraseñas no coinciden");
      return;
    }
    setSaving(true);
    try {
      await joomlaApi.changeAdminPassword(siteId, newPassword);
      toast.success("Contraseña de administrador actualizada en Joomla");
      setNewPassword("");
      setConfirmPassword("");
      onUpdated?.();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña");
    } finally {
      setSaving(false);
    }
  }

  const info = access ?? {
    site_url: "",
    login_url: "",
    admin_user: "",
    admin_email: "",
  };

  const content = (
    <div className="space-y-6">
      <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
        <p className="text-sm font-medium">Joomla</p>
        <CredentialRow label="URL del sitio" value={info.site_url} href={info.site_url} />
        <CredentialRow label="URL de login (administrator)" value={info.login_url} href={info.login_url} mono />
        <CredentialRow label="Usuario admin" value={info.admin_user} />
        <CredentialRow label="Email admin" value={info.admin_email} />
        {info.login_url ? (
          <Button asChild variant="secondary" className="w-full sm:w-auto">
            <a href={info.login_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              Abrir panel Joomla
            </a>
          </Button>
        ) : null}
      </div>

      {(info.db_name || info.db_user || info.db_host) && (
        <div className="space-y-3 rounded-lg border p-4">
          <p className="text-sm font-medium">Base de datos MySQL</p>
          <CredentialRow label="DB_NAME" value={info.db_name} mono />
          <CredentialRow label="DB_USER" value={info.db_user} mono />
          <CredentialRow label="DB_PASSWORD" value={info.db_password} secret mono />
          <CredentialRow label="DB_HOST" value={info.db_host} mono />
        </div>
      )}

      {(info.ftp_username || info.ftp_password || info.ftp_home) && (
        <div className="space-y-3 rounded-lg border p-4">
          <p className="text-sm font-medium">FTP</p>
          <CredentialRow label="FTP user" value={info.ftp_username} mono />
          <CredentialRow label="FTP password" value={info.ftp_password} secret mono />
          <CredentialRow label="FTP directory" value={info.ftp_home} mono />
        </div>
      )}

      <div className="space-y-3 rounded-lg border p-4">
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-muted-foreground" />
          <p className="text-sm font-medium">Cambiar contraseña admin</p>
        </div>
        {!canChangePassword ? (
          <p className="text-xs text-muted-foreground">
            Disponible cuando el sitio esté en estado <strong>running</strong> (Joomla instalado).
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="joomla-new-password">Nueva contraseña</Label>
              <Input
                id="joomla-new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="joomla-confirm-password">Confirmar</Label>
              <Input
                id="joomla-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="sm:col-span-2">
              <Button onClick={handleChangePassword} disabled={saving || !newPassword}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Actualizar contraseña
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Acceso al sitio</CardTitle>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  );
}
