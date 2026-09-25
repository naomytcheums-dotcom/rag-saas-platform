"use client";

import Link from "next/link";
import Image from "next/image";
import { useState } from "react";

// Reproduction Strativo -- landing isolée
// Couleurs : #0C574B (primary), #D4AF37 (secondary), #F0F3F3 (bg-alt)

const COLORS = {
  primary: "#0C574B",
  secondary: "#D4AF37",
  heading: "#03201B",
  foreground: "#4B504F",
  bgAlt: "#F0F3F3",
  border: "#E4E4E7",
};

export default function LandingStrativo() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white" style={{ fontFamily: "Inter, sans-serif" }}>
      {/* ==================== HEADER ==================== */}
      <header className="border-b" style={{ borderColor: COLORS.border }}>
        <div className="mx-auto flex max-w-[1260px] items-center justify-between px-6 py-5">
          <Link href="/" className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg text-lg font-bold text-white"
              style={{ backgroundColor: COLORS.primary }}
            >
              R
            </div>
            <span className="text-xl font-semibold" style={{ color: COLORS.heading }}>
              RAG SaaS
            </span>
          </Link>

          <nav className="hidden items-center gap-6 lg:flex">
            {[
              { label: "Features", href: "#features" },
              { label: "Solutions", href: "#solutions" },
              { label: "Pricing", href: "#pricing" },
              { label: "Docs", href: "#docs" },
              { label: "Contact", href: "#contact" },
            ].map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="text-base transition-colors hover:opacity-70"
                style={{ color: COLORS.heading }}
              >
                {item.label}
              </a>
            ))}
          </nav>

          <div className="hidden lg:block">
            <a
              href="/register"
              className="inline-flex items-center gap-2 rounded-full px-6 py-3 text-base font-medium text-white transition-all hover:-translate-y-0.5"
              style={{ backgroundColor: COLORS.primary }}
            >
              Try Today
              <span>→</span>
            </a>
          </div>

          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden"
            aria-label="Menu"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.heading} strokeWidth="2">
              <path d="M3 6h18M3 12h18M3 18h18" />
            </svg>
          </button>
        </div>
      </header>

      {/* ==================== HERO ==================== */}
      <section className="px-6 pb-16 pt-20" style={{ backgroundColor: "#FFFFFF" }}>
        <div className="mx-auto max-w-[1380px]">
          {/* Badge avec avatars Unsplash */}
          <div className="mb-16 flex justify-center">
            <div
              className="flex items-center gap-3 rounded-full border px-4 py-3"
              style={{ borderColor: COLORS.border }}
            >
              <div className="flex -space-x-2">
                {[
                  "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=64&h=64&fit=crop&crop=face",
                  "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=64&h=64&fit=crop&crop=face",
                  "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=64&h=64&fit=crop&crop=face",
                  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=64&h=64&fit=crop&crop=face",
                ].map((url, i) => (
                  <div key={i} className="relative h-8 w-8 overflow-hidden rounded-full border-2 border-white">
                    <Image src={url} alt={`User ${i + 1}`} width={32} height={32} className="object-cover" unoptimized />
                  </div>
                ))}
              </div>
              <span className="text-sm" style={{ color: COLORS.heading }}>
                Join the brands already growing with us!
              </span>
            </div>
          </div>

          {/* Titre */}
          <div className="mx-auto max-w-[680px] text-center">
            <h1
              className="mb-6 text-[68px] font-semibold leading-[1.2] tracking-[-2px]"
              style={{ color: COLORS.heading }}
            >
              Build what you truly believe in with RAG SaaS
            </h1>
            <p className="mx-auto mb-8 max-w-[580px] text-lg" style={{ color: COLORS.foreground }}>
              The modern RAG platform built for fast launches, knowledge-grounded answers, and higher client conversions.
            </p>

            {/* CTA */}
            <div className="mt-12 flex flex-wrap justify-center gap-4">
              <a
                href="/register"
                className="inline-flex items-center gap-2 rounded-full px-12 py-4 text-base font-medium text-white transition-all hover:-translate-y-0.5"
                style={{ backgroundColor: COLORS.primary }}
              >
                Get Started Free
                <span>→</span>
              </a>
              <a
                href="#pricing"
                className="inline-flex items-center gap-2 rounded-full px-12 py-4 text-base font-medium transition-all hover:-translate-y-0.5"
                style={{ backgroundColor: COLORS.bgAlt, color: COLORS.primary }}
              >
                See Pricing
              </a>
            </div>
          </div>

          {/* Image hero -- dashboard mockup Unsplash */}
          <div
            className="mt-16 overflow-hidden rounded-3xl"
            style={{ boxShadow: "0 0 40px rgba(0,0,0,0.12)" }}
          >
            <div className="relative h-[400px] w-full">
              <Image
                src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1920&h=800&fit=crop"
                alt="Dashboard preview"
                fill
                className="object-cover"
                unoptimized
                priority
              />
              <div
                className="absolute inset-0 flex items-center justify-center"
                style={{ backgroundColor: "rgba(12, 87, 75, 0.4)" }}
              >
                <div className="text-center text-white">
                  <p className="text-3xl font-semibold">RAG SaaS Platform</p>
                  <p className="mt-2 text-sm opacity-90">Live dashboard preview</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ==================== NOTE ==================== */}
      <section className="border-t py-12" style={{ borderColor: COLORS.border, backgroundColor: COLORS.bgAlt }}>
        <div className="mx-auto max-w-3xl px-6 text-center">
          <p className="text-sm" style={{ color: COLORS.foreground }}>
            🚧 Reproduction <strong>partielle</strong> de Strativo (Header + Hero).
            Prochaines sections : Services, About, Portfolio, Testimonials, Pricing, FAQ, Blog, CTA, Footer.
          </p>
        </div>
      </section>
    </div>
  );
}
