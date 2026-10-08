"use client";

import Link from "next/link";
import LanguageMenu from "@/components/LanguageMenu";
import { useTranslation } from "@/lib/i18n";

/** The landing page's navigation (brand, Home / Features / Pricing / FAQ, language menu, Login) as a normal responsive header, so the pages the
 *  visitor reaches from it (sign in, sign up, password reset) keep exactly the same header and menu. */
export default function SiteHeader() {
  const { t } = useTranslation();
  const links = [
    { href: "/", label: t("landing.nav.home") },
    { href: "/#features", label: t("landing.nav.features") },
    { href: "/#pricing", label: t("landing.footer.pricing") },
    { href: "/#faq", label: t("landing.nav.faq") },
  ];
  return (
    <header className="relative z-20 mx-auto flex w-full max-w-[1200px] items-center justify-between gap-4 px-6 py-6">
      <Link href="/" className="text-[22px] font-bold tracking-wide text-white md:text-[26px]" aria-label="RAG SaaS Platform">RAG SaaS Platform</Link>
      <nav className="hidden items-center gap-10 text-[18px] text-white md:flex" aria-label="Main">
        {links.map((link) => (
          <Link key={link.href} href={link.href} className="transition-opacity hover:opacity-80">{link.label}</Link>
        ))}
      </nav>
      <div className="flex items-center gap-3">
        <LanguageMenu tone="dark" />
        <Link href="/login" className="rounded-[10px] bg-[#ff541f] px-[26px] py-[12px] text-[18px] font-bold leading-[19.2px] text-white transition-opacity hover:opacity-90">{t("landing.login")}</Link>
      </div>
    </header>
  );
}
