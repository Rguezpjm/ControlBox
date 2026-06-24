"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck, ChevronRight, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { securityApi, type VulnerabilityAssessment } from "@/lib/security";
import { VulnerabilitySummaryModal } from "@/components/security/vulnerability-summary-modal";

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-destructive/15 text-destructive",
  medium: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  low: "bg-muted text-muted-foreground",
};

export function ServerVulnerabilities() {
  const [assessment, setAssessment] = useState<VulnerabilityAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setAssessment(await securityApi.vulnerabilities());
    } catch {
      setAssessment(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const top = (assessment?.findings || []).slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <ShieldAlert className="h-4 w-4 text-amber-500" />
          Server Vulnerabilities
        </CardTitle>
        {assessment && (
          <Badge variant="outline" className="text-[10px] tabular-nums">
            {assessment.total} riesgos
          </Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : !assessment ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No se pudo cargar la evaluación de seguridad.
          </p>
        ) : (
          <>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-4 border-amber-500/40 text-sm font-bold tabular-nums">
                {assessment.score}
              </div>
              <div className="flex flex-1 gap-2 text-xs">
                <span className="text-destructive">{assessment.high} High</span>
                <span className="text-amber-500">{assessment.medium} Medium</span>
                <span className="text-muted-foreground">{assessment.low} Low</span>
              </div>
            </div>

            {top.length === 0 ? (
              <p className="flex items-center justify-center gap-2 py-4 text-sm text-emerald-600">
                <ShieldCheck className="h-4 w-4" />
                Sin vulnerabilidades de configuración
              </p>
            ) : (
              <div className="space-y-2">
                {top.map((f) => (
                  <div key={f.id} className="flex items-start gap-2 text-sm">
                    <Badge variant="outline" className={`${SEVERITY_STYLES[f.severity] || SEVERITY_STYLES.low} shrink-0 text-[10px]`}>
                      {f.severity}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{f.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{f.target}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <Button variant="outline" size="sm" className="w-full" onClick={() => setOpen(true)}>
              Ver resumen
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </>
        )}
      </CardContent>

      <VulnerabilitySummaryModal
        open={open}
        onOpenChange={setOpen}
        assessment={assessment}
        onRefresh={load}
      />
    </Card>
  );
}
