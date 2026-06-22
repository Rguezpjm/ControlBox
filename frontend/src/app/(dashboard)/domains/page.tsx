"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Globe, Link2 } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/skeletons";
import { StatusBadge } from "@/components/shared/status-badge";
import { websitesApi } from "@/lib/websites";
import { wordpressApi } from "@/lib/wordpress";
import { dnsApi } from "@/lib/dns";

interface DomainRow {
  id: string;
  domain: string;
  source: string;
  status: string;
  ssl?: string;
}

function DomainsContent() {
  const [rows, setRows] = useState<DomainRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [websites, wpSites, zones] = await Promise.all([
          websitesApi.list().catch(() => []),
          wordpressApi.list().catch(() => []),
          dnsApi.listZones().catch(() => []),
        ]);

        const seen = new Set<string>();
        const next: DomainRow[] = [];

        for (const site of websites) {
          if (!site.domain || seen.has(site.domain)) continue;
          seen.add(site.domain);
          next.push({
            id: site.id,
            domain: site.domain,
            source: "Website",
            status: site.status,
            ssl: site.ssl_status,
          });
        }

        for (const site of wpSites) {
          if (!site.domain || seen.has(site.domain)) continue;
          seen.add(site.domain);
          next.push({
            id: site.id,
            domain: site.domain,
            source: "WordPress",
            status: site.status,
            ssl: site.ssl_status,
          });
        }

        for (const zone of zones) {
          if (!zone.name || seen.has(zone.name)) continue;
          seen.add(zone.name);
          next.push({
            id: zone.id,
            domain: zone.name,
            source: "DNS Zone",
            status: zone.status ?? "active",
          });
        }

        setRows(next);
      } catch {
        setRows([]);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const sorted = useMemo(
    () => [...rows].sort((a, b) => a.domain.localeCompare(b.domain)),
    [rows]
  );

  if (loading) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Domains"
        description="Domains connected to your websites, WordPress sites, and DNS zones"
        action={
          <Button asChild variant="outline">
            <Link href="/websites">
              <Globe className="h-4 w-4" />
              Add website
            </Link>
          </Button>
        }
      />

      <Card>
        <CardContent className="p-0">
          {sorted.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              No domains yet. Create a website or WordPress site to assign a domain.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Domain</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Source</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">SSL</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((row) => (
                    <tr key={`${row.source}-${row.id}`} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Link2 className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{row.domain}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline">{row.source}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">
                        {row.ssl ?? "—"}
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

export default function DomainsPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <DomainsContent />
    </Suspense>
  );
}
