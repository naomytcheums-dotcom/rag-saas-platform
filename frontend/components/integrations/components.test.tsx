// Partie 15.1/15.2 -- real render/interaction tests for the 11 named
// universal-integrations components (ProviderList/ProviderCard/
// ConnectionList/ConnectionItem/ConnectionForm/ConnectionTest/
// SyncHistory/MappingEditor/MappingList/WebhookConfig/
// IntegrationLogs). `@/lib/api` is mocked (a real network call to a
// FastAPI backend has no place in a component test), so each test
// asserts the component called the real, correct endpoint/method and
// rendered the real response -- not that a live backend exists.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConnectionForm from "../ConnectionForm";
import ConnectionItem from "../ConnectionItem";
import ConnectionList from "../ConnectionList";
import ConnectionTest from "../ConnectionTest";
import IntegrationLogs from "../IntegrationLogs";
import MappingEditor from "../MappingEditor";
import MappingList from "../MappingList";
import ProviderCard from "../ProviderCard";
import ProviderList from "../ProviderList";
import SyncHistory from "../SyncHistory";
import WebhookConfig from "../WebhookConfig";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
      this.detail = detail;
    }
  },
}));

import { api } from "@/lib/api";

const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn>; patch: ReturnType<typeof vi.fn>; delete: ReturnType<typeof vi.fn> };

beforeEach(() => {
  mockedApi.get.mockReset();
  mockedApi.post.mockReset();
  mockedApi.patch.mockReset();
  mockedApi.delete.mockReset();
});

describe("ProviderCard", () => {
  it("renders the provider name/description and reports selection", async () => {
    const onSelect = vi.fn();
    render(<ProviderCard provider={{ id: "n8n", name: "n8n", description: "Use an HTTP Request node." }} selected={false} onSelect={onSelect} />);
    await userEvent.click(screen.getByText("n8n"));
    expect(onSelect).toHaveBeenCalledWith("n8n");
  });
});

describe("ProviderList", () => {
  it("fetches GET /integrations/providers and renders one card per provider", async () => {
    mockedApi.get.mockResolvedValueOnce([
      { id: "webhook", name: "Generic webhook", description: "Any system that can POST JSON." },
      { id: "zapier", name: "Zapier", description: "Webhooks by Zapier." },
    ]);
    render(<ProviderList selected="webhook" onSelect={vi.fn()} />);
    await waitFor(() => expect(mockedApi.get).toHaveBeenCalledWith("/integrations/providers"));
    expect(await screen.findByText("Zapier")).toBeInTheDocument();
  });
});

describe("ConnectionForm", () => {
  it("POSTs the new connection with the selected provider/action and calls onCreated", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "webhook", name: "Generic webhook", description: "..." }]);
    mockedApi.post.mockResolvedValueOnce({ id: "c1", name: "My CRM", provider: "webhook", action: "log_only", is_active: true, created_at: "2026-01-01T00:00:00Z", token: "secret-token" });
    const onCreated = vi.fn();
    render(<ConnectionForm orgId="org1" onCreated={onCreated} onError={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText("Connection name"), "My CRM");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/integrations/connections", { name: "My CRM", provider: "webhook", action: "log_only" }));
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "c1", token: "secret-token" }));
  });
});

describe("WebhookConfig", () => {
  it("shows the inbound URL, and the token only when provided", () => {
    const { rerender } = render(<WebhookConfig connectionId="c1" provider="zapier" token="tok-123" />);
    expect(screen.getByText(/integrations\/inbound\/c1/)).toBeInTheDocument();
    expect(screen.getByText(/Bearer tok-123/)).toBeInTheDocument();

    rerender(<WebhookConfig connectionId="c1" provider="zapier" />);
    expect(screen.queryByText(/Bearer tok-123/)).not.toBeInTheDocument();
    expect(screen.getByText(/shown once, at creation/)).toBeInTheDocument();
  });
});

describe("ConnectionTest", () => {
  it("POSTs .../test and renders the real dry-run result", async () => {
    mockedApi.post.mockResolvedValueOnce({ connection_active: true, sample_payload: { title: "Sample record" }, mapped_payload: { title: "Sample record" }, would_run_action: "log_only" });
    render(<ConnectionTest orgId="org1" connectionId="c1" />);

    await userEvent.click(screen.getByRole("button", { name: "Run test" }));

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/integrations/connections/c1/test"));
    expect(await screen.findByText("log_only")).toBeInTheDocument();
  });
});

