// Real, already-shipped: a pack of IA credits included in every paid
// plan (api/models/admin.py's Plan.monthly_credits_included, granted
// monthly by api/tasks/billing.py's grant_monthly_plan_credits), spent
// per real LLM call (api/security/credit_packs.py's own real
// conversion table), plus the option to use your own provider key
// instead (BYOK, api/services/llm_byok.py) -- not aspirational copy.
const AI_ITEMS = [
  { title: "Crédits IA inclus", description: "Chaque forfait payant inclut un pack de crédits IA renouvelé chaque mois, sans configuration." },
  { title: "Facturation transparente", description: "1 crédit = 1 requête, 100 tokens en entrée ou 50 en sortie — visible en temps réel dans votre tableau de bord." },
  { title: "Crédits supplémentaires à la demande", description: "Besoin de plus ? Achetez un pack de crédits supplémentaire à tout moment, sans changer de forfait." },
  { title: "BYOK — utilisez votre propre clé", description: "Connectez votre propre clé API (Anthropic, OpenAI, Gemini, Mistral...) : vos appels sont alors facturés directement par votre fournisseur, jamais sur vos crédits." },
];

export default function AICreditsSection() {
  return (
    <section className="mt-28 rounded-2xl border border-border bg-surface p-8 sm:p-10">
      <h2 className="text-center text-2xl font-semibold text-foreground">IA incluse</h2>
      <p className="mx-auto mt-2 max-w-lg text-center text-sm text-foreground-muted">
        Un pack de crédits IA est inclus dans chaque forfait — ou utilisez votre propre clé API si vous préférez garder
        le contrôle total de votre facturation IA.
      </p>
      <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2">
        {AI_ITEMS.map((item) => (
          <div key={item.title} className="flex items-start gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">✓</span>
            <div>
              <p className="text-sm font-medium text-foreground">{item.title}</p>
              <p className="mt-0.5 text-xs text-foreground-muted">{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
