// BILL-004: buying a credit pack must go through the provider's hosted checkout; the direct top-up is only the fallback of a
// deployment without a payment provider. The API client is mocked: the assertions are about which endpoints are called.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/lib/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => ({ org: { id: "org-1", name: "Acme", slug: "acme", my_role: "owner" }, loading: false }) }));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
      this.detail = detail;
    }
  }
  return { api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) }, ApiError };
});

import { ApiError } from "@/lib/api";
import BillingPage from "./page";

const PLANS = [
  { id: "plan-free", key: "free", name: "Free", monthly_price_cents: 0, yearly_price_cents: 0, max_documents: 50, max_agents: 3, max_members: 5, priority_support: false, advanced_features: false, sla: false, is_active: true },
];
const SUBSCRIPTION = { id: "sub-1", plan_id: "plan-free", status: "active", billing_period: "monthly", current_period_end: null, canceled_at: null };
const PACKS = [{ id: "starter", name: "Starter", credits: 10000, price_cents: 999 }];
const originalLocation = window.location;
const assign = vi.fn();

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  assign.mockReset();
  get.mockImplementation(async (url: string) => {
    if (url === "/billing/plans") return PLANS;
    if (url.endsWith("/billing/subscription")) return SUBSCRIPTION;
    if (url.startsWith("/billing/plans/")) return PLANS[0];
    if (url.endsWith("/credits/packs")) return PACKS;
    if (url.endsWith("/credits/transactions") || url.includes("invoices")) return [];
    return { organization_id: "org-1", balance: 0 };
  });
  Object.defineProperty(window, "location", { configurable: true, value: { href: "http://localhost/dashboard/billing", assign } });
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

async function openBuyButton() {
  render(<BillingPage />);
  await userEvent.click(await screen.findByRole("button", { name: "billing.tab_credits" }));
  return screen.findByRole("button", { name: "billing.buy" });
}

describe("Billing page - buying credits", () => {
  it("opens the provider checkout and never uses the direct top-up", async () => {
    post.mockResolvedValue({ url: "https://checkout.example/session/pack" });
    await userEvent.click(await openBuyButton());

    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.example/session/pack"));
    expect(post).toHaveBeenCalledWith("/organizations/org-1/billing/credits/checkout", { pack_id: "starter" });
    expect(post.mock.calls.some(([url]) => String(url).endsWith("/credits/purchase"))).toBe(false);
  });

  it("falls back to the direct top-up only when no payment provider is configured (501)", async () => {
    post.mockImplementation(async (url: string) => {
      if (url.endsWith("/credits/checkout")) throw new ApiError(501, "No payment provider configured");
      return {};
    });
    await userEvent.click(await openBuyButton());

    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/billing/credits/purchase", { pack_id: "starter" }));
    expect(assign).not.toHaveBeenCalled();
  });

  it("shows any other checkout error and does not fall back to a free top-up", async () => {
    post.mockRejectedValue(new ApiError(502, "provider down"));
    await userEvent.click(await openBuyButton());

    expect(await screen.findByText("provider down")).toBeInTheDocument();
    expect(post.mock.calls.some(([url]) => String(url).endsWith("/credits/purchase"))).toBe(false);
  });
});
