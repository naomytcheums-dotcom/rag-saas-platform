import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post, searchState } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  searchState: { value: "tab=Subscriptions" },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(searchState.value),
}));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));
vi.mock("@/lib/auth", () => ({ useRequireAuth: () => ({ user: { id: "admin-1", email: "admin@example.test" }, loading: false }) }));
vi.mock("@/lib/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
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
  return { api: { get, post, delete: vi.fn() }, fileUrl: (path: string) => path, ApiError };
});

import AdminPage from "./page";
import { ApiError } from "@/lib/api";

const PLAN = { id: "plan-1", key: "free", name: "Free plan", monthly_price_cents: 0, is_active: true };

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockImplementation((path: string) => {
    if (path.startsWith("/admin/audit-logs")) return Promise.resolve({ items: [] });
    if (path === "/admin/plans") return Promise.resolve([PLAN]);
    if (path.startsWith("/admin/subscriptions")) return Promise.resolve([]);
    return Promise.reject(new ApiError(503, "unavailable"));
  });
});

async function fillAndSubmit(name: string, price: string) {
  fireEvent.change(await screen.findByPlaceholderText("admin.plan_name_placeholder"), { target: { value: name } });
  fireEvent.change(screen.getByPlaceholderText("admin.plan_price_placeholder"), { target: { value: price } });
  fireEvent.click(screen.getByRole("button", { name: "admin.create_plan" }));
}

describe("Creating a plan from the admin dashboard (SADM-005)", () => {
  it("explains a superadmin-only refusal next to the form and keeps the plans on screen", async () => {
    post.mockRejectedValue(new ApiError(403, "Superadmin access required"));
    render(<AdminPage />);
    await fillAndSubmit("Gold", "49");

    expect(await screen.findByRole("alert")).toHaveTextContent("admin.plan_write_forbidden");
    expect(screen.getByText("Free plan")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("admin.plan_name_placeholder")).toBeInTheDocument();
  });

  it("shows a readable message, not [object Object], for a server-side validation error", async () => {
    post.mockRejectedValue(new ApiError(422, [{ loc: ["body", "monthly_price_cents"], msg: "Input should be greater than or equal to 0", type: "greater_than_equal" }]));
    render(<AdminPage />);
    await fillAndSubmit("Gold", "49");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("monthly_price_cents: Input should be greater than or equal to 0");
    expect(alert).not.toHaveTextContent("[object Object]");
    expect(screen.getByText("Free plan")).toBeInTheDocument();
  });

  it("refuses a negative price in the form without calling the server", async () => {
    render(<AdminPage />);
    await fillAndSubmit("Gold", "-5");

    expect(await screen.findByRole("alert")).toHaveTextContent("admin.plan_price_invalid");
    expect(post).not.toHaveBeenCalled();
  });

  it("still creates a plan with the price in cents and reloads the list", async () => {
    post.mockResolvedValue({ id: "plan-2" });
    render(<AdminPage />);
    await fillAndSubmit("Gold", "49.9");

    await waitFor(() => expect(post).toHaveBeenCalledWith("/admin/plans", { key: "gold", name: "Gold", monthly_price_cents: 4990 }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
