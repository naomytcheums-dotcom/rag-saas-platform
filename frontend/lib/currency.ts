"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Price display currency of the visitor. Plans are stored and BILLED in euros (Stripe), so this only changes how the amount is shown.
 *
 * The server decides (GET /billing/display-currency): the visitor's country from their IP address, else the region of their browser language,
 * then that country's official currency with a real rate (a daily market rate, or the fixed official parity for the CFA, CFP and Comorian
 * francs). If the server cannot be reached the page falls back to what the browser alone can tell (CFA zones by time zone), then to euros.
 */
export interface DisplayCurrency {
  code: string;
  /** Units of the display currency for one euro. */
  perEuro: number;
  /** "euro" = no conversion, "peg" = fixed official parity, "market" = daily rate. */
  source: "euro" | "peg" | "market";
  attributionUrl?: string | null;
}

export interface DisplayCurrencyAnswer {
  country: string | null;
  currency: string;
  per_euro: number;
  source: "euro" | "peg" | "market";
  attribution_url: string | null;
  language: string | null;
}

export const EURO: DisplayCurrency = { code: "EUR", perEuro: 1, source: "euro" };

const CFA_PEG = 655.957;
const CEMAC = new Set(["CM", "GA", "CG", "TD", "CF", "GQ"]);
const UEMOA = new Set(["SN", "CI", "ML", "BF", "BJ", "TG", "NE", "GW"]);

const TIMEZONE_COUNTRY: Record<string, string> = {
  "Africa/Douala": "CM", "Africa/Libreville": "GA", "Africa/Brazzaville": "CG", "Africa/Ndjamena": "TD", "Africa/Bangui": "CF", "Africa/Malabo": "GQ",
  "Africa/Dakar": "SN", "Africa/Abidjan": "CI", "Africa/Bamako": "ML", "Africa/Ouagadougou": "BF", "Africa/Porto-Novo": "BJ", "Africa/Lome": "TG",
  "Africa/Niamey": "NE", "Africa/Bissau": "GW",
};

/** Offline fallback only: the CFA-franc countries, from the browser time zone or locale. */
export function detectCountry(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (zone && TIMEZONE_COUNTRY[zone]) return TIMEZONE_COUNTRY[zone];
    return new Intl.Locale(navigator.language).region ?? null;
  } catch {
    return null;
  }
}

export function currencyForCountry(country: string | null): DisplayCurrency {
  if (country && CEMAC.has(country)) return { code: "XAF", perEuro: CFA_PEG, source: "peg" };
  if (country && UEMOA.has(country)) return { code: "XOF", perEuro: CFA_PEG, source: "peg" };
  return EURO;
}

export function fromAnswer(answer: DisplayCurrencyAnswer): DisplayCurrency {
  if (!answer.currency || !(answer.per_euro > 0)) return EURO;
  return { code: answer.currency, perEuro: answer.per_euro, source: answer.source, attributionUrl: answer.attribution_url };
}

/** Converted prices are shown as clean price points (32 142 -> 32 000, 52.92 -> 53), the way a price list is written, not as raw conversions. */
function cleanPricePoint(amount: number): number {
  if (amount >= 1000) {
    const step = 10 ** (Math.floor(Math.log10(amount)) - 1);
    return Math.round(amount / step) * step;
  }
  if (amount >= 100) return Math.round(amount / 5) * 5;
  return Math.round(amount);
}

/** Formats an amount given in euro cents in the display currency. Euro amounts stay exact; converted ones are rounded to a clean price point. */
export function formatEuroCents(cents: number, currency: DisplayCurrency, locale: string): string {
  const exact = (cents / 100) * currency.perEuro;
  const amount = currency.code === "EUR" ? exact : cleanPricePoint(exact);
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency: currency.code, minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(amount);
  } catch {
    // a currency code this browser does not know: show the euro amount rather than a wrong one
    return new Intl.NumberFormat(locale, { style: "currency", currency: "EUR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(cents / 100);
  }
}

let cached: Promise<DisplayCurrencyAnswer | null> | null = null;

/** One shared request per page load for the currency and the language hint. */
export function fetchDisplayCurrency(): Promise<DisplayCurrencyAnswer | null> {
  cached ??= api.get<DisplayCurrencyAnswer>("/billing/display-currency").catch(() => null);
  return cached;
}

/** The visitor's display currency; euros until it is known (so server and first client render agree). */
export function useDisplayCurrency(): DisplayCurrency {
  const [currency, setCurrency] = useState<DisplayCurrency>(EURO);
  useEffect(() => {
    let cancelled = false;
    void fetchDisplayCurrency().then((answer) => {
      if (cancelled) return;
      setCurrency(answer ? fromAnswer(answer) : currencyForCountry(detectCountry()));
    });
    return () => { cancelled = true; };
  }, []);
  return currency;
}
