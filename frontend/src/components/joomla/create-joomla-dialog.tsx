"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Copy,
  Eye,
  EyeOff,
  ExternalLink,
  Loader2,
  RefreshCw,
  Shield,
} from "lucide-react";
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
import {
  joomlaApi,
  type JoomlaDeployCredentials,
  type JoomlaOptions,
  type JoomlaProvisionStep,
} from "@/lib/joomla";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface CreateJoomlaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

type Phase = "form" | "deploying" | "success" | "error";

function sanitizeIdentifier(raw: string): string {
  const normalized = raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const safe = normalized.replace(/_+/g, "_");
  if (!safe) return "site";
  return /^[a-z]/.test(safe) ? safe : `s_${safe}`;
}

function buildAutoDbName(siteName: string): string {
  const base = sanitizeIdentifier(siteName);
  return base.slice(0, 24);
}

function buildAutoDbUser(siteName: string): string {
  const base = sanitizeIdentifier(siteName);
  const user = `${base.slice(0, 18)}_usr`;
  return user.slice(0, 24);
}

function generatePassword(length = 16): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*";
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  let out = "";
  for (let i = 0; i < length; i += 1) {
    out += chars[bytes[i] % chars.length];
  }
  return out;
}

function CredentialRow({
  label,
  value,
  secret,
  mono,
}: {
  label: string;
  value: string;
  secret?: boolean;
  mono?: boolean;
}) {
  const [visible, setVisible] = useState(!secret);
  const [copied, setCopied] = useState(false);

  async function copyValue() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          readOnly
          value={visible ? value : "••••••••••••"}
          className={cn("h-9 text-sm", mono && "font-mono text-xs")}
        />
        {secret ? (
          <Button type="button" variant="outline" size="sm" onClick={() => setVisible((v) => !v)}>
            {visible ? "Ocultar" : "Mostrar"}
          </Button>
        ) : null}
        <Button type="button" variant="outline" size="icon" className="shrink-0" onClick={copyValue}>
          <Copy className="h-4 w-4" />
        </Button>
      </div>
      {copied ? <p className="text-xs text-emerald-600">Copiado</p> : null}
    </div>
  );
}

