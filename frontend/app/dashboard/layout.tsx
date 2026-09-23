"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useAuth, useRequireAuth } from "@/lib/auth";
import LanguageSelector from "@/components/LanguageSelector";
import LoadingState from "@/components/LoadingState";

const NAV_SECTIONS = [
  {
    label: "Espace de travail",
    items: [
      { href: "/dashboard", label: "Vue d'ensemble" },
      { href: "/chat", label: "Conversation" },
      { href: "/dashboard/documents", label: "Documents" },
      { href: "/dashboard/agents", label: "Agents" },
      { href: "/dashboard/autonomous-agents", label: "Agents autonomes" },
      { href: "/dashboard/workflows", label: "Workflows" },
      { href: "/dashboard/fine-tuning", label: "Fine-tuning" },
      { href: "/dashboard/analytics", label: "Analytics" },
    ],
  },
  {
    label: "Développeur",
    items: [
      { href: "/dashboard/settings/api-keys", label: "Clés API" },
      { href: "/dashboard/settings/webhooks", label: "Webhooks" },
      { href: "/dashboard/settings/llm-config", label: "Configuration IA (BYOK)" },
      { href: "/dashboard/api-docs", label: "Documentation API" },
    ],
  },
  {
    label: "Widget et intégrations",
    items: [
      { href: "/dashboard/settings/widget", label: "Widget" },
      { href: "/dashboard/settings/integrations", label: "Intégrations" },
      { href: "/dashboard/marketplace", label: "Marketplace" },
    ],
  },
  {
    label: "Compte",
    items: [
      { href: "/dashboard/profile", label: "Profil" },
      { href: "/dashboard/settings/organization", label: "Organisation" },
    ],
  },
  {
    label: "Plateforme",
    items: [
      { href: "/dashboard/billing", label: "Facturation" },
      { href: "/dashboard/security", label: "Sécurité" },
      { href: "/admin", label: "Administration" },
    ],
  },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (loading || !user) {
    return <LoadingState onRetry={() => window.location.reload()} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 md:hidden" onClick={() => setSidebarOpen(false)} role="presentation" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-60 shrink-0 flex-col border-r border-border bg-surface transition-transform md:static md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0 shadow-md" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-4">
          <Link href="/" className="text-sm font-semibold text-foreground">RAG SaaS Platform</Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="Fermer le menu"
            className="rounded-lg p-1 text-foreground-muted hover:bg-surface-muted md:hidden"
          >
            ✕
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label} className="mb-5">
              <p className="mb-1.5 px-2 text-xs font-semibold uppercase tracking-wide text-foreground-muted">{section.label}</p>
              <div className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setSidebarOpen(false)}
                      className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm ${
                        active ? "bg-accent-soft font-medium text-accent-hover" : "text-foreground hover:bg-surface-muted"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-border px-4 py-3">
          <div className="mb-2">
            <LanguageSelector />
          </div>
          <p className="truncate text-xs text-foreground-muted">{user.email}</p>
          <button type="button" onClick={() => void logout()} className="mt-1 text-xs font-medium text-accent hover:underline">
            Se déconnecter
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-border bg-surface px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Ouvrir le menu"
            className="rounded-lg p-1.5 text-foreground-muted hover:bg-surface-muted"
          >
            ☰
          </button>
          <span className="text-sm font-semibold text-foreground">RAG SaaS Platform</span>
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
