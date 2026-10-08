import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, orgState } = vi.hoisted(() => ({
  get: vi.fn(),
  orgState: { value: { id: "org-1", name: "Acme", slug: "acme", my_role: "owner" } as { id: string; name: string; slug: string; my_role: string } | null },
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));
vi.mock("@/lib/api", () => ({ api: { get } }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { email: "owner@example.test" } }) }));
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => ({ org: orgState.value, loading: false }) }));
vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ language: "en", t: (key: string) => key }),
}));

import DashboardHome from "./page";

beforeEach(() => {
  get.mockReset();
  orgState.value = { id: "org-1", name: "Acme", slug: "acme", my_role: "owner" };
});

describe("Dashboard home metrics", () => {
  it("explicitly reports failed requests without fabricating zero metrics", async () => {
    get.mockRejectedValue(new Error("API unavailable"));
    render(<DashboardHome />);

    expect(await screen.findByRole("alert")).toHaveTextContent("documents.error_load");
    expect(screen.getByRole("alert")).toHaveTextContent("agents.error_load");
    expect(screen.getByRole("alert")).toHaveTextContent("apikeys.error_load");
    expect(screen.getByRole("alert")).toHaveTextContent("webhooks.error_load");
    expect(screen.queryByText("0/0")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "0%" })).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });

  it("clears previous tenant errors and ignores rejected requests from a cancelled tenant", async () => {
    let rejectOldRequest: (error: Error) => void = () => {};
    get.mockImplementation((path: string) => {
      if (path.includes("/org-1/")) {
        if (path.endsWith("/webhooks")) return new Promise((_resolve, reject) => { rejectOldRequest = reject; });
        return Promise.reject(new Error("Tenant A unavailable"));
      }
      return Promise.resolve([]);
    });
    const view = render(<DashboardHome />);
    expect(await screen.findByRole("alert")).toHaveTextContent("documents.error_load");

    orgState.value = { id: "org-2", name: "Other", slug: "other", my_role: "owner" };
    view.rerender(<DashboardHome />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    rejectOldRequest(new Error("Tenant A late failure"));
    await waitFor(() => expect(get).toHaveBeenCalledTimes(8));
    await waitFor(() => expect(screen.getByText("dash.kb.empty")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows unavailable states rather than fabricated zeroes when API requests fail", async () => {
    get.mockRejectedValue(new Error("API unavailable"));
    render(<DashboardHome />);

    await waitFor(() => expect(get).toHaveBeenCalledTimes(4));

    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByText("0/0")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "0%" })).not.toBeInTheDocument();
    expect(screen.queryByText("dash.resources.upload")).not.toBeInTheDocument();
    expect(screen.queryByText("dash.agents.empty")).not.toBeInTheDocument();
  });

  it("derives displayed counts and indexing percentage from the selected organization's API data", async () => {
    get
      .mockResolvedValueOnce([
        { id: "doc-1", name: "Indexed.pdf", file_size: 100, file_type: "application/pdf", status: "indexed", created_at: "2026-10-01T00:00:00Z" },
        { id: "doc-2", name: "Pending.pdf", file_size: 200, file_type: "application/pdf", status: "processing", created_at: "2026-10-02T00:00:00Z" },
      ])
      .mockResolvedValueOnce([{ id: "agent-1", name: "Support", description: null, tools: [] }])
      .mockResolvedValueOnce([{ id: "key-1" }])
      .mockResolvedValueOnce([{ id: "hook-1" }]);
    render(<DashboardHome />);

    await waitFor(() => expect(screen.getAllByText("1/2")).toHaveLength(2));
    expect(screen.getByRole("img", { name: "50%" })).toBeInTheDocument();
    expect(screen.getByText("Indexed.pdf")).toBeInTheDocument();
    expect(screen.getByText("Support")).toBeInTheDocument();
  });

  it("does not retain one organization's metrics after switching organizations when the next fetch fails", async () => {
    get.mockImplementation((path: string) => {
      if (path.endsWith("/documents")) {
        return path.includes("/org-1/") ? Promise.resolve([
          { id: "private-doc", name: "Tenant A private document.pdf", file_size: 100, file_type: "application/pdf", status: "indexed", created_at: "2026-10-01T00:00:00Z" },
        ]) : Promise.reject(new Error("API unavailable"));
      }
      if (path.endsWith("/agents")) {
        return path.includes("/org-1/") ? Promise.resolve([{ id: "tenant-a-agent", name: "Tenant A private agent", description: null, tools: [] }]) : Promise.reject(new Error("API unavailable"));
      }
      return Promise.reject(new Error("API unavailable"));
    });
    const view = render(<DashboardHome />);

    expect(await screen.findByText("Tenant A private document.pdf")).toBeInTheDocument();
    expect(screen.getByText("Tenant A private agent")).toBeInTheDocument();

    orgState.value = { id: "org-2", name: "Other", slug: "other", my_role: "owner" };
    view.rerender(<DashboardHome />);

    await waitFor(() => expect(get).toHaveBeenCalledTimes(8));
    expect(screen.queryByText("Tenant A private document.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText("Tenant A private agent")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });
});
