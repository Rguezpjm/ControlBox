"use client";

import { useState } from "react";
import { Copy, Check, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface CredentialRowProps {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
  secret?: boolean;
  href?: string;
}

export function CredentialRow({ label, value, mono = false, secret = false, href }: CredentialRowProps) {
  const [visible, setVisible] = useState(!secret);
  const [copied, setCopied] = useState(false);
  const display = value?.trim() ? value : "—";

  async function copyValue() {
    if (!value?.trim()) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success("Copiado al portapapeles");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("No se pudo copiar");
    }
  }

  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        {href && value ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={`break-all text-primary hover:underline ${mono ? "font-mono text-xs" : ""}`}
          >
            {display}
          </a>
        ) : (
          <p className={`break-all ${mono ? "font-mono text-xs" : ""}`}>
            {secret && !visible ? "••••••••••••" : display}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {secret && value ? (
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={() => setVisible((v) => !v)}>
            {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        ) : null}
        {value ? (
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={copyValue}>
            {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
