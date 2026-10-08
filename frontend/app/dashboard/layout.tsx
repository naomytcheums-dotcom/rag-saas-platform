"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { LogOut, Menu, X } from "lucide-react";
import { useAuth, useRequireAuth } from "@/lib/auth";
import QuickNav from "@/components/dashboard/QuickNav";
import { navIcon } from "@/components/dashboard/nav";
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
  return <span className={`text-[15px] font-semibold tracking-wide text-foreground ${className ?? ""}`}>{branding.brand_name ?? t("nav.brand_fallback")}</span>;
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
        { href: "/dashboard/eval/evolution", label: t("nav.evolution") },
        { href: "/dashboard/quality", label: t("nav.quality") },
        { href: "/dashboard/voice-agent", label: t("nav.voice_agent") },
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

  const quickItems = NAV_SECTIONS.flatMap((section) => section.items.map((item) => ({ ...item, section: section.label })));
  const displayName = user.email.split("@")[0];

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <BrandingApplier />
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 md:hidden" onClick={() => setSidebarOpen(false)} role="presentation" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[224px] shrink-0 flex-col border-r border-border bg-surface-muted transition-transform md:static md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0 shadow-md" : "-translate-x-full"
        }`}
      >
        <div className="flex h-[65px] shrink-0 items-center justify-between border-b border-border px-5">
          <Link href="/"><BrandLogo /></Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label={t("nav.close_menu")}
            className="rounded-md p-1 text-foreground-muted hover:bg-surface md:hidden"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3.5 py-5">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label} className="mb-5">
              <p className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-foreground-muted/80">{section.label}</p>
              <div className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const active = pathname === item.href;
                  const Icon = navIcon(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setSidebarOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] font-medium transition-colors ${
                        active ? "bg-accent text-white" : "text-foreground-muted hover:bg-surface hover:text-foreground"
                      }`}
                    >
                      <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
                      <span className="truncate">{item.label}</span>
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
          <button type="button" onClick={() => void logout()} className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline">
            <LogOut className="h-3.5 w-3.5" aria-hidden />
            {t("nav.logout")}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[65px] shrink-0 items-center gap-3 border-b border-border bg-surface px-4 md:px-8">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label={t("nav.open_menu")}
            className="rounded-md p-1.5 text-foreground-muted hover:bg-surface-muted md:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>
          <div className="md:hidden"><BrandLogo /></div>
          <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-6 md:justify-between">
            <div className="hidden min-w-0 flex-1 md:block">
              <QuickNav items={quickItems} placeholder={t("nav.search")} />
            </div>
            <div className="flex shrink-0 items-center gap-2.5">
              <span className="grid h-[30px] w-[30px] place-items-center rounded-full bg-accent-soft text-xs font-semibold uppercase text-accent" aria-hidden>
                {displayName.slice(0, 1)}
              </span>
              <span className="hidden max-w-[140px] truncate text-[13px] font-medium text-foreground sm:block">{displayName}</span>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-surface p-5 md:p-8">{children}</main>
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
