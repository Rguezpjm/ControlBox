"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ExternalLink, MoreHorizontal, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { SslDaysCell } from "@/components/shared/ssl-days-cell";
import { MiniSparkline } from "@/components/shared/mini-sparkline";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ResourceStatus } from "@/types";

export interface SiteTableRow {
  id: string;
  name: string;
  domain: string;
  status: string;
  ssl_enabled?: boolean;
  ssl_status?: string;
  ssl_days_remaining?: number | null;
  traffic_mbps?: number;
  traffic_sparkline?: number[];
  href?: string;
  subtitle?: string;
}

interface SiteListTableProps {
  rows: SiteTableRow[];
  searchPlaceholder?: string;
  emptyMessage?: string;
  onSiteClick?: (row: SiteTableRow) => void;
  renderActions?: (row: SiteTableRow) => React.ReactNode;
}

function mapStatus(status: string): ResourceStatus {
  const map: Record<string, ResourceStatus> = {
    running: "running",
    stopped: "stopped",
    pending: "pending",
    provisioning: "pending",
    maintenance: "pending",
    error: "error",
    deleting: "pending",
  };
  return map[status] || "pending";
}

export function SiteListTable({
  rows,
  searchPlaceholder = "Search sites...",
  emptyMessage = "No sites found",
  onSiteClick,
  renderActions,
}: SiteListTableProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (row) =>
        row.name.toLowerCase().includes(q) ||
        row.domain.toLowerCase().includes(q) ||
        (row.subtitle?.toLowerCase().includes(q) ?? false)
    );
  }, [rows, query]);

  return (
    <div className="space-y-4">
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={searchPlaceholder}
          className="pl-9"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">{emptyMessage}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Site</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">SSL</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Tráfico</th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <div className="min-w-[180px]">
                          {onSiteClick ? (
                            <button
                              type="button"
                              onClick={() => onSiteClick(row)}
                              className="font-medium text-left hover:text-primary hover:underline"
                            >
                              {row.name}
                            </button>
                          ) : row.href ? (
                            <Link href={row.href} className="font-medium hover:text-primary hover:underline">
                              {row.name}
                            </Link>
                          ) : (
                            <p className="font-medium">{row.name}</p>
                          )}
                          <a
                            href={`https://${row.domain}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
                          >
                            {row.domain}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                          {row.subtitle && (
                            <p className="mt-0.5 text-xs text-muted-foreground">{row.subtitle}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={mapStatus(row.status)} />
                      </td>
                      <td className="px-4 py-3">
                        <SslDaysCell
                          days={row.ssl_days_remaining}
                          sslEnabled={row.ssl_enabled}
                          sslStatus={row.ssl_status}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex min-w-[100px] flex-col gap-1">
                          <span className="text-xs font-medium tabular-nums">
                            {(row.traffic_mbps ?? 0).toFixed(2)} Mbps
                          </span>
                          <MiniSparkline
                            data={row.traffic_sparkline ?? []}
                            className="text-emerald-500"
                          />
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {renderActions ? (
                          renderActions(row)
                        ) : (
                          <Button variant="ghost" size="icon" className="h-8 w-8" disabled>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
