"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

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
}

function money(cents: number): string {
  if (cents === 0) return "Gratuit";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: 0 }).format(cents / 100);
}

// Real /billing/plans data, the same public, unauthenticated endpoint
// api/dashboard/billing/page.tsx's own PlansTab reads once logged in --
// no separate marketing-only price list to keep in sync by hand, and
// nothing invented: what a visitor sees here is exactly what they'd be
// charged after signing up.
export default function PricingSection() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.get<Plan[]>("/billing/plans").then(setPlans).catch(() => setError(true));
  }, []);

  if (error) return null;

  return (
    <section id="pricing" className="mt-28">
      <h2 className="text-center text-2xl font-semibold text-foreground">Tarifs</h2>
      <p className="mx-auto mt-2 max-w-lg text-center text-sm text-foreground-muted">
        Commencez gratuitement, passez à l&apos;échelle quand vous en avez besoin. Aucune carte bancaire requise pour démarrer.
      </p>

      {!plans ? (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-64 animate-pulse rounded-xl border border-border bg-surface" />
          ))}
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => {
            const highlighted = plan.key === "pro";
            return (
              <div
                key={plan.id}
                className={`flex flex-col rounded-xl border p-6 text-left ${highlighted ? "border-accent bg-accent-soft/30 shadow-lg" : "border-border bg-surface"}`}
              >
                {highlighted && (
                  <span className="mb-2 self-start rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-white">Le plus populaire</span>
                )}
                <h3 className="text-sm font-semibold text-foreground">{plan.name}</h3>
                <p className="mt-2 text-2xl font-bold text-foreground">
                  {money(plan.monthly_price_cents)}
                  {plan.monthly_price_cents > 0 && <span className="text-sm font-normal text-foreground-muted"> / mois</span>}
                </p>
                <ul className="mt-4 flex flex-1 flex-col gap-2 text-xs text-foreground-muted">
                  <li>{plan.max_documents ?? "Illimité"} documents</li>
                  <li>{plan.max_agents ?? "Illimité"} agents</li>
                  <li>{plan.max_members ?? "Illimité"} membres</li>
                  {plan.priority_support && <li className="text-foreground">Support prioritaire</li>}
                  {plan.advanced_features && <li className="text-foreground">Fonctionnalités avancées</li>}
                  {plan.sla && <li className="text-foreground">SLA</li>}
                </ul>
                <Link
                  href="/register"
                  className={`mt-5 rounded-lg px-4 py-2 text-center text-sm font-medium transition-colors ${
                    highlighted ? "bg-accent text-white hover:bg-accent-hover" : "border border-border-strong text-foreground hover:bg-surface-muted"
                  }`}
                >
                  Choisir {plan.name}
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
