"use client";

import Link from "next/link";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

const QUICK_LINKS = [
  { href: "/chat", label: "Ouvrir la conversation", description: "Discutez avec vos agents" },
  { href: "/dashboard/documents", label: "Documents", description: "Envoyez et gérez vos connaissances" },
  { href: "/dashboard/agents", label: "Agents", description: "Configurez les prompts et les outils" },
  { href: "/dashboard/settings/api-keys", label: "Clés API", description: "Accès à l'API publique" },
  { href: "/dashboard/settings/webhooks", label: "Webhooks", description: "Livraison d'événements en temps réel" },
  { href: "/dashboard/settings/widget", label: "Widget", description: "Intégrez le chatbot sur votre site" },
  { href: "/dashboard/settings/integrations", label: "Intégrations", description: "Slack, Teams, Discord" },
  { href: "/dashboard/settings/organization", label: "Organisation", description: "Équipe et image de marque" },
];

export default function DashboardHome() {
  const { org, loading } = useCurrentOrg();

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">
        {loading ? "…" : org?.name ?? "Votre espace de travail"}
      </h1>
      <p className="mt-1 text-sm text-foreground-muted">Tout ce qu'il vous faut pour gérer votre plateforme RAG.</p>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {QUICK_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4 hover:border-accent hover:bg-accent-soft/40"
          >
            <div>
              <p className="text-sm font-medium text-foreground">{link.label}</p>
              <p className="text-xs text-foreground-muted">{link.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
