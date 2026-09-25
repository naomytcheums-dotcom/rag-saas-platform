"use client";

import Link from "next/link";
import AICreditsSection from "@/components/AICreditsSection";
import FAQSection from "@/components/FAQSection";
import PricingSection from "@/components/PricingSection";
import SecuritySection from "@/components/SecuritySection";
import { useTranslation } from "@/lib/i18n";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LandingPage() {
  const { t } = useTranslation();

  const FEATURES = [
    { title: t("landing.features.chat.title"), description: t("landing.features.chat.desc"), href: "/chat" },
    { title: t("landing.features.agents.title"), description: t("landing.features.agents.desc"), href: "/dashboard/agents" },
    { title: t("landing.features.widget.title"), description: t("landing.features.widget.desc"), href: "/dashboard/settings/widget" },
    { title: t("landing.features.integrations.title"), description: t("landing.features.integrations.desc"), href: "/dashboard/settings/integrations" },
    { title: t("landing.features.api.title"), description: t("landing.features.api.desc"), href: "/dashboard/settings/api-keys" },
    { title: t("landing.features.webhooks.title"), description: t("landing.features.webhooks.desc"), href: "/dashboard/settings/webhooks" },
  ];

  const STEPS = [
    { number: "1", title: t("landing.steps.1.title"), description: t("landing.steps.1.desc") },
    { number: "2", title: t("landing.steps.2.title"), description: t("landing.steps.2.desc") },
    { number: "3", title: t("landing.steps.3.title"), description: t("landing.steps.3.desc") },
  ];

  const FOOTER_COLUMNS = [
    { title: t("landing.footer.product"), links: [
      { label: t("landing.footer.chat_demo"), href: "/chat" },
      { label: t("landing.footer.pricing"), href: "/#pricing" },
      { label: t("landing.footer.widget"), href: "/dashboard/settings/widget" },
    ] },
    { title: t("landing.footer.developers"), links: [
      { label: t("landing.footer.api_keys"), href: "/dashboard/settings/api-keys" },
      { label: t("landing.footer.webhooks"), href: "/dashboard/settings/webhooks" },
      { label: t("landing.footer.api_ref"), href: `${API_BASE_URL}/docs` },
    ] },
    { title: t("landing.footer.account"), links: [
      { label: t("landing.login"), href: "/login" },
      { label: t("landing.register"), href: "/register" },
    ] },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-orange-50 to-white">
      <div className="flex justify-end gap-4 px-6 pt-5 text-sm">
        <Link href="/login" className="text-foreground-muted transition-colors hover:text-foreground">{t("landing.login")}</Link>
        <Link href="/register" className="font-medium text-accent transition-colors hover:text-accent-hover">{t("landing.register")}</Link>
      </div>

      <main className="mx-auto max-w-5xl px-6 pb-20 pt-8 text-center">
        <h1 className="text-4xl font-bold text-foreground sm:text-5xl">
          {t("landing.hero.title_line1")}<br />{t("landing.hero.title_line2")}
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-foreground-muted">
          {t("landing.hero.subtitle")}
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/register" className="rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white transition-transform hover:-translate-y-0.5 hover:bg-accent-hover">{t("landing.cta.start")}</Link>
          <Link href="/chat" className="rounded-lg border border-border-strong px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-surface-muted">{t("landing.cta.demo")}</Link>
        </div>

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
                {t("landing.features.explore")} →
              </span>
            </Link>
          ))}
        </div>

        <section className="mt-28">
          <h2 className="text-2xl font-semibold text-foreground">{t("landing.steps.title")}</h2>
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

        <section className="mt-28 rounded-2xl border border-border bg-surface p-10">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div>
              <p className="text-3xl font-bold text-accent">6</p>
              <p className="mt-1 text-sm text-foreground-muted">{t("landing.stats.languages")}</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-accent">3</p>
              <p className="mt-1 text-sm text-foreground-muted">{t("landing.stats.integrations")}</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-accent">3800+</p>
              <p className="mt-1 text-sm text-foreground-muted">{t("landing.stats.tests")}</p>
            </div>
          </div>
        </section>

        <AICreditsSection />
        <SecuritySection />
        <PricingSection />
        <FAQSection />

        <section className="mt-28 rounded-2xl bg-gradient-to-r from-accent to-orange-400 p-10 text-white">
          <h2 className="text-2xl font-semibold">{t("landing.cta_bottom.title")}</h2>
          <p className="mt-2 text-sm text-white/90">{t("landing.cta_bottom.subtitle")}</p>
          <Link href="/register" className="mt-5 inline-block rounded-lg bg-white px-6 py-3 text-sm font-medium text-accent-hover transition-transform hover:-translate-y-0.5">
            {t("landing.cta.start")}
          </Link>
        </section>
      </main>

      <footer className="border-t border-border bg-surface px-6 py-12">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <span className="text-sm font-semibold text-foreground">RAG SaaS Platform</span>
            <p className="mt-2 text-xs text-foreground-muted">{t("landing.footer.tagline")}</p>
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
          © {new Date().getFullYear()} RAG SaaS Platform. {t("landing.footer.copyright")}
        </p>
      </footer>
    </div>
  );
}
