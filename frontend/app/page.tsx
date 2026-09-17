import Link from "next/link";
import AICreditsSection from "@/components/AICreditsSection";
import FAQSection from "@/components/FAQSection";
import PricingSection from "@/components/PricingSection";
import SecuritySection from "@/components/SecuritySection";

const FEATURES = [
  { title: "Chat propulsé par le RAG", description: "Des réponses ancrées dans vos propres documents, avec de vraies citations.", href: "/chat" },
  { title: "Agents IA personnalisés", description: "Configurez un prompt, des garde-fous et les outils autorisés selon vos besoins.", href: "/dashboard/agents" },
  { title: "Widget embarquable", description: "Une seule balise script à ajouter sur n'importe quel site.", href: "/dashboard/settings/widget" },
  { title: "Slack, Teams, Discord", description: "Vos agents directement dans les outils que votre équipe utilise déjà.", href: "/dashboard/settings/integrations" },
  { title: "API publique", description: "Construisez sur votre propre base de connaissances avec une vraie API REST.", href: "/dashboard/settings/api-keys" },
  { title: "Webhooks", description: "Des événements en temps réel livrés directement à vos systèmes.", href: "/dashboard/settings/webhooks" },
];

const STEPS = [
  { number: "1", title: "Téléchargez vos documents", description: "PDF, docs, tableurs, sites web — tout ce que votre équipe possède déjà." },
  { number: "2", title: "Configurez un agent", description: "Choisissez un prompt, des garde-fous et les outils qu'il peut utiliser." },
  { number: "3", title: "Déployez partout", description: "Votre site web, Slack, Teams, Discord, ou votre propre application via l'API." },
];

const FOOTER_COLUMNS = [
  { title: "Produit", links: [{ label: "Démo de chat", href: "/chat" }, { label: "Tarifs", href: "/#pricing" }, { label: "Widget", href: "/dashboard/settings/widget" }] },
  { title: "Développeurs", links: [{ label: "Clés API", href: "/dashboard/settings/api-keys" }, { label: "Webhooks", href: "/dashboard/settings/webhooks" }, { label: "Référence API", href: "http://localhost:8000/docs" }] },
  { title: "Compte", links: [{ label: "Connexion", href: "/login" }, { label: "Inscription", href: "/register" }] },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-orange-50 to-white">
      {/* Pas de barre de navigation fixe, ni de barre de progression --
          seulement le défilement naturel de la page, comme demandé. Deux
          liens discrets en haut à droite, pas une vraie barre. */}
      <div className="flex justify-end gap-4 px-6 pt-5 text-sm">
        <Link href="/login" className="text-foreground-muted transition-colors hover:text-foreground">Connexion</Link>
        <Link href="/register" className="font-medium text-accent transition-colors hover:text-accent-hover">Inscription</Link>
      </div>

      <main className="mx-auto max-w-5xl px-6 pb-20 pt-8 text-center">
        <h1 className="text-4xl font-bold text-foreground sm:text-5xl">
          Créez un assistant RAG<br />pour votre entreprise
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-foreground-muted">
          Téléchargez vos documents, configurez un agent et déployez un véritable chatbot — sur votre site web, dans
          Slack ou via votre propre application.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/register" className="rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white transition-transform hover:-translate-y-0.5 hover:bg-accent-hover">Commencer gratuitement</Link>
          <Link href="/chat" className="rounded-lg border border-border-strong px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-surface-muted">Voir la démo</Link>
        </div>

        {/* Fonctionnalités */}
        <div className="mt-20 grid grid-cols-1 gap-5 text-left sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Link
              key={feature.title}
              href={feature.href}
              className="group rounded-xl border border-border bg-surface p-5 transition-all duration-200 hover:-translate-y-1 hover:border-accent hover:shadow-lg"
            >
              <h3 className="text-sm font-semibold text-foreground group-hover:text-accent-hover">{feature.title}</h3>
              <p className="mt-1 text-sm text-foreground-muted">{feature.description}</p>
              <span className="mt-2 inline-block text-xs font-medium text-accent opacity-0 transition-opacity group-hover:opacity-100">
                Explorer →
              </span>
            </Link>
          ))}
        </div>

        {/* Comment ça marche */}
        <section className="mt-28">
          <h2 className="text-2xl font-semibold text-foreground">Comment ça marche</h2>
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.number} className="rounded-xl border border-border bg-surface p-6 text-left transition-transform duration-200 hover:-translate-y-1">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white">{step.number}</span>
                <h3 className="mt-3 text-sm font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1 text-sm text-foreground-muted">{step.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Statistiques */}
        <section className="mt-28 rounded-2xl border border-border bg-surface p-10">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div>
              <p className="text-3xl font-bold text-accent">6</p>
              <p className="mt-1 text-sm text-foreground-muted">Langues prises en charge</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-accent">3</p>
              <p className="mt-1 text-sm text-foreground-muted">Intégrations de plateformes de chat</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-accent">3800+</p>
              <p className="mt-1 text-sm text-foreground-muted">Tests automatisés</p>
            </div>
          </div>
        </section>

        <AICreditsSection />
        <SecuritySection />
        <PricingSection />
        <FAQSection />

        {/* Appel à l'action */}
        <section className="mt-28 rounded-2xl bg-gradient-to-r from-accent to-orange-400 p-10 text-white">
          <h2 className="text-2xl font-semibold">Prêt à créer votre assistant ?</h2>
          <p className="mt-2 text-sm text-white/90">Créez votre organisation en moins d'une minute — aucune carte bancaire requise.</p>
          <Link href="/register" className="mt-5 inline-block rounded-lg bg-white px-6 py-3 text-sm font-medium text-accent-hover transition-transform hover:-translate-y-0.5">
            Commencer gratuitement
          </Link>
        </section>
      </main>

      <footer className="border-t border-border bg-surface px-6 py-12">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <span className="text-sm font-semibold text-foreground">RAG SaaS Platform</span>
            <p className="mt-2 text-xs text-foreground-muted">Créez et déployez des assistants IA ancrés dans vos propres données.</p>
          </div>
          {FOOTER_COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">{column.title}</p>
              <div className="mt-2 flex flex-col gap-1.5">
                {column.links.map((link) => (
                  <Link key={link.label} href={link.href} className="text-sm text-foreground-muted transition-colors hover:text-accent">
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
        <p className="mx-auto mt-10 max-w-5xl text-xs text-foreground-muted">
          © {new Date().getFullYear()} RAG SaaS Platform. Tous droits réservés.
        </p>
      </footer>
    </div>
  );
}
