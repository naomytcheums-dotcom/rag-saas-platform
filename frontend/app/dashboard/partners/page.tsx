"use client";

import { CommissionList } from "@/components/partners/CommissionList";
import { PartnerDashboard } from "@/components/partners/PartnerDashboard";

export default function PartnersPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Partner program</h1>
      <p className="mt-1 text-sm text-foreground-muted">Your commission rate, status, and payout history.</p>

      <div className="mt-5">
        <PartnerDashboard />
      </div>

      <h2 className="mt-8 text-sm font-medium text-foreground">Commissions</h2>
      <div className="mt-3">
        <CommissionList />
      </div>
    </div>
  );
}
