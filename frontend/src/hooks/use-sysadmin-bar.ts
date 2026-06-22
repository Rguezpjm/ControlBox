"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { getSystemInfo, type SystemInfo } from "@/lib/platform";

interface SessionUser {
  email: string;
  full_name: string;
}

export function useSysadminBar() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const [me, sys] = await Promise.all([
          api.auth.me() as Promise<{ email: string; full_name: string }>,
          getSystemInfo().catch(() => null),
        ]);
        if (!active) return;
        setUser({ email: me.email, full_name: me.full_name });
        setSystem(sys);
      } catch {
        if (active) {
          setUser(null);
          setSystem(null);
        }
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, []);

  return { user, system };
}
