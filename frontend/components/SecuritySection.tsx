// Each item names a real, already-shipped feature (api/security/,
// api/models/) -- not aspirational marketing copy. Kept as a server
// component (no client-side state needed) so it doesn't add to the
// landing page's client JS bundle.
const SECURITY_ITEMS = [
  { title: "Chiffrement des données sensibles", description: "Champs sensibles chiffrés au repos, avec rotation des clés." },
  { title: "Authentification à deux facteurs", description: "TOTP et clés de sécurité WebAuthn/FIDO2, en plus du mot de passe." },
  { title: "Journal d'audit complet", description: "Chaque action sensible est tracée : qui, quand, depuis quelle adresse IP." },
  { title: "RGPD / CCPA", description: "Export et suppression de vos données à la demande, gestion du consentement intégrée." },
  { title: "Rôles et permissions granulaires", description: "Rôles personnalisés, permissions précises par ressource et par action." },
  { title: "Détection de vulnérabilités", description: "Analyses de sécurité réelles (dépendances, code, secrets, conteneurs) intégrées au produit." },
];

export default function SecuritySection() {
  return (
    <section className="mt-28 rounded-2xl border border-border bg-surface p-8 sm:p-10">
      <h2 className="text-center text-2xl font-semibold text-foreground">Sécurité et conformité</h2>
      <p className="mx-auto mt-2 max-w-lg text-center text-sm text-foreground-muted">
        Conçu pour des équipes qui manipulent des données sensibles, pas seulement des cas d'usage de démonstration.
      </p>
      <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {SECURITY_ITEMS.map((item) => (
          <div key={item.title} className="flex items-start gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-success-soft text-xs font-semibold text-success">✓</span>
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
