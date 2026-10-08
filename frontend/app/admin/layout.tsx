"use client";

import { Activity, ArrowLeft, Bell, Building2, ChartColumn, CreditCard, LayoutDashboard, ScrollText, Users } from "lucide-react";
import type { ReactNode } from "react";
import AppShell, { type NavSection } from "@/components/dashboard/AppShell";
import { useTranslation } from "@/lib/i18n";

/** Super-admin area: the same frame as the customer dashboard, with one entry per administration tab (the page reads `?tab=`). */
export default function AdminLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const sections: NavSection[] = [
    {
      label: t("admin.title"),
      items: [
        { href: "/admin?tab=Overview", label: t("admin.tab_overview"), icon: LayoutDashboard },
        { href: "/admin?tab=Business", label: t("analytics.tab_business"), icon: ChartColumn },
        { href: "/admin?tab=Organizations", label: t("admin.tab_orgs"), icon: Building2 },
        { href: "/admin?tab=Users", label: t("admin.tab_users"), icon: Users },
        { href: "/admin?tab=Subscriptions", label: t("admin.tab_subscriptions"), icon: CreditCard },
        { href: "/admin?tab=Monitoring", label: t("admin.tab_monitoring"), icon: Activity },
        { href: "/admin?tab=Logs", label: t("admin.tab_logs"), icon: ScrollText },
        { href: "/admin?tab=Alerting", label: t("admin.tab_alerting"), icon: Bell },
      ],
    },
    { label: t("nav.section.platform"), items: [{ href: "/dashboard", label: t("nav.dashboard"), icon: ArrowLeft }] },
  ];
  return (
    <AppShell sections={sections} homeHref="/admin" brand={<span className="text-[15px] font-semibold tracking-wide text-foreground">{t("admin.title")}</span>}>
      {children}
    </AppShell>
  );
}
