"use client";

import { useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";

export interface Reseller {
  id: string;
  organization_id: string;
  commission_percent: number;
  is_active: boolean;
  referral_code: string;
}

export function PartnerDashboard() {
  const [reseller, setReseller] = useState<Reseller | null>(null);
  const [notPartner, setNotPartner] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

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

  // /r/{code} is served by the backend API (api/routers/sales.py), not
  // a Next.js route -- fileUrl() points at NEXT_PUBLIC_API_URL, the
  // frontend's own origin would be the wrong host entirely.
  const referralLink = fileUrl(`/r/${reseller.referral_code}`);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(referralLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy the link -- copy it manually instead.");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-xs font-medium uppercase text-foreground-muted">Commission rate</h2>
          <p className="mt-2 text-2xl font-semibold text-foreground">{reseller.commission_percent}%</p>
          <p className="mt-1 text-xs text-foreground-muted">Applied to your sub-clients&apos; active monthly subscriptions.</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-xs font-medium uppercase text-foreground-muted">Status</h2>
          <p className="mt-2 text-2xl font-semibold text-foreground">{reseller.is_active ? "Active" : "Inactive"}</p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Your referral link</h2>
        <p className="mt-1 text-xs text-foreground-muted">Share this link -- anyone who signs up through it is automatically attributed to you.</p>
        <div className="mt-3 flex items-center gap-2">
          <input readOnly value={referralLink} className="flex-1 rounded-lg border border-border bg-surface-muted px-3 py-2 text-sm text-foreground" />
          <button
            type="button" onClick={copyLink}
            className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
    </div>
  );
}