export function CreateJoomlaDialog({ open, onOpenChange, onCreated }: CreateJoomlaDialogProps) {
  const [options, setOptions] = useState<JoomlaOptions | null>(null);
  const [phase, setPhase] = useState<Phase>("form");
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<JoomlaProvisionStep[]>([]);
  const [credentials, setCredentials] = useState<JoomlaDeployCredentials | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const siteIdRef = useRef<string | null>(null);

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [adminUser, setAdminUser] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPasswordVisible, setAdminPasswordVisible] = useState(false);
  const [adminEmail, setAdminEmail] = useState("");
  const [dbName, setDbName] = useState("");
  const [dbUser, setDbUser] = useState("");
  const [dbPassword, setDbPassword] = useState("");
  const [dbPasswordVisible, setDbPasswordVisible] = useState(false);
  const [dbNameTouched, setDbNameTouched] = useState(false);
  const [dbUserTouched, setDbUserTouched] = useState(false);
  const [dbPasswordTouched, setDbPasswordTouched] = useState(false);
  const [phpVersion, setPhpVersion] = useState("8.3");
  const [sslEnabled, setSslEnabled] = useState(true);
  const [createFtpAccount, setCreateFtpAccount] = useState(false);

  const MAX_POLL_RETRIES = 300;
  const pollRetriesRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    pollRetriesRef.current = 0;
  }, []);

  const resetDialog = useCallback(() => {
    stopPolling();
    setPhase("form");
    setError(null);
    setSteps([]);
    setCredentials(null);
    siteIdRef.current = null;
  }, [stopPolling]);

  useEffect(() => {
    if (open) {
      joomlaApi.options()
        .then((opts) => {
          setOptions(opts);
          setPhpVersion(opts.php_versions[opts.php_versions.length - 1] || "8.3");
        })
        .catch(() => setOptions(null));
      setAdminPassword(generatePassword(16));
      setDbPassword(generatePassword(18));
      setDbPasswordTouched(false);
      setDbNameTouched(false);
      setDbUserTouched(false);
      setAdminPasswordVisible(false);
      setDbPasswordVisible(false);
    } else {
      resetDialog();
    }
  }, [open, resetDialog]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    if (!name.trim()) {
      if (!dbNameTouched) setDbName("");
      if (!dbUserTouched) setDbUser("");
      return;
    }
    if (!dbNameTouched) setDbName(buildAutoDbName(name));
    if (!dbUserTouched) setDbUser(buildAutoDbUser(name));
  }, [name, dbNameTouched, dbUserTouched]);

  const pollProvision = useCallback(
    (siteId: string) => {
      stopPolling();
      pollRetriesRef.current = 0;
      pollRef.current = setInterval(async () => {
        pollRetriesRef.current += 1;
        if (pollRetriesRef.current > MAX_POLL_RETRIES) {
          stopPolling();
          setError("El despliegue excedió el tiempo máximo de 10 minutos. Es posible que el sitio aún se esté aprovisionando.");
          setPhase("error");
          return;
        }
        try {
          const status = await joomlaApi.provisionStatus(siteId);
          setSteps(status.steps);
          if (status.status === "running" && status.credentials) {
            stopPolling();
            setCredentials({
              ...status.credentials,
            });
            setPhase("success");
            onCreated();
          } else if (status.status === "error") {
            stopPolling();
            setError(status.error_message || "Error en el despliegue de Joomla");
            setPhase("error");
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    },
    [onCreated, stopPolling]
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPhase("deploying");
    setError(null);
    setSteps([{ step: "queued", message: "Preparando despliegue…", at: new Date().toISOString() }]);
    try {
      const site = await joomlaApi.create({
        name,
        domain,
        admin_user: adminUser,
        admin_password: adminPassword,
        admin_email: adminEmail,
        php_version: phpVersion,
        ssl_enabled: sslEnabled,
        create_ftp_account: createFtpAccount,
        db_name: dbName.trim() || undefined,
        db_user: dbUser.trim() || undefined,
        db_password: dbPassword.trim() || undefined,
      });
      siteIdRef.current = site.id;
      try {
        const initial = await joomlaApi.provisionStatus(site.id);
        setSteps(initial.steps.length ? initial.steps : steps);
      } catch {
        /* polling will retry */
      }
      pollProvision(site.id);
    } catch (err) {
      if (err instanceof ApiError) {
        const hint =
          err.status === 500
            ? " Verifique el estado de Docker (docker ps) y ejecute una reparación."
            : "";
        setError(`${err.message}${hint}`);
      } else {
        setError("Error al desplegar Joomla. Verifique la conexión e intente nuevamente.");
      }
      setPhase("error");
    }
  }

  async function copyToClipboard(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    console.info(`${label} copiado`);
  }

  function handleClose() {
    onOpenChange(false);
    if (phase === "success") {
      setName("");
      setDomain("");
      setAdminPassword("");
      setDbName("");
      setDbUser("");
      setDbPassword("");
      setCreateFtpAccount(false);
      setDbNameTouched(false);
      setDbUserTouched(false);
      setDbPasswordTouched(false);
    }
  }

  const loginUrl =
    credentials?.login_url ||
    (sslEnabled ? `https://${domain}/administrator` : `http://${domain}/administrator`);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        {phase === "form" ? (
          <>
            <DialogHeader>
              <DialogTitle>Desplegar Joomla</DialogTitle>
              <DialogDescription>
                Joomla en un clic con Docker, MySQL, Nginx, PHP-FPM y SSL auto-gestionado.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="joomla-name">Nombre del sitio</Label>
                  <Input id="joomla-name" value={name} onChange={(e) => setName(e.target.value)} required />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="joomla-domain">Dominio</Label>
                  <Input
                    id="joomla-domain"
                    placeholder="sitio.example.com"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="joomla-admin">Usuario admin</Label>
                  <Input id="joomla-admin" value={adminUser} onChange={(e) => setAdminUser(e.target.value)} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="joomla-php">Versión de PHP</Label>
                  <Select value={phpVersion} onValueChange={setPhpVersion}>
                    <SelectTrigger id="joomla-php">
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
                  <Label htmlFor="joomla-password">Contraseña admin</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="joomla-password"
                      type={adminPasswordVisible ? "text" : "password"}
                      value={adminPassword}
                      onChange={(e) => setAdminPassword(e.target.value)}
                      minLength={8}
                      required
                    />
                    <Button type="button" variant="outline" size="icon" onClick={() => setAdminPasswordVisible((v) => !v)}>
                      {adminPasswordVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                    <Button type="button" variant="outline" size="icon" onClick={() => setAdminPassword(generatePassword(16))}>
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                    <Button type="button" variant="outline" size="icon" onClick={() => copyToClipboard(adminPassword, "Contraseña admin")}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="joomla-email">Correo admin</Label>
                  <Input
                    id="joomla-email"
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="space-y-3 rounded-lg border p-4">
                <div>
                  <p className="text-sm font-medium">Base de datos MySQL</p>
                  <p className="text-xs text-muted-foreground">
                    Opcional. Letras minúsculas, números y guión bajo. Dejar vacío para autogenerar.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="joomla-db-name">Nombre de BD</Label>
                    <Input
                      id="joomla-db-name"
                      placeholder="mijoomla"
                      value={dbName}
                      onChange={(e) => {
                        setDbNameTouched(true);
                        setDbName(e.target.value.toLowerCase());
                      }}
                      pattern="[a-z][a-z0-9_]*"
                      title="Debe empezar con una letra y usar solo minúsculas, números o _"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="joomla-db-user">Usuario de BD</Label>
                    <Input
                      id="joomla-db-user"
                      placeholder="joomlauser"
                      value={dbUser}
                      onChange={(e) => {
                        setDbUserTouched(true);
                        setDbUser(e.target.value.toLowerCase());
                      }}
                      pattern="[a-z][a-z0-9_]*"
                      title="Debe empezar con una letra y usar solo minúsculas, números o _"
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="joomla-db-password">Contraseña de BD</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="joomla-db-password"
                        type={dbPasswordVisible ? "text" : "password"}
                        placeholder="Autogenerada si se deja vacío"
                        value={dbPassword}
                        onChange={(e) => {
                          setDbPasswordTouched(true);
                          setDbPassword(e.target.value);
                        }}
                        minLength={8}
                      />
                      <Button type="button" variant="outline" size="icon" onClick={() => setDbPasswordVisible((v) => !v)}>
                        {dbPasswordVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => {
                          setDbPasswordTouched(true);
                          setDbPassword(generatePassword(18));
                        }}
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button type="button" variant="outline" size="icon" onClick={() => copyToClipboard(dbPassword, "Contraseña BD")}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <Label>SSL (Let&apos;s Encrypt)</Label>
                  <p className="text-xs text-muted-foreground">Generación automática de certificado HTTPS</p>
                </div>
                <Switch checked={sslEnabled} onCheckedChange={setSslEnabled} />
              </div>

              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <Label>Crear cuenta FTP</Label>
                  <p className="text-xs text-muted-foreground">
                    Crea automáticamente una cuenta FTP para este sitio.
                  </p>
                </div>
                <Switch checked={createFtpAccount} onCheckedChange={setCreateFtpAccount} />
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancelar
                </Button>
                <Button type="submit">
                  Desplegar Joomla
                </Button>
              </DialogFooter>
            </form>
          </>
        ) : null}

        {phase === "deploying" ? (
          <>
            <DialogHeader>
              <DialogTitle>Desplegando Joomla</DialogTitle>
              <DialogDescription>
                Creando base de datos, contenedores e instalando Joomla en <strong>{domain}</strong>
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
              {steps.map((step, index) => (
                <div key={`${step.step}-${index}`} className="flex items-start gap-3 text-sm">
                  {index === steps.length - 1 ? (
                    <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-emerald-600" />
                  ) : (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  )}
                  <p className={cn(index === steps.length - 1 && "font-medium")}>{step.message}</p>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {phase === "success" && credentials ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-emerald-600">
                <CheckCircle2 className="h-5 w-5" />
                Joomla Desplegado
              </DialogTitle>
              <DialogDescription>
                Guarde las credenciales. La contraseña de la BD solo se muestra aquí en el despliegue.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Shield className="h-4 w-4 text-emerald-600" />
                  Acceso administrativo de Joomla
                </div>
                <CredentialRow label="URL de Login" value={loginUrl} mono />
                <CredentialRow label="Usuario admin" value={adminUser} />
                <CredentialRow label="Contraseña admin" value={adminPassword} secret />
                <Button asChild variant="default" className="w-full bg-emerald-600 hover:bg-emerald-600/90">
                  <a href={loginUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Abrir administración de Joomla
                  </a>
                </Button>
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Base de datos MySQL</p>
                <CredentialRow label="Nombre de BD" value={credentials.db_name} mono />
                <CredentialRow label="Usuario de BD" value={credentials.db_user} mono />
                <CredentialRow label="Contraseña de BD" value={credentials.db_password} secret mono />
                {credentials.db_host ? (
                  <CredentialRow label="Host de BD" value={credentials.db_host} mono />
                ) : null}
              </div>

              {(credentials.ftp_username || credentials.ftp_password || credentials.ftp_home) && (
                <div className="rounded-lg border p-4 space-y-3">
                  <p className="text-sm font-medium">Acceso FTP</p>
                  {credentials.ftp_username ? <CredentialRow label="Usuario FTP" value={credentials.ftp_username} mono /> : null}
                  {credentials.ftp_password ? <CredentialRow label="Contraseña FTP" value={credentials.ftp_password} secret mono /> : null}
                  {credentials.ftp_home ? <CredentialRow label="Directorio FTP" value={credentials.ftp_home} mono /> : null}
                </div>
              )}
            </div>

            <DialogFooter>
              <Button onClick={handleClose}>Listo</Button>
            </DialogFooter>
          </>
        ) : null}

        {phase === "error" ? (
          <>
            <DialogHeader>
              <DialogTitle>Error en el despliegue</DialogTitle>
              <DialogDescription>El sitio Joomla no pudo ser desplegado.</DialogDescription>
            </DialogHeader>

            {steps.length > 0 ? (
              <div className="space-y-2 rounded-lg border bg-muted/20 p-4 text-sm">
                {steps.map((step, index) => (
                  <p key={`${step.step}-${index}`}>{step.message}</p>
                ))}
              </div>
            ) : null}

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Cerrar
              </Button>
              <Button onClick={() => setPhase("form")}>Intentar de nuevo</Button>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