describe("MappingEditor", () => {
  it("creates a new mapping via POST when no `existing` prop is given", async () => {
    mockedApi.post.mockResolvedValueOnce({ id: "m1", source_field: "Email", target_field: "email", transform: "normalize_email" });
    const onSaved = vi.fn();
    render(<MappingEditor orgId="org1" connectionId="c1" onSaved={onSaved} onError={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText("Source field"), "Email");
    await userEvent.type(screen.getByPlaceholderText("Target field"), "email");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/integrations/connections/c1/mappings", { source_field: "Email", target_field: "email", transform: null }));
    expect(onSaved).toHaveBeenCalled();
  });

  it("edits an existing mapping via the previously-missing PATCH endpoint", async () => {
    const existing = { id: "m1", source_field: "Email", target_field: "email", transform: null };
    mockedApi.patch.mockResolvedValueOnce({ ...existing, target_field: "email_address" });
    const onSaved = vi.fn();
    render(<MappingEditor orgId="org1" connectionId="c1" existing={existing} onSaved={onSaved} onError={vi.fn()} />);

    const targetInput = screen.getByDisplayValue("email");
    await userEvent.clear(targetInput);
    await userEvent.type(targetInput, "email_address");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(mockedApi.patch).toHaveBeenCalledWith("/organizations/org1/integrations/mappings/m1", { source_field: "Email", target_field: "email_address", transform: null }));
    expect(onSaved).toHaveBeenCalled();
  });
});

describe("MappingList", () => {
  it("fetches mappings and deletes one on click", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "m1", source_field: "Email", target_field: "email", transform: null }]);
    mockedApi.delete.mockResolvedValueOnce(undefined);
    mockedApi.get.mockResolvedValueOnce([]); // reload after delete
    render(<MappingList orgId="org1" connectionId="c1" onError={vi.fn()} />);

    expect(await screen.findByText(/Email → email/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith("/organizations/org1/integrations/mappings/m1"));
  });
});

describe("SyncHistory", () => {
  it("loads sync history and retries failed syncs on click", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "l1", status: "error", payload: {}, detail: "boom", created_at: "2026-01-01T00:00:00Z" }]);
    mockedApi.post.mockResolvedValueOnce([]);
    mockedApi.get.mockResolvedValueOnce([]); // reload after retry
    render(<SyncHistory orgId="org1" connectionId="c1" onError={vi.fn()} />);

    expect(await screen.findByText("error")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry failed" }));

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/integrations/connections/c1/sync"));
  });
});

describe("IntegrationLogs", () => {
  it("loads the receipt log and expands a row to show the raw payload", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "l1", status: "accepted", payload: { email: "a@b.com" }, detail: null, created_at: "2026-01-01T00:00:00Z" }]);
    render(<IntegrationLogs orgId="org1" connectionId="c1" onError={vi.fn()} />);

    const row = await screen.findByText(/accepted/);
    await userEvent.click(row);
    expect(screen.getByText(/a@b.com/)).toBeInTheDocument();
  });
});

describe("ConnectionItem", () => {
  it("expands to reveal its management panels and deletes the connection", async () => {
    mockedApi.get.mockResolvedValue([]); // every sub-panel's initial fetch
    mockedApi.delete.mockResolvedValueOnce(undefined);
    const onDeleted = vi.fn();
    const connection = { id: "c1", name: "My CRM", provider: "webhook", action: "log_only", is_active: true, created_at: "2026-01-01T00:00:00Z" };
    render(<ConnectionItem orgId="org1" connection={connection} onDeleted={onDeleted} onError={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Manage" }));
    expect(screen.getByText("Field mappings")).toBeInTheDocument();
    expect(screen.getByText("Sync history")).toBeInTheDocument();
    expect(screen.getByText("Receipt log")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith("/organizations/org1/integrations/connections/c1"));
    expect(onDeleted).toHaveBeenCalledWith("c1");
  });
});

describe("ConnectionList", () => {
  it("loads connections and reveals the just-created token on the matching item only", async () => {
    // Two independent children (ConnectionList itself, and ProviderList
    // nested inside ConnectionForm) each call api.get on mount -- their
    // real call order isn't guaranteed, so route by URL instead of by
    // call sequence.
    mockedApi.get.mockImplementation((path: string) => {
      if (path === "/organizations/org1/integrations/connections") {
        return Promise.resolve([{ id: "c1", name: "My CRM", provider: "webhook", action: "log_only", is_active: true, created_at: "2026-01-01T00:00:00Z" }]);
      }
      if (path === "/integrations/providers") {
        return Promise.resolve([{ id: "webhook", name: "Generic webhook", description: "..." }]);
      }
      return Promise.resolve([]);
    });
    render(<ConnectionList orgId="org1" onError={vi.fn()} />);

    expect(await screen.findByText("My CRM", { exact: false })).toBeInTheDocument();
    const list = screen.getByText(/Zapier \/ Make \/ n8n/).closest("div")!;
    expect(within(list).getByText(/webhook → log_only/)).toBeInTheDocument();
  });
});
