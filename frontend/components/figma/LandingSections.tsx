/* eslint-disable @next/next/no-img-element -- icons exported from the Figma reference are plain SVG files */
"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { formatEuroCents, useDisplayCurrency } from "@/lib/currency";
import { useTranslation } from "@/lib/i18n";
import Reveal from "./Reveal";
import SocialLinks from "./SocialLinks";
import { FaqShapesLayer, ParticlesLayer, SwooshLayer } from "./artwork";

const ORANGE = "#ff541f";
const TICK = "/landing/figma/imgVuesaxLinearTickCircle.svg";
const TICK_FILLED = "/landing/figma/imgVuesaxLinearTickCircle1.svg";

/** Shows a window of the Figma artwork (drawn on a 1440 x 5610 page) starting at `y`, so each section keeps the exact decoration of the mock-up. */
export function ArtWindow({ y, height, children }: { y: number; height: number; children: ReactNode }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 -z-0 overflow-hidden" style={{ height }} aria-hidden>
      <div className="stage-fade absolute left-1/2 w-[1440px] -translate-x-1/2" style={{ top: -y, height: 5610 }}>{children}</div>
    </div>
  );
}

function Heading({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <Reveal><h2 className={`text-4xl font-bold leading-[1.1] text-white md:text-[56px] ${className}`}>{children}</h2></Reveal>;
}

function Accent({ text }: { text: string }) {
  const words = text.split(" ");
  const head = words.slice(0, -2).join(" ");
  return <>{head ? `${head} ` : ""}<span style={{ color: ORANGE }}>{words.slice(-2).join(" ")}</span></>;
}

/* ------------------------------------------------------------------ features (bento) */

const BENTO = [
  { key: "chat", href: "/chat", span: "md:col-span-5", glow: true },
  { key: "agents", href: "/dashboard/agents", span: "md:col-span-7", glow: false },
  { key: "autonomous", href: "/dashboard/autonomous-agents", span: "md:col-span-7", glow: false },
  { key: "workflows", href: "/dashboard/workflows", span: "md:col-span-5", glow: true },
  { key: "eval", href: "/dashboard/eval", span: "md:col-span-5", glow: true },
  { key: "voice", href: "/dashboard/voice-agent", span: "md:col-span-7", glow: false },
];

const MORE = [
  ["finetune", "/dashboard/fine-tuning"], ["analytics", "/dashboard/analytics"], ["integrations", "/dashboard/settings/integrations"],
  ["api", "/dashboard/settings/api-keys"], ["widget", "/dashboard/settings/widget"], ["webhooks", "/dashboard/settings/webhooks"],
  ["abtests", "/dashboard/ab-tests"], ["media", "/dashboard/media"], ["marketplace", "/dashboard/marketplace"], ["whitelabel", "/dashboard/settings/white-label"],
] as const;

export function FeaturesSection() {
  const { t } = useTranslation();
  return (
    <section id="features" className="relative px-6 pb-24 pt-28">
      <ArtWindow y={1400} height={1400}><ParticlesLayer /></ArtWindow>
      <div className="relative mx-auto max-w-[1200px]">
        <Heading className="max-w-[860px]"><Accent text={t("landing.features.title")} /></Heading>
        <p className="mt-5 max-w-[661px] text-[18px] leading-[21.6px] text-white/85">{t("landing.features.subtitle")}</p>
        <div className="mt-14 grid grid-cols-1 gap-5 md:grid-cols-12">
          {BENTO.map(({ key, href, span, glow }, index) => (
            <Reveal key={key} className={span} delay={(index % 2) * 120}>
            <Link
              href={href}
              className="group relative block h-[199px] overflow-hidden rounded-[20px] border-[1.25px] border-[rgba(255,84,31,0.2)] bg-[rgba(39,40,41,0.7)] transition-all duration-300 hover:-translate-y-1.5 hover:border-[rgba(255,84,31,0.6)] hover:shadow-[0_18px_40px_rgba(255,84,31,0.18)]"
            >
              {glow && <span aria-hidden className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-[rgba(255,84,31,0.38)]" />}
              <p className="absolute left-5 top-[19px] w-[min(380px,72%)] text-[18px] leading-[19.2px] text-[rgba(217,217,217,0.85)]">{t(`landing.features.${key}.desc`)}</p>
              <span className="absolute right-[10px] top-[13px] grid h-[50px] w-[50px] place-items-center rounded-full bg-[#ff541f] transition-transform group-hover:scale-105">
                <ArrowRight className="h-6 w-6 -rotate-45 text-white" aria-hidden />
              </span>
              <p className="absolute bottom-[26px] left-5 whitespace-nowrap text-[28px] leading-[40.8px] text-white md:text-[34px]">{t(`landing.features.${key}.title`)}</p>
            </Link>
            </Reveal>
          ))}
        </div>
        <ul className="mt-10 flex flex-wrap gap-3">
          {MORE.map(([key, href]) => (
            <li key={key}>
              <Link href={href} title={t(`landing.features.${key}.desc`)} className="inline-block rounded-[10px] border border-[rgba(252,252,252,0.23)] px-5 py-2.5 text-[16px] text-white transition-colors hover:border-[#ff541f] hover:text-[#ff541f]">
                {t(`landing.features.${key}.title`)}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ AI credits & security (same card language as the bento) */

function InfoCards({ id, title, subtitle, items, columns }: { id?: string; title: string; subtitle: string; items: { title: string; description: string }[]; columns: string }) {
  return (
    <section id={id} className="relative px-6 py-20">
      <div className="mx-auto max-w-[1200px]">
        <Heading className="text-center">{title}</Heading>
        <p className="mx-auto mt-5 max-w-[780px] text-center text-[20px] leading-[28px] text-[#d9d9d9]">{subtitle}</p>
        <div className={`mt-14 grid grid-cols-1 gap-5 ${columns}`}>
          {items.map((item, index) => (
            <Reveal key={item.title} delay={(index % 3) * 100}>
            <div className="flex h-full items-start gap-4 rounded-[20px] border-[1.25px] border-[rgba(255,84,31,0.2)] bg-[rgba(39,40,41,0.7)] p-6 transition-all duration-300 hover:-translate-y-1 hover:border-[rgba(255,84,31,0.5)]">
              <img src={TICK_FILLED} alt="" className="mt-0.5 h-6 w-6 shrink-0" />
              <div>
                <p className="text-[20px] text-white">{item.title}</p>
                <p className="mt-2 text-[16px] leading-6 text-white/75">{item.description}</p>
              </div>
            </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function AiCreditsSection() {
  const { t } = useTranslation();
  const items = [1, 2, 3, 4].map((n) => ({ title: t(`lp.credits.${n}.title`), description: t(`lp.credits.${n}.desc`) }));
  return <InfoCards title={t("lp.credits.title")} subtitle={t("lp.credits.subtitle")} items={items} columns="md:grid-cols-2" />;
}

export function SecuritySection() {
  const { t } = useTranslation();
  const items = [1, 2, 3, 4, 5, 6].map((n) => ({ title: t(`lp.security.${n}.title`), description: t(`lp.security.${n}.desc`) }));
  return <InfoCards title={t("lp.security.title")} subtitle={t("lp.security.subtitle")} items={items} columns="md:grid-cols-2 lg:grid-cols-3" />;
}

/* ------------------------------------------------------------------ pricing */

interface Plan {
  id: string;
  key: string;
  name: string;
  monthly_price_cents: number;
  yearly_price_cents: number;
  max_documents: number | null;
  max_agents: number | null;
  max_members: number | null;
  priority_support: boolean;
  advanced_features: boolean;
  sla: boolean;
}

function yearlySavingPercent(plan: Plan): number {
  if (!plan.monthly_price_cents || !plan.yearly_price_cents) return 0;
  return Math.max(0, Math.round((1 - plan.yearly_price_cents / (plan.monthly_price_cents * 12)) * 100));
}

function GlowButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="relative inline-block rounded-[10px]">
      <span aria-hidden className="glow-pulse absolute -inset-[10px] rounded-[10px] bg-[#ff541f] opacity-20 mix-blend-screen blur-[10px]" />
      <span className="relative flex items-center gap-3 rounded-[10px] border border-white bg-black/50 px-5 py-2.5 text-[18px] text-white backdrop-blur-[10px]">
        {children}
        <img src="/landing/figma/imgChevronRight.svg" alt="" className="h-6 w-6" />
      </span>
    </Link>
  );
}

// Real /billing/plans data (the same public endpoint the billing page reads): nothing invented, what a visitor sees is what they are charged.
export function PricingSection() {
  const { t, language } = useTranslation();
  const currency = useDisplayCurrency();
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState(false);
  const [yearly, setYearly] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    api.get<Plan[]>("/billing/plans").then((data) => { setError(false); setPlans(data); }).catch(() => setError(true));
  }, [attempt]);

  const hasYearly = (plans ?? []).some((plan) => plan.yearly_price_cents > 0);

  return (
    <section id="pricing" className="relative px-6 py-24">
      <ArtWindow y={2640} height={1100}><SwooshLayer /></ArtWindow>
      <div className="relative mx-auto flex max-w-[1280px] flex-col items-center gap-[45px]">
        <div className="flex max-w-[780px] flex-col items-center gap-5 text-center">
          <Heading>{t("lp.pricing.title1")}<br />{t("lp.pricing.title2")}</Heading>
          <p className="text-[20px] leading-6 text-[#d9d9d9]">{t("lp.pricing.subtitle")}</p>
        </div>

        {hasYearly && (
          <div className="flex rounded-[333px] bg-white/10 p-[10px]" role="group" aria-label={t("lp.pricing.period")}>
            {[{ label: t("lp.pricing.monthly"), value: false }, { label: t("lp.pricing.yearly"), value: true }].map((option) => (
              <button
                key={option.label}
                type="button"
                onClick={() => setYearly(option.value)}
                aria-pressed={yearly === option.value}
                className={`rounded-[20px] px-8 py-[5px] text-[16px] leading-6 ${yearly === option.value ? "bg-white/20 text-white" : "text-[#919191]"}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}

        {error && !plans ? (
          <div className="rounded-[20px] border border-white/10 bg-[#1b1b1c] p-8 text-center">
            <p className="text-[16px] text-white/75">{t("lp.pricing.unavailable")}</p>
            <button type="button" onClick={() => setAttempt((value) => value + 1)} className="mt-4 rounded-[10px] bg-[#ff541f] px-[35px] py-[12px] text-[18px] font-bold text-white">{t("lp.pricing.retry")}</button>
          </div>
        ) : !plans ? (
          <div className="grid w-full grid-cols-1 gap-5 md:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="h-80 animate-pulse rounded-[20px] bg-[#1b1b1c]" />)}</div>
        ) : (
          <div className="grid w-full grid-cols-1 items-stretch gap-6 md:grid-cols-2 xl:grid-cols-4">
            {plans.map((plan, index) => {
              const highlighted = plan.key === "pro";
              const showYearly = yearly && plan.yearly_price_cents > 0;
              const saving = yearlySavingPercent(plan);
              const lines = [
                t("lp.pricing.documents", { n: plan.max_documents ?? t("lp.pricing.unlimited") }),
                t("lp.pricing.agents", { n: plan.max_agents ?? t("lp.pricing.unlimited") }),
                t("lp.pricing.members", { n: plan.max_members ?? t("lp.pricing.unlimited") }),
                ...(plan.priority_support ? [t("lp.pricing.priority")] : []),
                ...(plan.advanced_features ? [t("lp.pricing.advanced")] : []),
                ...(plan.sla ? [t("lp.pricing.sla")] : []),
              ];
              const cents = showYearly ? plan.yearly_price_cents : plan.monthly_price_cents;
              return (
                <Reveal key={plan.id} className="flex" delay={index * 120}>
                <div
                  className={`flex w-full flex-col items-center gap-[30px] rounded-[20px] bg-[#1b1b1c] px-6 py-8 transition-transform duration-300 hover:-translate-y-1.5 ${
                    highlighted ? "relative z-10 border-[3px] border-[#ff7044]" : "border border-white/10"
                  }`}>
                  <div className="flex w-full flex-col items-start gap-5">
                    <p className={highlighted ? "text-[30px] text-[#ff541f]" : "text-[18px] text-white"}>{plan.name}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="whitespace-nowrap text-[32px] font-bold tracking-[-1px] text-white">
                        {cents === 0 ? t("lp.pricing.free") : formatEuroCents(cents, currency, language)}
                      </span>
                      {plan.monthly_price_cents > 0 && <span className="text-[16px] text-white/75">{showYearly ? t("lp.pricing.per_year") : t("lp.pricing.per_month")}</span>}
                      {showYearly && saving > 0 && <span className="rounded-[24px] bg-[#ff541f] px-2 py-[5px] text-[12px] leading-[14px] text-white">-{saving}%</span>}
                    </div>
                  </div>
                  <div className="h-px w-full bg-gradient-to-r from-white/0 via-white/20 to-white/0" />
                  <div className="flex w-full flex-1 flex-col items-start gap-[15px]">
                    <p className="text-[16px] text-white/75">{t("lp.pricing.included")}</p>
                    <ul className="flex w-full flex-col gap-[14px]">
                      {lines.map((line) => (
                        <li key={line} className="flex items-start gap-3">
                          <img src={highlighted ? TICK_FILLED : TICK} alt="" className="h-6 w-6 shrink-0" />
                          <span className="text-[16px] leading-6 text-white/75">{line}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <GlowButton href="/register">{t("lp.pricing.choose", { plan: plan.name })}</GlowButton>
                </div>
                </Reveal>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ FAQ (five questions, like the mock-up) */

export function FaqSection() {
  const { t } = useTranslation();
  const items = [1, 2, 3, 4, 5].map((n) => ({ question: t(`lp.faq.${n}.q`), answer: t(`lp.faq.${n}.a`) }));
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="relative px-6 py-24">
      <ArtWindow y={3640} height={1200}><FaqShapesLayer /></ArtWindow>
      <div className="relative mx-auto flex max-w-[892px] flex-col items-center gap-[76px]">
        <div className="flex max-w-[830px] flex-col items-center gap-[29px] text-center">
          <Heading>{t("lp.faq.title1")}<br />{t("lp.faq.title2")}</Heading>
          <p className="text-[20px] leading-[28px] text-[#d9d9d9]">{t("lp.faq.subtitle")}</p>
        </div>
        <div className="flex w-full flex-col gap-[22px]">
          {items.map((item, index) => {
            const isOpen = open === index;
            return (
              <Reveal key={item.question} delay={index * 70}>
              <div className="w-full border-b-[1.2px] border-white/10 p-6">
                <button type="button" onClick={() => setOpen(isOpen ? null : index)} aria-expanded={isOpen} className="flex w-full items-start justify-between gap-6 text-left">
                  <span className="text-[20px] leading-[28.6px] text-white">{item.question}</span>
                  <img src="/landing/figma/imgArrowDown.svg" alt="" className={`h-7 w-7 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>
                {isOpen && <p className="hero-rise mt-6 text-[18px] leading-6 tracking-[-0.06px] text-[#919191]">{item.answer}</p>}
              </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ closing call to action + footer */

export function CtaSection() {
  const { t } = useTranslation();
  return (
    <section className="relative px-6 pb-24 pt-8 text-center">
      <Reveal className="relative mx-auto max-w-[900px] rounded-[20px] border-[1.25px] border-[rgba(255,84,31,0.2)] bg-[rgba(39,40,41,0.7)] px-8 py-16">
        <span aria-hidden className="absolute inset-0 rounded-[20px] bg-gradient-to-br from-transparent via-transparent to-[rgba(255,84,31,0.38)]" />
        <div className="relative">
          <h2 className="text-4xl font-bold leading-[1.1] text-white md:text-[48px]">{t("landing.cta_bottom.title")}</h2>
          <p className="mx-auto mt-4 max-w-[560px] text-[20px] leading-7 text-[#d9d9d9]">{t("landing.cta_bottom.subtitle")}</p>
          <Link href="/register" className="mt-9 inline-block rounded-[10px] bg-[#ff541f] px-[35px] py-[15px] text-[20px] font-bold leading-[19.2px] text-white transition-opacity hover:opacity-90">{t("landing.cta.start")}</Link>
        </div>
      </Reveal>
    </section>
  );
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function FooterSection() {
  const { t } = useTranslation();
  const currency = useDisplayCurrency();
  const columns = [
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
    <footer className="relative border-t border-white/10 px-6 py-14">
      <div className="mx-auto grid max-w-[1200px] grid-cols-2 gap-10 sm:grid-cols-4">
        <div className="col-span-2 sm:col-span-1">
          <span className="text-[22px] font-bold text-white">RAG SaaS Platform</span>
          <p className="mt-4 max-w-xs text-[16px] leading-6 text-white/75">{t("landing.footer.tagline")}</p>
          <div className="mt-12"><SocialLinks /></div>
        </div>
        {columns.map((column) => (
          <div key={column.title}>
            <p className="text-[18px] text-white">{column.title}</p>
            <div className="mt-4 flex flex-col gap-3">
              {column.links.map((link) => (
                <Link key={link.label} href={link.href} className="text-[16px] text-white/75 transition-colors hover:text-[#ff541f]">{link.label}</Link>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="mx-auto mt-12 max-w-[1200px] border-t border-white/10 pt-6 text-[14px] text-white/60">
        © {new Date().getFullYear()} RAG SaaS Platform. {t("landing.footer.copyright")}
        {currency.source === "market" && (
          <>
            {" "}{t("lp.footer.rates")}{" "}
            <a href={currency.attributionUrl ?? "https://www.exchangerate-api.com"} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">ExchangeRate-API</a>
          </>
        )}
      </p>
    </footer>
  );
}
