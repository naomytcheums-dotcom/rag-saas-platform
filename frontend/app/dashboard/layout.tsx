"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useAuth, useRequireAuth } from "@/lib/auth";
import LanguageSelector from "@/components/LanguageSelector";
import LoadingState from "@/components/LoadingState";
import { BrandingApplier } from "@/components/BrandingApplier";
import { BrandingProvider, useBranding } from "@/lib/branding-context";
import { useTranslation } from "@/lib/i18n";

function BrandLogo({ className }: { className?: string }) {
  const { branding } = useBranding();
  const { t } = useTranslation();
  if (branding.logo_url) {
    // eslint-disable-next-line @next/next/no-img-element -- an organization's own uploaded logo is an arbitrary external/S3 URL, not a static local asset next/image can optimize
    return <img src={branding.logo_url} alt={branding.brand_name ?? ""} className={`max-h-8 max-w-[140px] object-contain ${className ?? ""}`} />;
  }
  return <span className={`text-sm font-semibold text-foreground ${className ?? ""}`}>{branding.brand_name ?? t("nav.brand_fallback")}</span>;
}

function DashboardLayoutInner({ children }: { children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const pathname = usePathname();
  const { t } = useTranslation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const NAV_SECTIONS = [
    {
      label: t("nav.section.workspace"),
      items: [
        { href: "/dashboard", label: t("nav.dashboard") },
        { href: "/chat", label: t("nav.chat") },
        { href: "/dashboard/documents", label: t("nav.documents") },
        { href: "/dashboard/agents", label: t("nav.agents") },
        { href: "/dashboard/autonomous-agents", label: t("nav.autonomous_agents") },
        { href: "/dashboard/workflows", label: t("nav.workflows") },
        { href: "/dashboard/fine-tuning", label: t("nav.fine_tuning") },
        { href: "/dashboard/analytics", label: t("nav.analytics") },
        { href: "/dashboard/eval", label: t("nav.eval") },
      ],
    },
    {
      label: t("nav.section.developer"),
      items: [
        { href: "/dashboard/settings/api-keys", label: t("nav.api_keys") },
        { href: "/dashboard/settings/webhooks", label: t("nav.webhooks") },
        { href: "/dashboard/settings/llm-config", label: t("nav.llm_config") },
        { href: "/dashboard/api-docs", label: t("nav.api_docs") },
      ],
    },
    {
      label: t("nav.section.widget"),
      items: [
        { href: "/dashboard/settings/widget", label: t("nav.widget") },
        { href: "/dashboard/settings/integrations", label: t("nav.integrations") },
        { href: "/dashboard/marketplace", label: t("nav.marketplace") },
      ],
    },
    {
      label: t("nav.section.account"),
      items: [
        { href: "/dashboard/profile", label: t("nav.profile") },
        { href: "/dashboard/settings/organization", label: t("nav.organization") },
      ],
    },
    {
      label: t("nav.section.platform"),
      items: [
        { href: "/dashboard/billing", label: t("nav.billing") },
        { href: "/dashboard/security", label: t("nav.security") },
        { href: "/admin", label: t("nav.admin") },
      ],
    },
  ];

  if (loading || !user) {
    return <LoadingState onRetry={() => window.location.reload()} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <BrandingApplier />
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 md:hidden" onClick={() => setSidebarOpen(false)} role="presentation" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-60 shrink-0 flex-col border-r border-border bg-surface transition-transform md:static md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0 shadow-md" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-4">
          <Link href="/"><BrandLogo /></Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label={t("nav.close_menu")}
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
            {t("nav.logout")}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-border bg-surface px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label={t("nav.open_menu")}
            className="rounded-lg p-1.5 text-foreground-muted hover:bg-surface-muted"
          >
            ☰
          </button>
          <BrandLogo />
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <BrandingProvider>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </BrandingProvider>
  );
}
