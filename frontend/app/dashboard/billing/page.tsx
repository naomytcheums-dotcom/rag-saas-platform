"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface Plan {
  id: string;
  key: string;
  name: string;
  monthly_price_cents: number;
  yearly_price_cents: number;
  max_documents: number | null;
  max_agents: number | null;
  max_members: number | null;
  priority_support: boolean;
  advanced_features: boolean;
  sla: boolean;
  is_active: boolean;
}

interface Subscription {
  id: string;
  plan_id: string;
  status: string;
  billing_period: string;
  current_period_end: string | null;
  canceled_at: string | null;
}

interface Credit {
  organization_id: string;
  balance: number;
}

interface CreditTransaction {
  id: string;
  type: string;
  amount: number;
  balance_after: number;
  reason: string | null;
  created_at: string;
}

interface CreditPack {
  id: string;
  name: string;
  credits: number;
  price_cents: number;
}

interface Invoice {
  id: string;
  number: string;
  status: string;
  currency: string;
  subtotal_cents: number;
  vat_cents: number;
  total_cents: number;
  due_date: string | null;
  paid_at: string | null;
  created_at: string;
}

interface UsageSummary {
  total_by_metric: Record<string, number>;
  by_day: { date: string; metrics: Record<string, number> }[];
}

const TABS = ["Overview", "Plans", "Usage", "Credits", "Invoices", "Payment"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  Overview: "Vue d'ensemble", Plans: "Forfaits", Usage: "Usage", Credits: "Crédits", Invoices: "Factures", Payment: "Paiement",
};

function money(cents: number, currency = "EUR"): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency }).format(cents / 100);
}

export default function BillingPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const [tab, setTab] = useState<Tab>("Overview");
  const [error, setError] = useState<string | null>(null);

  if (orgLoading || !org) {
    return <div className="mx-auto max-w-4xl text-sm text-foreground-muted">Chargement…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Facturation</h1>
      <p className="mt-1 text-sm text-foreground-muted">Forfait, abonnement, usage, crédits et factures pour {org.name}.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === t ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Overview" && <OverviewTab orgId={org.id} onError={setError} />}
        {tab === "Plans" && <PlansTab orgId={org.id} onError={setError} />}
        {tab === "Usage" && <UsageTab orgId={org.id} onError={setError} />}
        {tab === "Credits" && <CreditsTab orgId={org.id} onError={setError} />}
        {tab === "Invoices" && <InvoicesTab orgId={org.id} onError={setError} />}
        {tab === "Payment" && <PaymentTab orgId={org.id} onError={setError} />}
      </div>
    </div>
  );
}

function OverviewTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [credit, setCredit] = useState<Credit | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  const load = useCallback(async () => {
    try {
      const subRes = await api.get<Subscription>(`/organizations/${orgId}/billing/subscription`);
      setSub(subRes);
      const [planRes, creditRes, invoicesRes] = await Promise.all([
        api.get<Plan>(`/billing/plans/${subRes.plan_id}`),
        api.get<Credit>(`/organizations/${orgId}/billing/credits`),
        api.get<Invoice[]>(`/organizations/${orgId}/billing/invoices?limit=5`),
      ]);
      setPlan(planRes);
      setCredit(creditRes);
      setInvoices(invoicesRes);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du chargement de l'aperçu de facturation");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-xs font-medium uppercase text-foreground-muted">Forfait actuel</h2>
          <p className="mt-2 text-2xl font-semibold text-foreground">{plan?.name ?? "…"}</p>
          <p className="mt-1 text-xs text-foreground-muted">
            {plan ? money(sub?.billing_period === "yearly" ? plan.yearly_price_cents : plan.monthly_price_cents) : ""}
            {plan ? ` / ${sub?.billing_period === "yearly" ? "an" : "mois"}` : ""}
          </p>
          <p className="mt-2 text-xs text-foreground-muted">Statut : {sub?.status ?? "…"}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-xs font-medium uppercase text-foreground-muted">Crédits</h2>
          <p className="mt-2 text-2xl font-semibold text-foreground">{credit?.balance ?? "…"}</p>
          <p className="mt-1 text-xs text-foreground-muted">disponibles</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-xs font-medium uppercase text-foreground-muted">Renouvellement</h2>
          <p className="mt-2 text-lg font-semibold text-foreground">{sub?.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : "—"}</p>
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Factures récentes</h2>
        {invoices.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucune facture pour l&apos;instant.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {invoices.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
                <span>{inv.number}</span>
                <span className="text-foreground-muted">{money(inv.total_cents, inv.currency)}</span>
                <span className="text-xs uppercase text-foreground-muted">{inv.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PlansTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");

  const load = useCallback(async () => {
    try {
      const [plansRes, subRes] = await Promise.all([
        api.get<Plan[]>("/billing/plans"),
        api.get<Subscription>(`/organizations/${orgId}/billing/subscription`),
      ]);
      setPlans(plansRes);
      setSub(subRes);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du chargement des forfaits");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function choosePlan(planId: string) {
    try {
      await api.post(`/organizations/${orgId}/billing/subscribe`, { plan_id: planId, billing_period: period });
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du changement de forfait");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => setPeriod("monthly")} className={`rounded-lg px-3 py-1.5 text-sm font-medium ${period === "monthly" ? "bg-accent text-white" : "border border-border text-foreground-muted"}`}>Mensuel</button>
        <button type="button" onClick={() => setPeriod("yearly")} className={`rounded-lg px-3 py-1.5 text-sm font-medium ${period === "yearly" ? "bg-accent text-white" : "border border-border text-foreground-muted"}`}>Annuel</button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {plans.map((plan) => {
          const isCurrent = sub?.plan_id === plan.id;
          const price = period === "yearly" ? plan.yearly_price_cents : plan.monthly_price_cents;
          return (
            <div key={plan.id} className={`rounded-xl border p-5 ${isCurrent ? "border-accent" : "border-border"} bg-surface`}>
              <h3 className="text-sm font-semibold text-foreground">{plan.name}</h3>
              <p className="mt-2 text-2xl font-semibold text-foreground">{money(price)}<span className="text-sm font-normal text-foreground-muted"> / {period === "yearly" ? "an" : "mois"}</span></p>
              <ul className="mt-3 flex flex-col gap-1 text-xs text-foreground-muted">
                <li>{plan.max_documents ?? "Illimité"} documents</li>
                <li>{plan.max_agents ?? "Illimité"} agents</li>
                <li>{plan.max_members ?? "Illimité"} membres</li>
                {plan.priority_support && <li>Support prioritaire</li>}
                {plan.advanced_features && <li>Fonctionnalités avancées</li>}
                {plan.sla && <li>SLA</li>}
              </ul>
              <button
                type="button"
                disabled={isCurrent}
                onClick={() => void choosePlan(plan.id)}
                className="mt-4 w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isCurrent ? "Forfait actuel" : "Choisir ce forfait"}
              </button>
            </div>
          );
        })}
      </div>

      {sub && sub.status !== "canceled" && (
        <button
          type="button"
          onClick={async () => {
            try {
              await api.post(`/organizations/${orgId}/billing/cancel`, { reason: null });
              await load();
            } catch (err) {
              onError(err instanceof ApiError ? String(err.detail) : "Échec de l'annulation de l'abonnement");
            }
          }}
          className="self-start text-xs font-medium text-danger hover:underline"
        >
          Annuler l&apos;abonnement
        </button>
      )}
      {sub && sub.status === "canceled" && (
        <button
          type="button"
          onClick={async () => {
            try {
              await api.post(`/organizations/${orgId}/billing/reactivate`);
              await load();
            } catch (err) {
              onError(err instanceof ApiError ? String(err.detail) : "Échec de la réactivation de l'abonnement");
            }
          }}
          className="self-start text-xs font-medium text-accent hover:underline"
        >
          Réactiver l&apos;abonnement
        </button>
      )}
    </div>
  );
}

function UsageTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [forecast, setForecast] = useState<{ projected_next_period: Record<string, number> } | null>(null);

  const load = useCallback(async () => {
    try {
      const [usageRes, forecastRes] = await Promise.all([
        api.get<UsageSummary>(`/organizations/${orgId}/billing/usage?period_days=30`),
        api.get<{ projected_next_period: Record<string, number> }>(`/organizations/${orgId}/billing/usage/forecast`),
      ]);
      setUsage(usageRes);
      setForecast(forecastRes);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du chargement de l'usage");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  const metrics = usage ? Object.entries(usage.total_by_metric) : [];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Usage — 30 derniers jours</h2>
        {metrics.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucun usage enregistré pour l&apos;instant pour cette organisation.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {metrics.map(([metric, total]) => (
              <div key={metric} className="rounded-xl border border-border bg-surface p-4">
                <p className="text-xs font-medium uppercase text-foreground-muted">{metric.replace(/_/g, " ")}</p>
                <p className="mt-1 text-xl font-semibold text-foreground">{total}</p>
                {forecast?.projected_next_period[metric] !== undefined && (
                  <p className="mt-1 text-xs text-foreground-muted">≈ {forecast.projected_next_period[metric]} projeté pour la prochaine période</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CreditsTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [credit, setCredit] = useState<Credit | null>(null);
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [packs, setPacks] = useState<CreditPack[]>([]);

  const load = useCallback(async () => {
    try {
      const [creditRes, txRes, packsRes] = await Promise.all([
        api.get<Credit>(`/organizations/${orgId}/billing/credits`),
        api.get<CreditTransaction[]>(`/organizations/${orgId}/billing/credits/transactions`),
        api.get<CreditPack[]>(`/organizations/${orgId}/billing/credits/packs`),
      ]);
      setCredit(creditRes);
      setTransactions(txRes);
      setPacks(packsRes);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du chargement des crédits");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function purchase(packId: string) {
    try {
      await api.post(`/organizations/${orgId}/billing/credits/purchase`, { pack_id: packId });
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec de l'achat de crédits");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Solde</h2>
        <p className="mt-2 text-3xl font-semibold text-foreground">{credit?.balance ?? "…"}</p>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Packs de crédits</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          {packs.map((pack) => (
            <div key={pack.id} className="rounded-xl border border-border bg-surface p-4">
              <p className="text-sm font-semibold text-foreground">{pack.name}</p>
              <p className="mt-1 text-xs text-foreground-muted">{pack.credits.toLocaleString()} crédits</p>
              <p className="mt-1 text-sm font-medium text-foreground">{money(pack.price_cents)}</p>
              <button type="button" onClick={() => void purchase(pack.id)} className="mt-3 w-full rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">Acheter</button>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Historique des transactions</h2>
        {transactions.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucune transaction pour l&apos;instant.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
                <span className="capitalize">{tx.type}{tx.reason ? ` — ${tx.reason}` : ""}</span>
                <span className={tx.amount >= 0 ? "text-success" : "text-danger"}>{tx.amount >= 0 ? "+" : ""}{tx.amount}</span>
                <span className="text-xs text-foreground-muted">{new Date(tx.created_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InvoicesTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  const load = useCallback(async () => {
    try {
      setInvoices(await api.get<Invoice[]>(`/organizations/${orgId}/billing/invoices`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du chargement des factures");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function downloadPdf(invoiceId: string, number: string) {
    try {
      const token = window.localStorage.getItem("access_token");
      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${base}/organizations/${orgId}/billing/invoices/${invoiceId}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        credentials: "include",
      });
      if (!response.ok) throw new Error(`PDF download failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Échec du téléchargement du PDF de la facture");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {invoices.length === 0 ? (
        <p className="text-sm text-foreground-muted">Aucune facture pour l&apos;instant — les factures sont générées automatiquement une fois un vrai forfait payant actif.</p>
      ) : (
        invoices.map((inv) => (
          <div key={inv.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
            <span className="font-medium text-foreground">{inv.number}</span>
            <span className="text-xs uppercase text-foreground-muted">{inv.status}</span>
            <span className="text-foreground-muted">{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "—"}</span>
            <span className="font-medium text-foreground">{money(inv.total_cents, inv.currency)}</span>
            <button type="button" onClick={() => void downloadPdf(inv.id, inv.number)} className="text-xs font-medium text-accent hover:underline">Télécharger le PDF</button>
          </div>
        ))
      )}
    </div>
  );
}

function PaymentTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [portalLoading, setPortalLoading] = useState(false);

  async function openPortal() {
    setPortalLoading(true);
    try {
      const res = await api.post<{ url: string }>(`/organizations/${orgId}/billing/stripe/create-portal-session`);
      window.location.href = res.url;
    } catch (err) {
      if (err instanceof ApiError && err.status === 501) {
        onError("Le traitement des paiements n'est pas encore configuré sur ce déploiement (aucun compte Stripe connecté).");
      } else {
        onError(err instanceof ApiError ? String(err.detail) : "Échec de l'ouverture du portail de paiement");
      }
    } finally {
      setPortalLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">Moyen de paiement</h2>
        <p className="mt-1 text-sm text-foreground-muted">Gérez vos cartes enregistrées et votre historique de paiement via le portail sécurisé de Stripe.</p>
        <button type="button" onClick={() => void openPortal()} disabled={portalLoading} className="mt-3 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {portalLoading ? "Ouverture…" : "Gérer les moyens de paiement"}
        </button>
      </div>
    </div>
  );
}
