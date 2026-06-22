"use client";

import { Suspense } from "react";
import { Mail } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent } from "@/components/ui/card";

function EmailContent() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Email"
        description="Email hosting for your domains"
      />

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
            <Mail className="h-7 w-7 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">Email hosting not configured</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Mail server integration is not enabled on this server yet. When configured, email accounts
            and quotas will appear here with live data from the platform.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function EmailPage() {
  return (
    <Suspense>
      <EmailContent />
    </Suspense>
  );
}
