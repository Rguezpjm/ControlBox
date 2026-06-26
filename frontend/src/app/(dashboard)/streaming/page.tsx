"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Tv,
  Plus,
  Trash2,
  Play,
  Users,
  Activity,
  FileText,
  Copy,
  Check,
  RefreshCw,
  Search,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  streamingApi,
  type StreamingSource,
  type StreamingCategory,
  type StreamingChannel,
  type StreamingClient,
  type ImportChannelItem,
  type ActiveConnection,
  type StreamingStats,
} from "@/lib/streaming";

export default function StreamingPage() {
  const [stats, setStats] = useState<StreamingStats>({
    connected_users: 0,
    bandwidth_mbps: 0,
    active_streams: 0,
    total_channels: 0,
  });
  const [sources, setSources] = useState<StreamingSource[]>([]);
  const [channels, setChannels] = useState<StreamingChannel[]>([]);
  const [categories, setCategories] = useState<StreamingCategory[]>([]);
  const [clients, setClients] = useState<StreamingClient[]>([]);
  const [connections, setConnections] = useState<ActiveConnection[]>([]);
  
  // Create forms state
  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceType, setNewSourceType] = useState("m3u");
  const [newSourceUrl, setNewSourceUrl] = useState("");
  const [newSourceUser, setNewSourceUser] = useState("");
  const [newSourcePass, setNewSourcePass] = useState("");

  const [newClientUser, setNewClientUser] = useState("");
  const [newClientPass, setNewClientPass] = useState("");
  const [newClientMaxConn, setNewClientMaxConn] = useState(1);
  const [newClientExpires, setNewClientExpires] = useState("");

  const [epgUrl, setEpgUrl] = useState("");

  // Catalog items for the active source
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ImportChannelItem[]>([]);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [selectedCatalogItems, setSelectedCatalogItems] = useState<number[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const [copiedClientId, setCopiedClientId] = useState<string | null>(null);

  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importTotal, setImportTotal] = useState(0);

  useEffect(() => {
    setCurrentPage(1);
  }, [catalogSearch, selectedSourceId]);

  const loadData = useCallback(async () => {
    try {
      const [s, sourcesData, channelsData, categoriesData, clientsData, connsData] =
        await Promise.all([
          streamingApi.getStats(),
          streamingApi.listSources(),
          streamingApi.listChannels(),
          streamingApi.listCategories(),
          streamingApi.listClients(),
          streamingApi.listActiveConnections(),
        ]);
      setStats(s);
      setSources(sourcesData);
      setChannels(channelsData);
      setCategories(categoriesData);
      setClients(clientsData);
      setConnections(connsData);
    } catch {
      toast.error("Error al cargar datos del servidor de streaming");
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  async function handleCreateSource(e: React.FormEvent) {
    e.preventDefault();
    try {
      await streamingApi.createSource({
        name: newSourceName,
        type: newSourceType,
        url: newSourceUrl,
        username: newSourceUser || undefined,
        password: newSourcePass || undefined,
      });
      toast.success("Fuente de streaming creada con éxito");
      setNewSourceName("");
      setNewSourceUrl("");
      setNewSourceUser("");
      setNewSourcePass("");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Error al crear la fuente");
    }
  }

  async function handleDeleteSource(id: string) {
    try {
      await streamingApi.deleteSource(id);
      toast.success("Fuente eliminada");
      if (selectedSourceId === id) {
        setCatalog([]);
        setSelectedCatalogItems([]);
      }
      loadData();
    } catch {
      toast.error("Error al eliminar la fuente");
    }
  }

  async function handleLoadCatalog(sourceId: string) {
    setCatalogLoading(true);
    setSelectedSourceId(sourceId);
    setSelectedCatalogItems([]);
    try {
      const items = await streamingApi.getCatalog(sourceId);
      setCatalog(items);
      toast.success(`Se encontraron ${items.length} canales en la fuente`);
    } catch (err: any) {
      toast.error(err.message || "Error al obtener la lista de canales");
      setCatalog([]);
    } finally {
      setCatalogLoading(false);
    }
  }

  async function handleImportChannels() {
    if (!selectedSourceId || selectedCatalogItems.length === 0) return;
    const itemsToImport = selectedCatalogItems.map((index) => catalog[index]);
    
    setImporting(true);
    setImportProgress(0);
    setImportTotal(itemsToImport.length);
    
    const chunkSize = 300;
    let importedTotalCount = 0;
    
    try {
      for (let i = 0; i < itemsToImport.length; i += chunkSize) {
        const chunk = itemsToImport.slice(i, i + chunkSize);
        const res = await streamingApi.importChannels(selectedSourceId, chunk);
        importedTotalCount += res.imported;
        setImportProgress(Math.min(i + chunkSize, itemsToImport.length));
      }
      toast.success(`Se importaron/actualizaron ${importedTotalCount} canales con éxito`);
      setSelectedCatalogItems([]);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Error al importar los canales");
    } finally {
      setImporting(false);
      setImportProgress(0);
      setImportTotal(0);
    }
  }

  async function handleCreateClient(e: React.FormEvent) {
    e.preventDefault();
    try {
      await streamingApi.createClient({
        username: newClientUser,
        password: newClientPass,
        max_connections: newClientMaxConn,
        is_active: true,
        expires_at: newClientExpires ? new Date(newClientExpires).toISOString() : null,
        allowed_categories: [],
      });
      toast.success("Cliente autorizado con éxito");
      setNewClientUser("");
      setNewClientPass("");
      setNewClientMaxConn(1);
      setNewClientExpires("");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Error al crear el cliente");
    }
  }

  async function handleDeleteClient(id: string) {
    try {
      await streamingApi.deleteClient(id);
      toast.success("Cliente eliminado");
      loadData();
    } catch {
      toast.error("Error al eliminar el cliente");
    }
  }

  async function handleSyncEpg(e: React.FormEvent) {
    e.preventDefault();
    try {
      await streamingApi.syncEpg(epgUrl);
      toast.success("Sincronización de guía de EPG iniciada en segundo plano");
      setEpgUrl("");
    } catch {
      toast.error("Error al iniciar sincronización de EPG");
    }
  }

  async function copyToClipboard(text: string, id: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedClientId(id);
      toast.success("Copiado al portapapeles");
      setTimeout(() => setCopiedClientId(null), 2000);
    } catch {
      toast.error("No se pudo copiar");
    }
  }

  const filteredCatalog = catalog
    .map((item, originalIndex) => ({ ...item, originalIndex }))
    .filter((item) => {
      const q = catalogSearch.toLowerCase();
      return (
        item.name.toLowerCase().includes(q) ||
        item.category_name.toLowerCase().includes(q)
      );
    });

  const itemsPerPage = 100;
  const totalPages = Math.ceil(filteredCatalog.length / itemsPerPage);
  const paginatedCatalog = filteredCatalog.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const currentHost = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Streaming & IPTV Manager"
        description="Gestione canales de video en vivo, ingesta FFmpeg, control de clientes y estadísticas en tiempo real."
      />

      {/* Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="bg-gradient-to-br from-blue-500/10 to-indigo-500/5 border-blue-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Clientes Conectados</CardTitle>
            <Users className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.connected_users}</div>
            <p className="text-xs text-muted-foreground">Sesiones activas de visualización</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-purple-500/10 to-pink-500/5 border-purple-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Ancho de Banda</CardTitle>
            <Activity className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.bandwidth_mbps.toFixed(1)} Mbps</div>
            <p className="text-xs text-muted-foreground">Consumo de red en tiempo real</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border-emerald-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Procesos de Ingesta</CardTitle>
            <RefreshCw className="h-4 w-4 text-emerald-500 animate-spin-slow" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.active_streams}</div>
            <p className="text-xs text-muted-foreground">Hilos FFmpeg remuxing activos</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-amber-500/10 to-orange-500/5 border-amber-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Canales Habilitados</CardTitle>
            <Tv className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_channels}</div>
            <p className="text-xs text-muted-foreground">Guía activa en catálogo local</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="sources" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-5 h-auto gap-1">
          <TabsTrigger value="sources">Fuentes & Catálogo</TabsTrigger>
          <TabsTrigger value="channels">Canales Activos</TabsTrigger>
          <TabsTrigger value="clients">Clientes & Accesos</TabsTrigger>
          <TabsTrigger value="connections">Conexiones en Vivo</TabsTrigger>
          <TabsTrigger value="epg">EPG Guía local</TabsTrigger>
        </TabsList>

        {/* 1. SOURCES & CATALOG */}
        <TabsContent value="sources" className="space-y-4">
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Agregar Lista de Ingesta</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreateSource} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="source-name">Nombre descriptivo</Label>
                    <Input
                      id="source-name"
                      placeholder="DalePlay TV"
                      value={newSourceName}
                      onChange={(e) => setNewSourceName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="source-type">Tipo de Fuente</Label>
                    <select
                      id="source-type"
                      value={newSourceType}
                      onChange={(e) => setNewSourceType(e.target.value)}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      <option value="m3u">Lista M3U / M3U8 URL</option>
                      <option value="xtream">Xcode Streaming API (Xtream)</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="source-url">URL / Host</Label>
                    <Input
                      id="source-url"
                      placeholder="http://host.vip/get.php?..."
                      value={newSourceUrl}
                      onChange={(e) => setNewSourceUrl(e.target.value)}
                      required
                    />
                  </div>
                  {newSourceType === "xtream" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-2">
                        <Label htmlFor="source-user">Username</Label>
                        <Input
                          id="source-user"
                          value={newSourceUser}
                          onChange={(e) => setNewSourceUser(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="source-pass">Password</Label>
                        <Input
                          id="source-pass"
                          type="password"
                          value={newSourcePass}
                          onChange={(e) => setNewSourcePass(e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                  <Button type="submit" className="w-full">
                    <Plus className="mr-2 h-4 w-4" />
                    Registrar Lista
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Listas M3U & Xcode Conectadas</CardTitle>
              </CardHeader>
              <CardContent>
                {sources.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">No hay fuentes registradas.</p>
                ) : (
                  <div className="space-y-3">
                    {sources.map((s) => (
                      <div
                        key={s.id}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-lg border bg-muted/20"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold">{s.name}</span>
                            <Badge variant="outline" className="text-[10px]">
                              {s.type.toUpperCase()}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground truncate font-mono mt-1">{s.url}</p>
                          <p className="text-[10px] text-muted-foreground/60 mt-1">
                            Sincronizado: {s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Nunca"}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2 shrink-0">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleLoadCatalog(s.id)}
                            disabled={catalogLoading && selectedSourceId === s.id}
                          >
                            {catalogLoading && selectedSourceId === s.id ? (
                              <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Play className="mr-1.5 h-3.5 w-3.5 text-blue-500" />
                            )}
                            Catalogar canales
                          </Button>
                          <Button asChild variant="outline" size="sm">
                            <a
                              href={`${currentHost}/api/v1/streaming/sources/${s.id}/catalog?download_txt=true`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <FileText className="mr-1.5 h-3.5 w-3.5" />
                              Descargar .txt
                            </a>
                          </Button>
                          <Button variant="destructive" size="sm" onClick={() => handleDeleteSource(s.id)}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Catalog grid */}
          {selectedSourceId && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Catalogador de Canales</CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Seleccione los canales que desea importar a su plataforma ControlBox.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => {
                      if (selectedCatalogItems.length === filteredCatalog.length) {
                        setSelectedCatalogItems([]);
                      } else {
                        setSelectedCatalogItems(filteredCatalog.map((item) => item.originalIndex));
                      }
                    }}
                    variant="outline"
                    size="sm"
                  >
                    Marcar todos
                  </Button>
                  <Button
                    onClick={handleImportChannels}
                    disabled={selectedCatalogItems.length === 0 || importing}
                    className="bg-emerald-600 hover:bg-emerald-600/90"
                    size="sm"
                  >
                    {importing ? (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Importando ({importProgress}/{importTotal})
                      </>
                    ) : (
                      `Importar Seleccionados (${selectedCatalogItems.length})`
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative max-w-sm">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Filtrar por nombre o grupo..."
                    value={catalogSearch}
                    onChange={(e) => setCatalogSearch(e.target.value)}
                    className="pl-9"
                  />
                </div>

                {catalogLoading ? (
                  <div className="flex justify-center py-12">
                    <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                ) : filteredCatalog.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">Ningún canal disponible.</p>
                ) : (
                  <>
                    <div className="max-h-[50vh] overflow-y-auto border rounded-lg">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-background border-b z-10">
                          <tr className="bg-muted/40">
                            <th className="w-12 px-4 py-2" />
                            <th className="px-4 py-2 text-left font-medium">Logotipo</th>
                            <th className="px-4 py-2 text-left font-medium">Nombre de Canal</th>
                            <th className="px-4 py-2 text-left font-medium">Categoría Original</th>
                            <th className="px-4 py-2 text-left font-medium">EPG ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {paginatedCatalog.map((item) => {
                            const isSelected = selectedCatalogItems.includes(item.originalIndex);
                            return (
                              <tr key={item.originalIndex} className="border-b last:border-0 hover:bg-muted/20">
                                <td className="px-4 py-2 text-center">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      setSelectedCatalogItems((prev) =>
                                        e.target.checked
                                          ? [...prev, item.originalIndex]
                                          : prev.filter((x) => x !== item.originalIndex)
                                      );
                                    }}
                                  />
                                </td>
                                <td className="px-4 py-2">
                                  {item.logo_url ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                      src={item.logo_url}
                                      alt={item.name}
                                      className="h-7 w-auto max-w-[50px] object-contain rounded"
                                      onError={(e) => {
                                        (e.target as HTMLElement).style.display = "none";
                                      }}
                                    />
                                  ) : (
                                    <span className="text-xs text-muted-foreground">—</span>
                                  )}
                                </td>
                                <td className="px-4 py-2 font-medium">{item.name}</td>
                                <td className="px-4 py-2 text-muted-foreground">{item.category_name}</td>
                                <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                                  {item.epg_id || "N/A"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {totalPages > 1 && (
                      <div className="flex items-center justify-between pt-2">
                        <p className="text-xs text-muted-foreground">
                          Mostrando {Math.min(filteredCatalog.length, (currentPage - 1) * itemsPerPage + 1)}-
                          {Math.min(filteredCatalog.length, currentPage * itemsPerPage)} de {filteredCatalog.length} canales
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={currentPage === 1}
                            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                          >
                            Anterior
                          </Button>
                          <span className="text-xs flex items-center px-2">
                            Página {currentPage} de {totalPages}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={currentPage === totalPages}
                            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                          >
                            Siguiente
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* 2. ACTIVE CHANNELS */}
        <TabsContent value="channels" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Canales Habilitados en Catálogo</CardTitle>
            </CardHeader>
            <CardContent>
              {channels.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-12">No hay canales importados aún.</p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                  {channels.map((chan) => (
                    <div
                      key={chan.id}
                      className="flex items-center gap-3 p-3 border rounded-lg hover:shadow-sm bg-muted/5 transition-all"
                    >
                      <div className="h-10 w-10 shrink-0 border rounded bg-background flex items-center justify-center overflow-hidden">
                        {chan.logo_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={chan.logo_url} alt={chan.name} className="h-8 w-auto max-w-full object-contain" />
                        ) : (
                          <Tv className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold truncate">{chan.name}</p>
                        <div className="flex items-center gap-1.5 mt-1">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              chan.status === "online"
                                ? "bg-emerald-500"
                                : chan.status === "offline"
                                ? "bg-rose-500"
                                : "bg-zinc-400"
                            }`}
                          />
                          <span className="text-[10px] text-muted-foreground uppercase">{chan.status}</span>
                        </div>
                      </div>
                      <Badge variant={chan.is_active ? "default" : "secondary"} className="text-[9px]">
                        {chan.is_active ? "Activo" : "Inactivo"}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 3. CLIENTS MANAGER */}
        <TabsContent value="clients" className="space-y-4">
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Autorizar Cliente / Dispositivo</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreateClient} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="client-user">Usuario del dispositivo</Label>
                    <Input
                      id="client-user"
                      placeholder="dispositivo01"
                      value={newClientUser}
                      onChange={(e) => setNewClientUser(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="client-pass">Contraseña del dispositivo</Label>
                    <Input
                      id="client-pass"
                      type="password"
                      placeholder="******"
                      value={newClientPass}
                      onChange={(e) => setNewClientPass(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="client-max">Conexiones concurrentes máximas</Label>
                    <Input
                      id="client-max"
                      type="number"
                      value={newClientMaxConn}
                      onChange={(e) => setNewClientMaxConn(parseInt(e.target.value) || 1)}
                      min={1}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="client-expires">Vencimiento de suscripción</Label>
                    <Input
                      id="client-expires"
                      type="datetime-local"
                      value={newClientExpires}
                      onChange={(e) => setNewClientExpires(e.target.value)}
                    />
                  </div>
                  <Button type="submit" className="w-full">
                    <Plus className="mr-2 h-4 w-4" />
                    Autorizar Suscripción
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Clientes Habilitados</CardTitle>
              </CardHeader>
              <CardContent>
                {clients.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-12">No hay clientes autorizados.</p>
                ) : (
                  <div className="space-y-4">
                    {clients.map((c) => {
                      const m3uUrl = `${currentHost}/api/v1/streaming/get.php?username=${c.username}&password=${c.password}`;
                      const isExpired = c.expires_at && new Date(c.expires_at) < new Date();
                      return (
                        <div key={c.id} className="p-4 border rounded-lg bg-muted/10 space-y-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="font-semibold text-sm flex items-center gap-2">
                                {c.username}
                                {isExpired && (
                                  <Badge variant="destructive" className="text-[9px]">
                                    Expirado
                                  </Badge>
                                )}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                Conexiones: <strong>{c.max_connections}</strong> max · Vence:{" "}
                                {c.expires_at ? new Date(c.expires_at).toLocaleString() : "Nunca"}
                              </p>
                            </div>
                            <Button variant="destructive" size="sm" onClick={() => handleDeleteClient(c.id)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>

                          <div className="space-y-2 pt-2 border-t text-xs">
                            <div className="space-y-1">
                              <span className="text-muted-foreground">Lista M3U Playback:</span>
                              <div className="flex gap-2">
                                <Input readOnly value={m3uUrl} className="h-7 text-xs font-mono" />
                                <Button
                                  variant="outline"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={() => copyToClipboard(m3uUrl, c.id)}
                                >
                                  {copiedClientId === c.id ? (
                                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                                  ) : (
                                    <Copy className="h-3.5 w-3.5" />
                                  )}
                                </Button>
                              </div>
                            </div>

                            <div className="space-y-1">
                              <span className="text-muted-foreground">Xtream Codes Credentials:</span>
                              <div className="grid gap-2 grid-cols-3 p-2 bg-muted/40 rounded border font-mono">
                                <div>URL: {currentHost.replace(/^https?:\/\//, "")}</div>
                                <div>User: {c.username}</div>
                                <div>Pass: {c.password}</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 4. ACTIVE CONNECTIONS */}
        <TabsContent value="connections" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Conexiones de Clientes en Vivo</CardTitle>
            </CardHeader>
            <CardContent>
              {connections.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-12">No hay sesiones activas.</p>
              ) : (
                <div className="overflow-x-auto border rounded-lg">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/40 border-b">
                        <th className="px-4 py-2 text-left font-medium">Cliente</th>
                        <th className="px-4 py-2 text-left font-medium">Canal de Video</th>
                        <th className="px-4 py-2 text-left font-medium">IP del Cliente</th>
                        <th className="px-4 py-2 text-left font-medium">Datos transferidos</th>
                        <th className="px-4 py-2 text-left font-medium">Hora Conexión</th>
                      </tr>
                    </thead>
                    <tbody>
                      {connections.map((c) => (
                        <tr key={c.id} className="border-b last:border-0">
                          <td className="px-4 py-2 font-medium">{c.client_username}</td>
                          <td className="px-4 py-2">{c.channel_name}</td>
                          <td className="px-4 py-2 font-mono text-xs">{c.ip_address}</td>
                          <td className="px-4 py-2">
                            {(c.bytes_transferred / (1024 * 1024)).toFixed(2)} MB
                          </td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {new Date(c.connected_at).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 5. EPG LOCAL GUIDE */}
        <TabsContent value="epg" className="space-y-4">
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Importador XMLTV EPG</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSyncEpg} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="epg-input">XMLTV URL (.xml / .xml.gz)</Label>
                    <Input
                      id="epg-input"
                      placeholder="http://epg.provider.com/guide.xml"
                      value={epgUrl}
                      onChange={(e) => setEpgUrl(e.target.value)}
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full">
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Sincronizar EPG
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Canales del Catálogo con Guía de EPG</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 rounded-lg border p-4 bg-muted/10">
                  <div className="flex items-start gap-2 text-sm text-amber-600">
                    <ShieldAlert className="h-5 w-5 shrink-0" />
                    <p className="text-xs">
                      Los clientes que reproduzcan su lista M3U o a través de Xtream Codes recibirán
                      la programación de los canales que coincidan con la etiqueta <strong>EPG ID</strong> configurada en el catálogo.
                    </p>
                  </div>
                  <div className="pt-2 text-xs space-y-1">
                    <p className="font-semibold">Mapeo dinámico XMLTV:</p>
                    <p className="text-muted-foreground">
                      Exporte a sus dispositivos el feed de programación EPG ControlBox en:
                    </p>
                    <Input
                      readOnly
                      value={`${currentHost}/api/v1/streaming/epg.xml?username=CLIENT_USER&password=CLIENT_PASS`}
                      className="font-mono text-xs h-8"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
