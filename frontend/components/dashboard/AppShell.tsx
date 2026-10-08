"use client";

import { LogOut, Menu, X, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useState, type ReactNode } from "react";
import LanguageSelector from "@/components/LanguageSelector";
import LoadingState from "@/components/LoadingState";
import { useAuth, useRequireAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import QuickNav from "./QuickNav";
import { navIcon } from "./nav";

export interface NavItem { href: string; label: string; icon?: LucideIcon }
export interface NavSection { label: string; items: NavItem[] }

/** `/admin?tab=Users` is active only for that exact tab; a plain path is active when it is the current path. */
function isActive(href: string, pathname: string, search: string): boolean {
  const [path, query] = href.split("?");
  if (path !== pathname) return false;
  if (!query) return true;
  return new URLSearchParams(search).get("tab") === new URLSearchParams(query).get("tab") || (!new URLSearchParams(search).get("tab") && new URLSearchParams(query).get("tab") === "Overview");
}

function Shell({ sections, brand, homeHref, children }: { sections: NavSection[]; brand: ReactNode; homeHref: string; children: ReactNode }) {
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const { t } = useTranslation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (loading || !user) {
    return <LoadingState onRetry={() => window.location.reload()} />;
  }

  const quickItems = sections.flatMap((section) => section.items.map((item) => ({ ...item, section: section.label })));
  const displayName = user.email.split("@")[0];

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {sidebarOpen && <div className="fixed inset-0 z-40 bg-black/20 md:hidden" onClick={() => setSidebarOpen(false)} role="presentation" />}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[224px] shrink-0 flex-col border-r border-border bg-surface-muted transition-transform md:static md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0 shadow-md" : "-translate-x-full"
        }`}
      >
        <div className="flex h-[65px] shrink-0 items-center justify-between border-b border-border px-5">
          <Link href={homeHref}>{brand}</Link>
          <button type="button" onClick={() => setSidebarOpen(false)} aria-label={t("nav.close_menu")} className="rounded-md p-1 text-foreground-muted hover:bg-surface md:hidden">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3.5 py-5">
          {sections.map((section) => (
            <div key={section.label} className="mb-5">
              <p className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-foreground-muted/80">{section.label}</p>
              <div className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const active = isActive(item.href, pathname, search);
                  const Icon = item.icon ?? navIcon(item.href);
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
          <div className="mb-2"><LanguageSelector /></div>
          <p className="truncate text-xs text-foreground-muted">{user.email}</p>
          <button type="button" onClick={() => void logout()} className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline">
            <LogOut className="h-3.5 w-3.5" aria-hidden />
            {t("nav.logout")}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[65px] shrink-0 items-center gap-3 border-b border-border bg-surface px-4 md:px-8">
          <button type="button" onClick={() => setSidebarOpen(true)} aria-label={t("nav.open_menu")} className="rounded-md p-1.5 text-foreground-muted hover:bg-surface-muted md:hidden">
            <Menu className="h-5 w-5" aria-hidden />
          </button>
          <div className="md:hidden">{brand}</div>
          <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-6 md:justify-between">
            <div className="hidden min-w-0 flex-1 md:block">
              <QuickNav items={quickItems} placeholder={t("nav.search")} />
            </div>
            <div className="flex shrink-0 items-center gap-2.5">
              <span className="grid h-[30px] w-[30px] place-items-center rounded-full bg-accent-soft text-xs font-semibold uppercase text-accent" aria-hidden>{displayName.slice(0, 1)}</span>
              <span className="hidden max-w-[140px] truncate text-[13px] font-medium text-foreground sm:block">{displayName}</span>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-surface p-5 md:p-8">{children}</main>
      </div>
    </div>
  );
}

/** The Designo-style application frame (grey sidebar with icons, header with search, white content) shared by the customer dashboard and the super-admin area. */
export default function AppShell(props: { sections: NavSection[]; brand: ReactNode; homeHref: string; children: ReactNode }) {
  return (
    <Suspense fallback={<LoadingState onRetry={() => window.location.reload()} />}>
      <Shell {...props} />
    </Suspense>
  );
}
