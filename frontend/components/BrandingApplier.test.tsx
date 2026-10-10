// Specs 1.4.6, 1.4.8: the organization's brand name, accent colour and font are applied to the whole signed-in interface.
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const branding = { logo_url: null, favicon_url: null, primary_color: "#112233", secondary_color: "#000000", accent_color: "#112233", font_family: "Georgia", custom_css: null, brand_name: "Acme Support" };
vi.mock("@/lib/branding-context", () => ({ useBranding: () => ({ branding }) }));

import { BrandingApplier } from "./BrandingApplier";

afterEach(() => { document.title = ""; document.documentElement.removeAttribute("style"); });

describe("BrandingApplier", () => {
  it("replaces the platform name in the tab title with the organization brand name", () => {
    render(<BrandingApplier />);
    expect(document.title).toBe("Acme Support");
  });

  it("applies the accent colour and the font to the whole interface", () => {
    render(<BrandingApplier />);
    const style = document.documentElement.style;
    expect(style.getPropertyValue("--accent")).toBe("#112233");
    expect(style.getPropertyValue("--font-sans")).toBe("Georgia");
  });
});
