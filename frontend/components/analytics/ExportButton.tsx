"use client";

import { useState } from "react";
import { fileUrl } from "@/lib/api";
import { exportMetricsUrl } from "@/lib/services/analytics";

interface ExportButtonProps {
  orgId: string;
  dateRange: string;
}

export function ExportButton({ orgId, dateRange }: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async (format: "csv" | "json") => {
    setOpen(false);
    setError(null);
    try {
      const token = window.localStorage.getItem("access_token");
      const response = await fetch(fileUrl(exportMetricsUrl(orgId, dateRange, format)), {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        credentials: "include",
      });
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analytics.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  };

  return (
    <div className="relative">
      <button
        type="button" onClick={() => setOpen((o) => !o)}
        className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-surface-muted"
      >
        Export
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-32 rounded-lg border border-border bg-surface shadow-sm">
          <button type="button" onClick={() => void download("csv")} className="block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-surface-muted">CSV</button>
          <button type="button" onClick={() => void download("json")} className="block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-surface-muted">JSON</button>
        </div>
      )}
      {error && <p className="absolute right-0 mt-1 w-48 text-xs text-danger">{error}</p>}
    </div>
  );
}
