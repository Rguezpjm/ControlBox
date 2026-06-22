"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";

function SupabaseRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/databases?tab=supabase");
  }, [router]);
  return null;
}

export default function SupabasePage() {
  return (
    <Suspense>
      <SupabaseRedirect />
    </Suspense>
  );
}
