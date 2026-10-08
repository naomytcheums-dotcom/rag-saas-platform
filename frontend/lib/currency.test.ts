import { describe, expect, it } from "vitest";
import { currencyForCountry, EURO, formatEuroCents, fromAnswer } from "@/lib/currency";

const digits = (text: string) => text.replace(/\D/g, "");

describe("price display currency", () => {
  it("shows Central-African (CEMAC) visitors, such as Cameroon, in CFA francs (XAF)", () => {
    expect(currencyForCountry("CM").code).toBe("XAF");
    expect(currencyForCountry("GA").code).toBe("XAF");
  });

  it("shows West-African (UEMOA) visitors in CFA francs (XOF)", () => {
    expect(currencyForCountry("SN").code).toBe("XOF");
    expect(currencyForCountry("CI").code).toBe("XOF");
  });

  it("keeps euros everywhere else, and when the country is unknown", () => {
    expect(currencyForCountry("FR").code).toBe("EUR");
    expect(currencyForCountry("US").code).toBe("EUR");
    expect(currencyForCountry(null).code).toBe("EUR");
  });

  it("converts with the official fixed peg, 655.957 CFA francs per euro (49 EUR = 32 142 XAF, shown as the clean price point 32 000)", () => {
    const text = formatEuroCents(4900, currencyForCountry("CM"), "fr");
    expect(digits(text)).toBe("32000");
    expect(text).toMatch(/FCFA|XAF/);
  });

  it("leaves euro amounts untouched", () => {
    const text = formatEuroCents(4900, currencyForCountry("FR"), "fr");
    expect(digits(text)).toBe("49");
    expect(text).toContain("€");
  });
});

describe("currency answered by the server", () => {
  it("converts euro cents with the rate the server gave, for any currency in the world", () => {
    const usd = fromAnswer({ country: "US", currency: "USD", per_euro: 1.08, source: "market", attribution_url: null, language: null });
    expect(digits(formatEuroCents(4900, usd, "en"))).toBe("53");
    const jpy = fromAnswer({ country: "JP", currency: "JPY", per_euro: 165.4, source: "market", attribution_url: null, language: null });
    expect(digits(formatEuroCents(4900, jpy, "en"))).toBe("8100");
    const mru = fromAnswer({ country: "MR", currency: "MRU", per_euro: 43.2, source: "market", attribution_url: null, language: "ar" });
    expect(digits(formatEuroCents(4900, mru, "fr"))).toBe("2100");
  });

  it("falls back to euros when the answer is unusable", () => {
    expect(fromAnswer({ country: null, currency: "", per_euro: 0, source: "euro", attribution_url: null, language: null })).toEqual(EURO);
  });

  it("never throws on a currency code the browser does not know: it shows the euro amount", () => {
    const text = formatEuroCents(4900, { code: "ZZZZ", perEuro: 3, source: "market" }, "en");
    expect(digits(text)).toBe("49");
  });
});
