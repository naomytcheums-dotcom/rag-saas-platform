"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface PartnerCommission {
  id: string;
  period_start: string;
  period_end: string;
  amount_cents: number;
  status: "pending" | "paid";
  paid_at: string | null;
}

function formatCents(cents: number): string {
  return (cents / 100).toLocaleString(undefined, { style: "currency", currency: "EUR" });
}

export function CommissionList() {
  const [commissions, setCommissions] = useState<PartnerCommission[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setCommissions(await api.get<PartnerCommission[]>("/partners/me/commissions"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load commissions");
      }
    })();
  }, []);

  if (error) {
    return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  }

  if (!commissions) {
    return <p className="text-sm text-foreground-muted">Loading…</p>;
  }

  if (commissions.length === 0) {
    return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No commissions recorded yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase text-foreground-muted">
            <th className="px-4 py-3">Period</th>
            <th className="px-4 py-3">Amount</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Paid at</th>
          </tr>
        </thead>
        <tbody>
          {commissions.map((commission) => (
            <tr key={commission.id} className="border-b border-border last:border-0">
              <td className="px-4 py-3 text-foreground">{commission.period_start} — {commission.period_end}</td>
              <td className="px-4 py-3 text-foreground">{formatCents(commission.amount_cents)}</td>
              <td className="px-4 py-3">
                <span className={commission.status === "paid" ? "rounded-full bg-success-soft px-2 py-0.5 text-xs text-success" : "rounded-full bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted"}>
                  {commission.status}
                </span>
              </td>
              <td className="px-4 py-3 text-foreground-muted">{commission.paid_at ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
