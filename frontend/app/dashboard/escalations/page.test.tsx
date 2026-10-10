// Spec 15.1.9: the human-facing escalations screen lists tickets, takes one, adds a note and resolves with a written resolution.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();

const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
const currentOrg = { org: { id: "org-1" } };
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => currentOrg }));
vi.mock("@/components/LoadingState", () => ({ default: () => <p>loading</p> }));
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
  return { api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), patch: (...a: unknown[]) => patch(...a) }, ApiError };
});

import EscalationsPage from "./page";

const ticket = { id: "t1", issue: "Cannot find the contract", priority: "high", status: "open", resolution: null, assignee_id: null, created_at: "2026-10-10T10:00:00Z", sla_due_at: null, sla_breached: true };

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
  get.mockImplementation((path: string) => {
    if (path.endsWith("/notes")) return Promise.resolve([]);
    if (path === "/account/me") return Promise.resolve({ id: "u1" });
    return Promise.resolve({ items: [ticket] });
  });
  post.mockResolvedValue({});
  patch.mockResolvedValue({});
});

describe("EscalationsPage", () => {
  it("lists the tickets with priority, status and the SLA warning", async () => {
    render(<EscalationsPage />);
    expect(await screen.findByText("Cannot find the contract")).toBeInTheDocument();
    expect(screen.getByText("escalations.sla_breached")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/organizations/org-1/escalations");
  });

  it("filters by status through the query string", async () => {
    render(<EscalationsPage />);
    await screen.findByText("Cannot find the contract");
    await userEvent.selectOptions(screen.getByLabelText("escalations.filter_status"), "resolved");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/organizations/org-1/escalations?status=resolved"));
  });

  it("takes a ticket for the signed-in user", async () => {
    render(<EscalationsPage />);
    await userEvent.click(await screen.findByText("Cannot find the contract"));
    await userEvent.click(await screen.findByRole("button", { name: "escalations.take" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/escalations/t1/assign", { assignee_id: "u1" }));
  });

  it("adds an internal note", async () => {
    render(<EscalationsPage />);
    await userEvent.click(await screen.findByText("Cannot find the contract"));
    await userEvent.type(await screen.findByLabelText("escalations.note_placeholder"), "Called the customer");
    await userEvent.click(screen.getByRole("button", { name: "escalations.add_note" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/escalations/t1/notes", { body: "Called the customer" }));
  });

  it("only allows resolving with a written resolution", async () => {
    render(<EscalationsPage />);
    await userEvent.click(await screen.findByText("Cannot find the contract"));
    const resolve = await screen.findByRole("button", { name: "escalations.resolve" });
    expect(resolve).toBeDisabled();
    await userEvent.type(screen.getByLabelText("escalations.resolution_placeholder"), "Sent by e-mail");
    expect(resolve).toBeEnabled();
    await userEvent.click(resolve);
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/organizations/org-1/escalations/t1", { status: "resolved", resolution: "Sent by e-mail" }));
  });
});
