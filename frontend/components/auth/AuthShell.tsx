"use client";

import Link from "next/link";
import type { InputHTMLAttributes, ReactNode } from "react";
import { HeroArtLayer } from "@/components/figma/artwork";
import SiteHeader from "@/components/figma/SiteHeader";
import Stage from "@/components/figma/Stage";

/**
 * Card used by every authentication page (login, register, forgot / reset password, two-factor code).
 * Visual spec supplied by the product owner: a 420px blue gradient card, white pill inputs with a translucent border, a white pill button.
 */
export default function AuthShell({ title, subtitle, error, children, footer }: { title: string; subtitle?: string; error?: string | null; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-[#010101]">
      <div className="pointer-events-none absolute inset-x-0 top-0" aria-hidden>
        <Stage width={1440} height={972}><div className="relative h-[972px] w-[1440px] overflow-hidden"><HeroArtLayer /></div></Stage>
      </div>
      <SiteHeader />
      <div className="relative flex flex-1 items-center justify-center px-4 pb-16 pt-4">
      <div
        className="relative w-full max-w-[420px] rounded-xl px-10 py-[30px] text-white shadow-md backdrop-blur-[9px]"
        style={{ background: "linear-gradient(90deg, var(--auth-from) 9%, var(--auth-via) 68%, var(--auth-to) 97%)" }}
      >
        <h1 className="text-center text-4xl font-medium">{title}</h1>
        {subtitle && <p className="mt-2 text-center text-sm text-white/75">{subtitle}</p>}
        {error && <p role="alert" className="mt-5 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        {children}
        {footer && <div className="mb-[15px] mt-5 text-center text-[14.5px]">{footer}</div>}
      </div>
      </div>
    </div>
  );
}

/** Pill input. The visible label is the placeholder (as in the reference design); a screen-reader label keeps it accessible. */
export function AuthField({ label, ...props }: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative my-[30px] h-[50px] w-full">
      <label className="sr-only">{label}</label>
      <input
        aria-label={label}
        placeholder={label}
        {...props}
        className="h-full w-full rounded-full border-2 border-white/20 bg-transparent py-5 pl-5 pr-[45px] text-base text-white outline-none transition-colors placeholder:text-white focus:border-white/60"
      />
    </div>
  );
}

export function AuthButton({ children, disabled }: { children: ReactNode; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="mx-auto mt-2.5 block h-[45px] w-[150px] rounded-full bg-white text-base font-semibold text-[#333] shadow-[0_0_10px_rgba(0,0,0,0.1)] transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function AuthLink({ href, children, strong = false }: { href: string; children: ReactNode; strong?: boolean }) {
  return (
    <Link href={href} className={`text-white hover:underline ${strong ? "font-semibold" : ""}`}>
      {children}
    </Link>
  );
}
