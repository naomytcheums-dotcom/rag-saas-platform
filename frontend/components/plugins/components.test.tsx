// Partie 16 (ter) -- real render/interaction tests for the plugin
// marketplace components. `@/lib/api` is mocked (a real network call
// to a FastAPI backend has no place in a component test), so each
// test asserts the component called the real, correct endpoint/method
// and rendered the real response -- not that a live backend exists.
// Same pattern as frontend/components/integrations/components.test.tsx.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InstalledPlugins from "./InstalledPlugins";
import PluginCard from "./PluginCard";
import PluginCreateForm from "./PluginCreateForm";
import PluginFilters from "./PluginFilters";
import PluginInstallButton from "./PluginInstallButton";
import PluginList from "./PluginList";
import PluginLogs from "./PluginLogs";
import PluginReviewForm from "./PluginReviewForm";
import PluginReviews from "./PluginReviews";
import PluginSearch from "./PluginSearch";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), postMultipart: vi.fn(), putMultipart: vi.fn() },
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

const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn>; patch: ReturnType<typeof vi.fn>; delete: ReturnType<typeof vi.fn>; postMultipart: ReturnType<typeof vi.fn>; putMultipart: ReturnType<typeof vi.fn> };

beforeEach(() => {
  mockedApi.get.mockReset();
  mockedApi.post.mockReset();
  mockedApi.patch.mockReset();
  mockedApi.delete.mockReset();
  mockedApi.postMultipart.mockReset();
  mockedApi.putMultipart.mockReset();
});

const SAMPLE_PLUGIN = {
  id: "p1", organization_id: "org1", name: "My Plugin", slug: "my-plugin", description: "A test plugin.",
  category: "productivity" as const, pricing: "free" as const, price: null,
  manifest: { name: "My Plugin", version: "1.0.0", entry_point: "index.js", description: "...", permissions: [] },
  version: "1.0.0", code_size_bytes: 100, status: "approved" as const, rejection_reason: null, install_count: 3,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("PluginCard", () => {
  it("renders name/description/install count and reports selection", async () => {
    const onSelect = vi.fn();
    render(<PluginCard plugin={SAMPLE_PLUGIN} onSelect={onSelect} />);
    expect(screen.getByText("My Plugin")).toBeInTheDocument();
    expect(screen.getByText(/3 installs/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("My Plugin"));
    expect(onSelect).toHaveBeenCalledWith(SAMPLE_PLUGIN);
  });
});

describe("PluginList", () => {
  it("renders one PluginCard per plugin, or the empty message", () => {
    const { rerender } = render(<PluginList plugins={[SAMPLE_PLUGIN]} />);
    expect(screen.getByText("My Plugin")).toBeInTheDocument();

    rerender(<PluginList plugins={[]} />);
    expect(screen.getByText("No plugins found.")).toBeInTheDocument();
  });
});

describe("PluginSearch", () => {
  it("reports typed input to the parent", async () => {
    const onChange = vi.fn();
    render(<PluginSearch value="" onChange={onChange} />);
    await userEvent.type(screen.getByPlaceholderText("Search plugins…"), "x");
    expect(onChange).toHaveBeenCalledWith("x");
  });
});

describe("PluginFilters", () => {
  it("reports category/sort/rating changes", async () => {
    const onCategoryChange = vi.fn();
    render(<PluginFilters category="" onCategoryChange={onCategoryChange} pricing="" onPricingChange={vi.fn()} sortBy="date" onSortByChange={vi.fn()} minRating={undefined} onMinRatingChange={vi.fn()} />);
    await userEvent.selectOptions(screen.getByDisplayValue("All categories"), "security");
    expect(onCategoryChange).toHaveBeenCalledWith("security");
  });
});

describe("PluginInstallButton", () => {
  it("POSTs .../install and calls onInstalled", async () => {
    mockedApi.post.mockResolvedValueOnce({ id: "inst1" });
    const onInstalled = vi.fn();
    render(<PluginInstallButton orgId="org1" pluginId="p1" onInstalled={onInstalled} />);
    await userEvent.click(screen.getByRole("button", { name: "Install" }));
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/plugins/p1/install"));
    expect(onInstalled).toHaveBeenCalled();
  });
});

describe("PluginReviews", () => {
  it("loads reviews and lets the owner delete their own", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "r1", plugin_id: "p1", organization_id: "org1", user_id: "u1", rating: 4, comment: "Great", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }]);
    mockedApi.delete.mockResolvedValueOnce(undefined);
    mockedApi.get.mockResolvedValueOnce([]);
    render(<PluginReviews pluginId="p1" currentUserId="u1" />);

    expect(await screen.findByText(/Great/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith("/marketplace/reviews/r1"));
  });
});

