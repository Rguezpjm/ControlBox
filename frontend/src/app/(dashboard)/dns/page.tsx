"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { Plus, Search, Download, Upload, Key, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableSkeleton } from "@/components/skeletons";
import { dnsApi, type DnsZone, type DnsRecord } from "@/lib/dns";
import { ApiError } from "@/lib/api-client";

const typeColors: Record<string, string> = {
  A: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  AAAA: "bg-indigo-500/15 text-indigo-600",
  CNAME: "bg-purple-500/15 text-purple-600",
  MX: "bg-amber-500/15 text-amber-600",
  TXT: "bg-gray-500/15 text-gray-600",
  NS: "bg-emerald-500/15 text-emerald-600",
  SRV: "bg-rose-500/15 text-rose-600",
  CAA: "bg-cyan-500/15 text-cyan-600",
};

function DnsContent() {
  const [zones, setZones] = useState<DnsZone[]>([]);
  const [records, setRecords] = useState<DnsRecord[]>([]);
  const [recordTypes, setRecordTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeZone, setActiveZone] = useState<string>("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [createZoneOpen, setCreateZoneOpen] = useState(false);
  const [newZoneName, setNewZoneName] = useState("");
  const [recordDialogOpen, setRecordDialogOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importContent, setImportContent] = useState("");
  const [apiKeyOpen, setApiKeyOpen] = useState(false);
  const [newApiKeyName, setNewApiKeyName] = useState("");
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null);

  const [recName, setRecName] = useState("@");
  const [recType, setRecType] = useState("A");
  const [recContent, setRecContent] = useState("");
  const [recTtl, setRecTtl] = useState("3600");
  const [recPriority, setRecPriority] = useState("10");

  const loadZones = useCallback(async () => {
    setLoading(true);
    try {
      const [zonesData, typesData] = await Promise.all([
        dnsApi.listZones(),
        dnsApi.recordTypes(),
      ]);
      setZones(zonesData);
      setRecordTypes(typesData.types);
      if (zonesData.length > 0 && !activeZone) {
        setActiveZone(zonesData[0].id);
      }
    } catch {
      setZones([]);
    } finally {
      setLoading(false);
    }
  }, [activeZone]);

  const loadRecords = useCallback(async (zoneId: string) => {
    if (!zoneId) return;
    try {
      const data = await dnsApi.listRecords(zoneId);
      setRecords(data);
    } catch {
      setRecords([]);
    }
  }, []);

  useEffect(() => {
    loadZones();
  }, [loadZones]);

  useEffect(() => {
    if (activeZone) loadRecords(activeZone);
  }, [activeZone, loadRecords]);

  const currentZone = zones.find((z) => z.id === activeZone);
  const filtered = records.filter(
    (r) =>
      r.name.includes(search) ||
      r.content.includes(search) ||
      r.record_type.includes(search.toUpperCase())
  );

  async function handleCreateZone(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const zone = await dnsApi.createZone(newZoneName);
      setCreateZoneOpen(false);
      setNewZoneName("");
      await loadZones();
      setActiveZone(zone.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create zone");
    }
  }

  async function handleCreateRecord(e: React.FormEvent) {
    e.preventDefault();
    if (!activeZone) return;
    setError(null);
    try {
      await dnsApi.createRecord(activeZone, {
        name: recName,
        record_type: recType,
        content: recContent,
        ttl: parseInt(recTtl, 10) || 3600,
        priority: recType === "MX" || recType === "SRV" ? parseInt(recPriority, 10) : undefined,
      });
      setRecordDialogOpen(false);
      setRecName("@");
      setRecContent("");
      await loadRecords(activeZone);
      await loadZones();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create record");
    }
  }

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    if (!activeZone) return;
    try {
      await dnsApi.importZone(activeZone, importContent);
      setImportOpen(false);
      setImportContent("");
      await loadRecords(activeZone);
      await loadZones();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed");
    }
  }

  async function handleExport() {
    if (!activeZone) return;
    try {
      const content = await dnsApi.exportZone(activeZone);
      const blob = new Blob([content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${currentZone?.name || "zone"}.zone`;
      a.click();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    }
  }

  async function handleDeleteRecord(record: DnsRecord) {
    if (!activeZone || !confirm("Delete this record?")) return;
    const shortName = record.name.replace(`.${currentZone?.name}`, "").replace(currentZone?.name || "", "@");
    await dnsApi.deleteRecord(activeZone, shortName === "" ? "@" : shortName, record.record_type);
    await loadRecords(activeZone);
    await loadZones();
  }

  async function handleCreateApiKey(e: React.FormEvent) {
    e.preventDefault();
    try {
      const result = await dnsApi.createApiKey(newApiKeyName);
      setCreatedApiKey(result.api_key);
      setNewApiKeyName("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create API key");
    }
  }

  if (loading) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="DNS Manager"
        description="Manage DNS zones and records via PowerDNS"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setApiKeyOpen(true)}>
              <Key className="h-4 w-4" />
              API Keys
            </Button>
            <Button onClick={() => setCreateZoneOpen(true)}>
              <Plus className="h-4 w-4" />
              Create Zone
            </Button>
          </div>
        }
      />

      {error && <p className="text-sm text-destructive">{error}</p>}

      {zones.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-12">
          No DNS zones yet. Create a zone to start managing records.
        </p>
      ) : (
        <Tabs value={activeZone} onValueChange={setActiveZone}>
          <TabsList className="flex-wrap h-auto">
            {zones.map((zone) => (
              <TabsTrigger key={zone.id} value={zone.id}>
                {zone.name}
              </TabsTrigger>
            ))}
          </TabsList>

          {zones.map((zone) => (
            <TabsContent key={zone.id} value={zone.id} className="space-y-4">
              <div className="flex flex-wrap gap-2 items-center justify-between">
                <div className="relative max-w-sm flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Filter records..."
                    className="pl-9"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
                    <Upload className="h-4 w-4" /> Import
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleExport}>
                    <Download className="h-4 w-4" /> Export
                  </Button>
                  <Button size="sm" onClick={() => setRecordDialogOpen(true)}>
                    <Plus className="h-4 w-4" /> Add Record
                  </Button>
                </div>
              </div>

              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="px-4 py-3 text-left font-medium text-muted-foreground w-16">Type</th>
                          <th className="px-4 py-3 text-left font-medium text-muted-foreground">Name</th>
                          <th className="px-4 py-3 text-left font-medium text-muted-foreground">Value</th>
                          <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden sm:table-cell">TTL</th>
                          <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((record) => {
                          const shortName = record.name.replace(`.${zone.name}`, "");
                          return (
                            <tr key={record.id} className="border-b last:border-0 hover:bg-muted/30 font-mono text-xs">
                              <td className="px-4 py-3">
                                <Badge className={typeColors[record.record_type] || ""} variant="outline">
                                  {record.record_type}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 font-medium">
                                {shortName === zone.name ? "@" : shortName}
                              </td>
                              <td className="px-4 py-3 text-muted-foreground max-w-xs truncate">
                                {record.priority != null ? `${record.priority} ` : ""}{record.content}
                              </td>
                              <td className="px-4 py-3 hidden sm:table-cell text-muted-foreground">{record.ttl}s</td>
                              <td className="px-4 py-3 text-right">
                                <Button variant="ghost" size="sm" onClick={() => handleDeleteRecord(record)}>
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      )}

      <Dialog open={createZoneOpen} onOpenChange={setCreateZoneOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Create DNS Zone</DialogTitle></DialogHeader>
          <form onSubmit={handleCreateZone} className="space-y-4">
            <div className="space-y-2">
              <Label>Zone name</Label>
              <Input placeholder="example.com" value={newZoneName} onChange={(e) => setNewZoneName(e.target.value)} required />
            </div>
            <DialogFooter>
              <Button type="submit">Create</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={recordDialogOpen} onOpenChange={setRecordDialogOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add DNS Record</DialogTitle></DialogHeader>
          <form onSubmit={handleCreateRecord} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={recName} onChange={(e) => setRecName(e.target.value)} placeholder="@ or www" />
              </div>
              <div className="space-y-2">
                <Label>Type</Label>
                <Select value={recType} onValueChange={setRecType}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {recordTypes.map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Content</Label>
              <Input value={recContent} onChange={(e) => setRecContent(e.target.value)} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>TTL</Label>
                <Input type="number" value={recTtl} onChange={(e) => setRecTtl(e.target.value)} />
              </div>
              {(recType === "MX" || recType === "SRV") && (
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Input type="number" value={recPriority} onChange={(e) => setRecPriority(e.target.value)} />
                </div>
              )}
            </div>
            <DialogFooter><Button type="submit">Add Record</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle>Import Zone File</DialogTitle></DialogHeader>
          <form onSubmit={handleImport} className="space-y-4">
            <textarea
              className="w-full h-48 rounded-md border bg-background p-3 font-mono text-xs"
              placeholder="$ORIGIN example.com.&#10;@ IN A 192.0.2.1"
              value={importContent}
              onChange={(e) => setImportContent(e.target.value)}
              required
            />
            <DialogFooter><Button type="submit">Import</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={apiKeyOpen} onOpenChange={(o) => { setApiKeyOpen(o); if (!o) setCreatedApiKey(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Integration API Keys</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Public API: <code className="text-xs">/api/v1/integrations/dns</code> with header <code className="text-xs">X-API-Key</code>
          </p>
          {createdApiKey && (
            <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-xs font-mono break-all">
              {createdApiKey}
            </div>
          )}
          <form onSubmit={handleCreateApiKey} className="flex gap-2">
            <Input placeholder="Key name" value={newApiKeyName} onChange={(e) => setNewApiKeyName(e.target.value)} required />
            <Button type="submit">Create</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function DnsPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <DnsContent />
    </Suspense>
  );
}
