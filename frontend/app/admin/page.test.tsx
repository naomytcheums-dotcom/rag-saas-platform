import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, searchState } = vi.hoisted(() => ({
  get: vi.fn(),
  searchState: { value: "" },
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
  return { api: { get, post: vi.fn(), delete: vi.fn() }, fileUrl: (path: string) => path, ApiError };
});

import AdminPage from "./page";
import { ApiError } from "@/lib/api";

beforeEach(() => {
  get.mockReset();
  searchState.value = "";
});

describe("Admin dashboard data and access states", () => {
  it("renders the translated denial description instead of hardcoded text when server authorization rejects access", async () => {
    get.mockRejectedValue(new ApiError(404, "not found"));
    render(<AdminPage />);

    expect(await screen.findByText("admin.access_denied_desc")).toBeInTheDocument();
  });

  it("does not present failed alerting requests as empty history or no incidents", async () => {
    get.mockImplementation((path: string) => path.startsWith("/admin/audit-logs")
      ? Promise.resolve({ items: [] })
      : Promise.reject(new ApiError(503, "unavailable")));
    searchState.value = "tab=Alerting";
    render(<AdminPage />);

    expect(await screen.findAllByText("admin.error_load")).toHaveLength(4);
    expect(screen.queryByText("admin.alert_history_empty")).not.toBeInTheDocument();
    expect(screen.queryByText("admin.incidents_empty")).not.toBeInTheDocument();
  });

  it("does not show an empty subscriptions state when the subscription request fails", async () => {
    get.mockImplementation((path: string) => {
      if (path.startsWith("/admin/audit-logs")) return Promise.resolve({ items: [] });
      if (path === "/admin/plans") return Promise.resolve([]);
      return Promise.reject(new ApiError(503, "unavailable"));
    });
    searchState.value = "tab=Subscriptions";
    render(<AdminPage />);

    expect(await screen.findByText("admin.error_load")).toBeInTheDocument();
    expect(screen.queryByText("admin.subs_empty")).not.toBeInTheDocument();
  });
});