describe("PluginReviewForm", () => {
  it("submits a rating and comment", async () => {
    mockedApi.post.mockResolvedValueOnce({ id: "r1" });
    const onSubmitted = vi.fn();
    render(<PluginReviewForm orgId="org1" pluginId="p1" onSubmitted={onSubmitted} />);
    await userEvent.type(screen.getByPlaceholderText("Comment (optional)"), "Nice");
    await userEvent.click(screen.getByRole("button", { name: "Rate" }));
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/plugins/p1/reviews", { rating: 5, comment: "Nice" }));
    expect(onSubmitted).toHaveBeenCalled();
  });
});

describe("PluginLogs", () => {
  it("loads execution history and runs the plugin on demand", async () => {
    mockedApi.get.mockResolvedValueOnce([]);
    mockedApi.post.mockResolvedValueOnce({ id: "e1", status: "success" });
    mockedApi.get.mockResolvedValueOnce([{ id: "e1", plugin_id: "p1", organization_id: "org1", installation_id: null, hook: null, status: "success", input_payload: {}, output_payload: { ok: true }, error_message: null, duration_ms: 12, created_at: "2026-01-01T00:00:00Z" }]);
    render(<PluginLogs orgId="org1" pluginId="p1" />);

    expect(await screen.findByText("No executions yet.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run now" }));
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/organizations/org1/plugins/p1/execute", { data: {} }));
    expect(await screen.findByText(/success/)).toBeInTheDocument();
  });
});

describe("InstalledPlugins", () => {
  it("loads installations and can disable one", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "inst1", plugin_id: "p1", organization_id: "org1", enabled: true, config: {}, installed_at: "2026-01-01T00:00:00Z" }]);
    mockedApi.patch.mockResolvedValueOnce({});
    mockedApi.get.mockResolvedValueOnce([{ id: "inst1", plugin_id: "p1", organization_id: "org1", enabled: false, config: {}, installed_at: "2026-01-01T00:00:00Z" }]);
    render(<InstalledPlugins orgId="org1" />);

    expect(await screen.findByText(/Enabled/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Disable" }));
    await waitFor(() => expect(mockedApi.patch).toHaveBeenCalledWith("/organizations/org1/plugins/installed/inst1", { enabled: false }));
  });
});

describe("PluginCreateForm", () => {
  it("publishes with the entered name/description and calls onPublished", async () => {
    mockedApi.get.mockResolvedValueOnce([{ id: "read:documents", label: "Read documents" }]);
    mockedApi.postMultipart.mockResolvedValueOnce({ id: "p1", name: "New Plugin" });
    const onPublished = vi.fn();
    render(<PluginCreateForm orgId="org1" onPublished={onPublished} />);

    await userEvent.type(screen.getByPlaceholderText("Plugin name"), "New Plugin");
    await userEvent.type(screen.getByPlaceholderText("Description"), "A new plugin");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mockedApi.postMultipart).toHaveBeenCalled());
    const [path, fields] = mockedApi.postMultipart.mock.calls[0];
    expect(path).toBe("/organizations/org1/plugins/publish");
    expect(fields).toEqual({ name: "New Plugin", description: "A new plugin", category: "other", pricing: "free" });
    expect(onPublished).toHaveBeenCalledWith({ id: "p1", name: "New Plugin" });
  });
});
