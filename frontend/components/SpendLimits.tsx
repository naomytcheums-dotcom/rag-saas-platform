"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

interface SettingsSlice {
  daily_credit_limit: number | null;
  monthly_credit_limit: number | null;
}

/** Organization-level daily / monthly credit caps (`daily_credit_limit` /
 * `monthly_credit_limit` in `PATCH /organizations/{id}/settings`). Empty means
 * "no cap". Only the Owner can change them (the endpoint is Owner-only); the
 * inputs are read-only for anyone else instead of failing on save. */
export default function SpendLimits({ orgId, canEdit }: { orgId: string; canEdit: boolean }) {
  const { t } = useTranslation();
  const [daily, setDaily] = useState("");
  const [monthly, setMonthly] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<SettingsSlice>(`/organizations/${orgId}/settings`)
      .then((s) => {
        setDaily(s.daily_credit_limit === null ? "" : String(s.daily_credit_limit));
        setMonthly(s.monthly_credit_limit === null ? "" : String(s.monthly_credit_limit));
      })
      .catch(() => {
        /* Admin+ only endpoint: a lower role simply sees empty read-only fields */
      });
  }, [orgId]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    // An EXPLICITLY sent `null` is stored as "no cap" (the PATCH is a partial update
    // keyed on which fields were sent, not on their value), so an emptied field
    // clears its cap; a typed 0 freezes spending.
    const body = {
      daily_credit_limit: daily === "" ? null : Number(daily),
      monthly_credit_limit: monthly === "" ? null : Number(monthly),
    };
    try {
      await api.patch(`/organizations/${orgId}/settings`, body);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("spend.error_generic"));
    }
  }

  return (
    <form onSubmit={save} className="mt-6 rounded-xl border border-border bg-surface p-4">
      <h2 className="text-sm font-semibold text-foreground">{t("spend.title")}</h2>
      <p className="mt-1 text-xs text-foreground-muted">{t("spend.hint")}</p>
      {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
      {saved && <p role="status" className="mt-2 text-sm text-success">{t("spend.saved")}</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-sm">{t("spend.daily")}
          <input type="number" min="0" step="1" disabled={!canEdit} value={daily} onChange={(e) => setDaily(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" />
        </label>
        <label className="text-sm">{t("spend.monthly")}
          <input type="number" min="0" step="1" disabled={!canEdit} value={monthly} onChange={(e) => setMonthly(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" />
        </label>
      </div>
      {canEdit && <button type="submit" className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">{t("spend.save")}</button>}
    </form>
  );
}
