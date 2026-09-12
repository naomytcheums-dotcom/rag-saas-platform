"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

export interface Reseller {
  id: string;
  organization_id: string;
  commission_percent: number;
  is_active: boolean;
}

export function PartnerDashboard() {
  const [reseller, setReseller] = useState<Reseller | null>(null);
  const [notPartner, setNotPartner] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setReseller(await api.get<Reseller>("/partners/me"));
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setNotPartner(true);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load partner profile");
        }
      }
    })();
  }, []);

  if (notPartner) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">
        You are not a registered partner yet. Register at <code className="rounded bg-surface-muted px-1 py-0.5">/partners/register</code> to bring on your own clients and earn commission.
      </div>
    );
  }

  if (error) {
    return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  }

  if (!reseller) {
    return <p className="text-sm text-foreground-muted">Loading…</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Commission rate</h2>
        <p className="mt-2 text-2xl font-semibold text-foreground">{reseller.commission_percent}%</p>
        <p className="mt-1 text-xs text-foreground-muted">Applied to your sub-clients' active monthly subscriptions.</p>
      </div>
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Status</h2>
        <p className="mt-2 text-2xl font-semibold text-foreground">{reseller.is_active ? "Active" : "Inactive"}</p>
      </div>
    </div>
  );
}
