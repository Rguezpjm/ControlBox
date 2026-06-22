"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  siteModificationApi,
  type AccessLogEntry,
  type SiteType,
} from "@/lib/site-modification";
import { cn } from "@/lib/utils";

const LIMIT_OPTIONS = [
  { label: "50", value: 50 },
  { label: "100", value: 100 },
  { label: "500", value: 500 },
  { label: "All", value: 0 },
] as const;

function statusClass(status: number): string {
  if (status >= 500) return "text-red-400";
  if (status >= 400) return "text-amber-400";
  if (status >= 300) return "text-sky-400";
  if (status >= 200) return "text-emerald-400";
  return "text-zinc-300";
}

function AccessLogLine({ entry }: { entry: AccessLogEntry }) {
  if (!entry.ip && entry.raw) {
    return (
      <div className="py-0.5 text-zinc-400 break-all">{entry.raw}</div>
    );
  }

  return (
    <div className="py-0.5 leading-relaxed break-all">
      <span className="text-amber-500">{entry.ip}</span>
      <span className="text-emerald-400"> [{entry.timestamp}]</span>
      <span className="text-zinc-100">
        {" "}
        &quot;{entry.method} {entry.path} {entry.protocol}&quot;
      </span>
      <span className={cn("font-medium", statusClass(entry.status))}>
        {" "}
        {entry.status}
      </span>
      <span className="text-zinc-500"> {entry.bytes}</span>
      {entry.user_agent ? (
        <span className="text-zinc-500"> &quot;{entry.user_agent}&quot;</span>
      ) : null}
      {entry.ip_location ? (
        <span className="text-cyan-400/90">
          {" "}
          — {entry.ip_location}
        </span>
      ) : null}
    </div>
  );
}

interface SiteAccessLogViewerProps {
  siteType: SiteType;
  siteId: string;
  active: boolean;
}

export function SiteAccessLogViewer({
  siteType,
  siteId,
  active,
}: SiteAccessLogViewerProps) {
  const [limit, setLimit] = useState(100);
  const [accessSource, setAccessSource] = useState("");
  const [accessEntries, setAccessEntries] = useState<AccessLogEntry[]>([]);
  const [errorSource, setErrorSource] = useState("");
  const [errorContent, setErrorContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    if (!siteId) return;
    setLoading(true);
    setError(null);
    try {
      const [access, err] = await Promise.all([
        siteModificationApi.accessLogs(siteType, siteId, limit),
        siteModificationApi.errorLog(siteType, siteId, limit),
      ]);
      setAccessSource(access.source);
      setAccessEntries(access.entries);
      setErrorSource(err.source);
      setErrorContent(err.content);
    } catch {
      setError("Failed to load site logs");
      setAccessEntries([]);
      setErrorContent("");
    } finally {
      setLoading(false);
    }
  }, [siteId, siteType, limit]);

  useEffect(() => {
    if (active && siteId) {
      loadLogs();
    }
  }, [active, siteId, loadLogs]);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Access log</Label>
        <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
          <div className="max-h-[360px] overflow-auto p-3 font-mono text-[11px] sm:text-xs">
            {loading && accessEntries.length === 0 ? (
              <div className="flex items-center gap-2 text-zinc-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading access log…
              </div>
            ) : accessEntries.length === 0 ? (
              <p className="text-zinc-500">(empty)</p>
            ) : (
              accessEntries.map((entry, index) => (
                <AccessLogLine key={`${entry.raw}-${index}`} entry={entry} />
              ))
            )}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800 bg-zinc-900/80 px-3 py-2 text-xs">
            <p className="min-w-0 truncate text-zinc-400">
              From{" "}
              <span className="text-emerald-400">{accessSource || "—"}</span>
            </p>
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="text-zinc-500">Last</span>
              {LIMIT_OPTIONS.map((opt) => (
                <Button
                  key={opt.label}
                  type="button"
                  variant={limit === opt.value ? "default" : "outline"}
                  size="sm"
                  className={cn(
                    "h-7 min-w-[2.5rem] px-2 text-xs",
                    limit === opt.value
                      ? "bg-emerald-600 text-white hover:bg-emerald-600/90"
                      : "border-zinc-700 bg-zinc-950 text-zinc-300 hover:bg-zinc-800"
                  )}
                  onClick={() => setLimit(opt.value)}
                  disabled={loading}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Error log</Label>
        <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
          <pre className="max-h-[200px] overflow-auto p-3 font-mono text-[11px] leading-relaxed text-zinc-300 sm:text-xs whitespace-pre-wrap break-all">
            {loading && !errorContent ? "Loading error log…" : errorContent || "(empty)"}
          </pre>
          {errorSource ? (
            <div className="border-t border-zinc-800 bg-zinc-900/80 px-3 py-2 text-xs text-zinc-400">
              From <span className="text-emerald-400">{errorSource}</span>
            </div>
          ) : null}
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <Button variant="outline" size="sm" onClick={loadLogs} disabled={loading}>
        {loading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <RefreshCw className="mr-2 h-4 w-4" />
        )}
        Refresh logs
      </Button>
    </div>
  );
}
