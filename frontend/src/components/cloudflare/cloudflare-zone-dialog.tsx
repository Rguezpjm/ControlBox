"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { cloudflareApi, type CloudflareDnsRecord, type CloudflareZone } from "@/lib/cloudflare";

interface CloudflareZoneDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  zone: CloudflareZone | null;
  onUpdated: () => void;
}

export function CloudflareZoneDialog({ open, onOpenChange, zone, onUpdated }: CloudflareZoneDialogProps) {
  const [records, setRecords] = useState<CloudflareDnsRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [zoneState, setZoneState] = useState<CloudflareZone | null>(zone);

  const [newType, setNewType] = useState("A");
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newProxied, setNewProxied] = useState(true);

  const loadRecords = useCallback(async () => {
    if (!zone) return;
    setLoading(true);
    try {
      const list = await cloudflareApi.listDnsRecords(zone.id);
      setRecords(list);
    } catch {
      toast.error("No se pudieron cargar los registros DNS");
    } finally {
      setLoading(false);
    }
  }, [zone]);

  useEffect(() => {
    setZoneState(zone);
    if (open && zone) void loadRecords();
  }, [open, zone, loadRecords]);

  async function patchZone(data: { paused?: boolean; under_attack?: boolean }) {
    if (!zoneState) return;
    setBusy("zone");
    try {
      const updated = await cloudflareApi.updateZone(zoneState.id, data);
      setZoneState(updated);
      onUpdated();
      toast.success("Zona actualizada");
    } catch {
      toast.error("Error al actualizar la zona");
    } finally {
      setBusy(null);
    }
  }

  async function handleAddRecord() {
    if (!zoneState || !newName.trim() || !newContent.trim()) return;
    setBusy("add");
    try {
      await cloudflareApi.createDnsRecord(zoneState.id, {
        type: newType,
        name: newName.trim(),
        content: newContent.trim(),
        proxied: newProxied,
      });
      setNewName("");
      setNewContent("");
      await loadRecords();
      toast.success("Registro DNS creado");
    } catch {
      toast.error("No se pudo crear el registro");
    } finally {
      setBusy(null);
    }
  }

  async function handleDeleteRecord(recordId: string) {
    if (!zoneState || !window.confirm("¿Eliminar este registro DNS?")) return;
    setBusy(recordId);
    try {
      await cloudflareApi.deleteDnsRecord(zoneState.id, recordId);
      await loadRecords();
      toast.success("Registro eliminado");
    } catch {
      toast.error("No se pudo eliminar el registro");
    } finally {
      setBusy(null);
    }
  }

  if (!zoneState) return null;

  const underAttack = zoneState.security_level === "under_attack";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {zoneState.name}
            <Badge variant="outline">Cloudflare</Badge>
          </DialogTitle>
          <DialogDescription>
            Estado: {zoneState.status}
            {zoneState.paused ? " · Pausado" : ""}
            {underAttack ? " · Under Attack" : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={zoneState.paused ? "default" : "outline"}
            disabled={busy !== null}
            onClick={() => void patchZone({ paused: !zoneState.paused })}
          >
            {zoneState.paused ? "Reanudar zona" : "Pausar zona"}
          </Button>
          <Button
            size="sm"
            variant={underAttack ? "destructive" : "outline"}
            disabled={busy !== null}
            onClick={() => void patchZone({ under_attack: !underAttack })}
          >
            <ShieldAlert className="mr-1.5 h-3.5 w-3.5" />
            {underAttack ? "Quitar Under Attack" : "Under Attack"}
          </Button>
        </div>

        <div className="space-y-3 rounded-lg border p-4">
          <h4 className="text-sm font-medium">Nuevo registro DNS</h4>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>Tipo</Label>
              <Input value={newType} onChange={(e) => setNewType(e.target.value.toUpperCase())} />
            </div>
            <div>
              <Label>Nombre</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="@ o www" />
            </div>
            <div className="sm:col-span-2">
              <Label>Contenido</Label>
              <Input value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="IP o destino" />
            </div>
            <div className="flex items-center gap-2 sm:col-span-2">
              <Switch checked={newProxied} onCheckedChange={setNewProxied} />
              <Label>Proxy Cloudflare (naranja)</Label>
            </div>
          </div>
          <Button size="sm" onClick={() => void handleAddRecord()} disabled={busy === "add"}>
            {busy === "add" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
            Agregar registro
          </Button>
        </div>

        <div className="space-y-2">
          <h4 className="text-sm font-medium">Registros DNS</h4>
          {loading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Cargando...
            </div>
          ) : records.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">Sin registros DNS en esta zona.</p>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-3 py-2 text-left">Tipo</th>
                    <th className="px-3 py-2 text-left">Nombre</th>
                    <th className="px-3 py-2 text-left">Contenido</th>
                    <th className="px-3 py-2 text-left">Proxy</th>
                    <th className="px-3 py-2 text-right">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr key={record.id} className="border-b last:border-0">
                      <td className="px-3 py-2 font-medium">{record.type}</td>
                      <td className="px-3 py-2">{record.name}</td>
                      <td className="px-3 py-2 max-w-[200px] truncate">{record.content}</td>
                      <td className="px-3 py-2">{record.proxied ? "Sí" : "No"}</td>
                      <td className="px-3 py-2 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          disabled={busy === record.id}
                          onClick={() => void handleDeleteRecord(record.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
