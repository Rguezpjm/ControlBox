"use client";

import { useEffect, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge } from "@/components/shared/status-badge";
import { ftpApi, type FtpServiceStatus } from "@/lib/ftp";
import { ApiError } from "@/lib/api-client";
import { toast } from "sonner";
import type { ResourceStatus } from "@/types";

function mapStatus(status: FtpServiceStatus): ResourceStatus {
  if (!status.enabled) return "stopped";
  if (status.running) return "running";
  return status.status === "error" ? "error" : "stopped";
}

interface FtpServiceSettingsProps {
  serviceStatus: FtpServiceStatus | null;
  onUpdated: () => void;
}

export function FtpServiceSettings({ serviceStatus, onUpdated }: FtpServiceSettingsProps) {
  const [enabled, setEnabled] = useState(false);
  const [protocol, setProtocol] = useState<"ftp" | "ftps" | "sftp">("ftp");
  const [port, setPort] = useState("21");
  const [passiveMin, setPassiveMin] = useState("30000");
  const [passiveMax, setPassiveMax] = useState("30009");
  const [publicHost, setPublicHost] = useState("");
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (!serviceStatus) return;
    setEnabled(serviceStatus.enabled);
    setProtocol(serviceStatus.protocol as "ftp" | "ftps" | "sftp");
    setPort(String(serviceStatus.port ?? (serviceStatus.protocol === "sftp" ? 22 : 21)));
    setPassiveMin(String(serviceStatus.passive_port_min));
    setPassiveMax(String(serviceStatus.passive_port_max));
    setPublicHost(serviceStatus.public_host || "");
  }, [serviceStatus]);

  async function handleSave() {
    setSaving(true);
    try {
      const result = await ftpApi.configureService({
        enabled,
        protocol,
        port: parseInt(port, 10) || 21,
        passive_port_min: parseInt(passiveMin, 10) || 30000,
        passive_port_max: parseInt(passiveMax, 10) || 30009,
        public_host: publicHost,
      });
      toast[result.success ? "success" : "error"](result.message);
      if (result.success) onUpdated();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar la configuración FTP");
    } finally {
      setSaving(false);
    }
  }

  async function handleStartStop(start: boolean) {
    setToggling(true);
    try {
      const result = start ? await ftpApi.startService() : await ftpApi.stopService();
      toast[result.success ? "success" : "error"](result.message);
      if (result.success) onUpdated();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cambiar el estado del servicio");
    } finally {
      setToggling(false);
    }
  }

  if (!serviceStatus) return null;

  const canManage = serviceStatus.can_manage;
  const showPassive = protocol === "ftp" || protocol === "ftps";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base">Servicio FTP</CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Protocolo, puerto y estado global del servicio
          </p>
        </div>
        <StatusBadge status={mapStatus(serviceStatus)} />
      </CardHeader>
      <CardContent className="space-y-4">
        {serviceStatus.message && (
          <p className="text-sm text-muted-foreground rounded-lg border bg-muted/30 p-3">
            {serviceStatus.message}
          </p>
        )}

        <div className="flex items-center justify-between gap-4">
          <div>
            <Label htmlFor="ftp-enabled">Habilitar servicio</Label>
            <p className="text-xs text-muted-foreground">Activa FTP/FTPS/SFTP en este servidor</p>
          </div>
          <Switch
            id="ftp-enabled"
            checked={enabled}
            onCheckedChange={setEnabled}
            disabled={!canManage || saving}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Protocolo</Label>
            <Select
              value={protocol}
              onValueChange={(v) => {
                const next = v as "ftp" | "ftps" | "sftp";
                setProtocol(next);
                if (next === "sftp" && port === "21") setPort("22");
                if (next !== "sftp" && port === "22") setPort("21");
              }}
              disabled={!canManage || saving}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ftp">FTP (puerto 21)</SelectItem>
                <SelectItem value="ftps">FTPS (FTP + TLS)</SelectItem>
                <SelectItem value="sftp">SFTP (SSH)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="ftp-port">Puerto</Label>
            <Input
              id="ftp-port"
              type="number"
              min={1}
              max={65535}
              value={port}
              onChange={(e) => setPort(e.target.value)}
              disabled={!canManage || saving}
            />
          </div>
        </div>

        {showPassive && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="passive-min">Puerto pasivo (inicio)</Label>
              <Input
                id="passive-min"
                type="number"
                value={passiveMin}
                onChange={(e) => setPassiveMin(e.target.value)}
                disabled={!canManage || saving}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="passive-max">Puerto pasivo (fin)</Label>
              <Input
                id="passive-max"
                type="number"
                value={passiveMax}
                onChange={(e) => setPassiveMax(e.target.value)}
                disabled={!canManage || saving}
              />
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="public-host">Host público (PASV / cliente)</Label>
          <Input
            id="public-host"
            placeholder="ftp.tudominio.com o IP del servidor"
            value={publicHost}
            onChange={(e) => setPublicHost(e.target.value)}
            disabled={!canManage || saving}
          />
        </div>

        {canManage ? (
          <div className="flex flex-wrap gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving || toggling}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Guardar configuración
            </Button>
            {enabled && !serviceStatus.running && (
              <Button variant="secondary" onClick={() => handleStartStop(true)} disabled={toggling || saving}>
                {toggling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Iniciar
              </Button>
            )}
            {serviceStatus.running && (
              <Button variant="outline" onClick={() => handleStartStop(false)} disabled={toggling || saving}>
                {toggling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
                Detener
              </Button>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            La gestión del servicio requiere instalación en VPS con acceso Docker.
          </p>
        )}

        {protocol === "sftp" && (
          <p className="text-xs text-muted-foreground">
            SFTP: tras cambiar a este modo, reinicie la contraseña de cada cuenta para sincronizar el acceso SSH.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
