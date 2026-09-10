"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import GoogleTranslate from "@/components/GoogleTranslate";
import { useAuth, useRequireAuth } from "@/lib/auth";

const NAV_SECTIONS = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Overview", icon: "🏠" },
      { href: "/chat", label: "Chat", icon: "💬" },
      { href: "/dashboard/documents", label: "Documents", icon: "📄" },
      { href: "/dashboard/agents", label: "Agents", icon: "🤖" },
    ],
  },
  {
    label: "Developer",
    items: [
      { href: "/dashboard/settings/api-keys", label: "API keys", icon: "🔑" },
      { href: "/dashboard/settings/webhooks", label: "Webhooks", icon: "🔗" },
      { href: "/dashboard/api-docs", label: "API docs", icon: "📚" },
    ],
  },
  {
    label: "Widget & integrations",
    items: [
      { href: "/dashboard/settings/widget", label: "Widget", icon: "🧩" },
      { href: "/dashboard/settings/integrations", label: "Integrations", icon: "🔌" },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/dashboard/profile", label: "Profile", icon: "👤" },
      { href: "/dashboard/settings/organization", label: "Organization", icon: "⚙️" },
    ],
  },
  {
    label: "Platform",
    items: [
      { href: "/dashboard/billing", label: "Billing", icon: "💳" },
      { href: "/dashboard/security", label: "Security", icon: "🔒" },
      { href: "/admin", label: "Admin", icon: "🛠️" },
    ],
  },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const pathname = usePathname();

  if (loading || !user) {
    return <div className="flex h-screen items-center justify-center text-sm text-foreground-muted">Loading…</div>;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
        <div className="border-b border-border px-4 py-4">
          <Link href="/" className="text-sm font-semibold text-foreground">RAG SaaS Platform</Link>
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
                      className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm ${
                        active ? "bg-accent-soft font-medium text-accent-hover" : "text-foreground hover:bg-surface-muted"
                      }`}
                    >
                      <span aria-hidden="true">{item.icon}</span>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-border px-4 py-3">
          <p className="truncate text-xs text-foreground-muted">{user.email}</p>
          <button type="button" onClick={() => void logout()} className="mt-1 text-xs font-medium text-accent hover:underline">
            Log out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-end border-b border-border bg-surface px-6 py-3">
          <GoogleTranslate />
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
