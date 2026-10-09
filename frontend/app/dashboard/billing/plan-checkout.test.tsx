// P0 billing (BILL-001/UX-001): "Choose this plan" must start the provider checkout for a paid plan and only call
// /subscribe for a free one. The API client is mocked: the assertions are about which endpoint the screen calls, the
// redirect, and that a failure is shown as an error instead of a misleading success.

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
  { id: "plan-ent", key: "enterprise", name: "Enterprise", monthly_price_cents: 99900, yearly_price_cents: 999000, max_documents: null, max_agents: null, max_members: null, priority_support: true, advanced_features: true, sla: true, is_active: true },
];
const SUBSCRIPTION = { id: "sub-1", plan_id: "plan-other", status: "active", billing_period: "monthly", current_period_end: null, canceled_at: null };
const originalLocation = window.location;
const assign = vi.fn();

beforeEach(() => {
  get.mockReset();
  assign.mockReset();
  post.mockReset();
  get.mockImplementation(async (url: string) => {
    if (url === "/billing/plans") return PLANS;
    if (url.endsWith("/billing/subscription")) return SUBSCRIPTION;
    if (url.startsWith("/billing/plans/")) return PLANS[0];
    return url.includes("invoices") ? [] : { organization_id: "org-1", balance: 0 };
  });
  Object.defineProperty(window, "location", { configurable: true, value: { href: "http://localhost/dashboard/billing", assign } });
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

async function openPlansTab() {
  render(<BillingPage />);
  await userEvent.click(await screen.findByRole("button", { name: "billing.tab_plans" }));
  return screen.findAllByRole("button", { name: "billing.choose_plan" });
}

describe("Billing page - choosing a plan", () => {
  it("starts the checkout for a paid plan, redirects to its URL and never calls /subscribe", async () => {
    post.mockResolvedValue({ url: "https://checkout.example/session/abc" });
    const buttons = await openPlansTab();

    await userEvent.click(buttons[1]);

    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.example/session/abc"));
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/organizations/org-1/billing/checkout", { plan_id: "plan-ent", billing_period: "monthly" });
    expect(post.mock.calls.some(([url]) => String(url).endsWith("/billing/subscribe"))).toBe(false);
  });

  it("sends the selected yearly period to the checkout", async () => {
    post.mockResolvedValue({ url: "https://checkout.example/session/yearly" });
    const buttons = await openPlansTab();
    await userEvent.click(screen.getByRole("button", { name: "billing.yearly" }));

    await userEvent.click(buttons[1]);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/billing/checkout", { plan_id: "plan-ent", billing_period: "yearly" }));
  });

  it("uses /subscribe only for a free plan and does not open a checkout", async () => {
    post.mockResolvedValue({});
    const buttons = await openPlansTab();

    await userEvent.click(buttons[0]);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/billing/subscribe", { plan_id: "plan-free", billing_period: "monthly" }));
    expect(post.mock.calls.some(([url]) => String(url).endsWith("/billing/checkout"))).toBe(false);
    expect(assign).not.toHaveBeenCalled();
  });

  it("shows the 'payment not configured' error on 501 and neither redirects nor falls back to /subscribe", async () => {
    post.mockRejectedValue(new ApiError(501, "No payment provider configured"));
    const buttons = await openPlansTab();

    await userEvent.click(buttons[1]);

    expect(await screen.findByText("billing.payment_not_configured")).toBeTruthy();
    expect(assign).not.toHaveBeenCalled();
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls.some(([url]) => String(url).endsWith("/billing/subscribe"))).toBe(false);
  });

  it("shows the server's message on 402 instead of a success", async () => {
    post.mockRejectedValue(new ApiError(402, "Payment required for this plan"));
    const buttons = await openPlansTab();

    await userEvent.click(buttons[1]);

    expect(await screen.findByText("Payment required for this plan")).toBeTruthy();
    expect(assign).not.toHaveBeenCalled();
  });
});
