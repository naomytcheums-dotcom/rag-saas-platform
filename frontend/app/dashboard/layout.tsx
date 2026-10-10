"use client";

import type { ReactNode } from "react";
import { BrandingApplier } from "@/components/BrandingApplier";
import AppShell, { type NavSection } from "@/components/dashboard/AppShell";
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
  const { t } = useTranslation();

  const sections: NavSection[] = [
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
        { href: "/dashboard/voice-settings", label: t("nav.voice_settings") },
        { href: "/dashboard/escalations", label: t("nav.escalations") },
        { href: "/dashboard/insights", label: t("nav.insights") },
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

  return (
    <>
      <BrandingApplier />
      <AppShell sections={sections} brand={<BrandLogo />} homeHref="/" >{children}</AppShell>
    </>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <BrandingProvider>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </BrandingProvider>
  );
}
