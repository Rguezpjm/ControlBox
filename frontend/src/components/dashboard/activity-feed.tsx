"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRealtime } from "@/hooks/use-realtime";
import { useI18n } from "@/providers/i18n-provider";
import { formatDistanceToNow } from "date-fns";
import { Activity, AlertTriangle, BarChart3, RefreshCw } from "lucide-react";

const eventIcons = {
  metric: BarChart3,
  status: RefreshCw,
  alert: AlertTriangle,
  backup: Activity,
  deployment: RefreshCw,
};

export function ActivityFeed() {
  const { events, connected } = useRealtime();
  const { t } = useI18n();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-sm font-medium">{t("dashboard.liveActivity")}</CardTitle>
        {connected && (
          <span className="flex items-center gap-1.5 text-xs text-success">
            <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
            {t("dashboard.streaming")}
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">{t("dashboard.waitingEvents")}</p>
        ) : (
          events.slice(0, 8).map((event, i) => {
            const Icon = eventIcons[event.type] || Activity;
            return (
              <div key={`${event.timestamp}-${i}`} className="flex items-start gap-3 text-sm">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted">
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">
                    {event.type} · {event.resource}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
