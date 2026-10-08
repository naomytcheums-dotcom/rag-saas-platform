// Hardening Mission (§14/§26) -- render/interaction tests for the agent
// Factory page and for the contract fixes on the "new agent" page. The
// backend client, router, org hook and i18n are mocked (no network); the
// assertions are about what the pages SEND and where they GO.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const get = vi.fn();
const post = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));
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
  return { api: { get: (...args: unknown[]) => get(...args), post: (...args: unknown[]) => post(...args) }, ApiError };
});

import { ApiError } from "@/lib/api";
import AgentFactoryPage from "./factory/page";
import NewAgentPage from "./new/page";

const BLUEPRINT = {
  profile: "support",
  rationale: ["profile 'support': customer-facing Q&A"],
  retrieval_config: { strategy: "hybrid", top_k: 5 },
  agent: { name: "Helpdesk", system_prompt: "x", tools: [{ name: "search_knowledge_base" }] },
};

beforeEach(() => {
  push.mockReset();
  get.mockReset();
  post.mockReset();
});

describe("Agent Factory page", () => {
  it("previews the blueprint (dry run) and only then offers to create the agent", async () => {
    post.mockResolvedValueOnce({ blueprint: BLUEPRINT, problems: [], deployable: true });
    render(<AgentFactoryPage />);

    expect(screen.queryByText("agents.factory.deploy")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/agents.factory.requirement/), "Customer support FAQ assistant for our helpdesk");
    await userEvent.click(screen.getByText("agents.factory.preview"));

    await waitFor(() => expect(screen.getByText("agents.factory.deploy")).toBeEnabled());
    expect(post).toHaveBeenCalledWith("/organizations/org-1/factory/blueprint", { requirement: "Customer support FAQ assistant for our helpdesk", name: null });
    expect(screen.getByText(/profile 'support'/)).toBeInTheDocument();
    expect(screen.getByText("search_knowledge_base")).toBeInTheDocument();
  });

  it("shows the validation problems and keeps the create button disabled when the blueprint is not deployable", async () => {
    post.mockResolvedValueOnce({ blueprint: BLUEPRINT, problems: ["tools: Unknown tool: 'x'"], deployable: false });
    render(<AgentFactoryPage />);

    await userEvent.type(screen.getByLabelText(/agents.factory.requirement/), "Customer support FAQ assistant for our helpdesk");
    await userEvent.click(screen.getByText("agents.factory.preview"));

    await waitFor(() => expect(screen.getByText(/Unknown tool/)).toBeInTheDocument());
    expect(screen.getByText("agents.factory.deploy")).toBeDisabled();
  });

  it("creates the agent through the deploy endpoint and returns to the agent list", async () => {
    post.mockResolvedValueOnce({ blueprint: BLUEPRINT, problems: [], deployable: true }).mockResolvedValueOnce({ agent_id: "a1" });
    render(<AgentFactoryPage />);

    await userEvent.type(screen.getByLabelText(/agents.factory.requirement/), "Customer support FAQ assistant for our helpdesk");
    await userEvent.click(screen.getByText("agents.factory.preview"));
    await userEvent.click(await screen.findByText("agents.factory.deploy"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard/agents"));
    expect(post).toHaveBeenLastCalledWith("/organizations/org-1/factory/deploy", expect.objectContaining({ requirement: expect.any(String) }));
  });

  it("surfaces every problem from a 422 list-style error", async () => {
    post.mockRejectedValueOnce(new ApiError(422, ["requirement must be longer", "name: required"]));
    render(<AgentFactoryPage />);

    await userEvent.type(screen.getByLabelText(/agents.factory.requirement/), "Customer support FAQ assistant for our helpdesk");
    await userEvent.click(screen.getByText("agents.factory.preview"));

    expect(await screen.findByRole("alert")).toHaveTextContent("requirement must be longer · name: required");
  });
});

describe("New agent page contract", () => {
  it("lists the tools the BACKEND offers and sends them as {name, enabled, config} objects with model/temperature in model_config", async () => {
    get.mockResolvedValueOnce({ search_knowledge_base: {}, web_search: {} });
    post.mockResolvedValueOnce({ id: "a1" });
    render(<NewAgentPage />);

    await userEvent.click(await screen.findByLabelText("search_knowledge_base"));
    await userEvent.type(screen.getByLabelText(/agents.new.name/), "Bot");
    await userEvent.type(screen.getByLabelText(/agents.new.system_prompt/), "You help.");
    await userEvent.click(screen.getByText("agents.new.submit"));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [url, payload] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(url).toBe("/organizations/org-1/agents");
    expect(payload.tools).toEqual([{ name: "search_knowledge_base", enabled: true, config: {} }]);
    expect(payload.model_config).toEqual({ model: "claude-sonnet-5-5", temperature: 0.7 });
    expect(payload).not.toHaveProperty("max_iterations");
    expect(payload).not.toHaveProperty("model");
    expect(get).toHaveBeenCalledWith("/tools/available");
  });

  it("goes back to the agent list after creating (there is no per-agent page to open)", async () => {
    get.mockResolvedValueOnce({});
    post.mockResolvedValueOnce({ id: "a1" });
    render(<NewAgentPage />);

    await userEvent.type(screen.getByLabelText(/agents.new.name/), "Bot");
    await userEvent.type(screen.getByLabelText(/agents.new.system_prompt/), "You help.");
    await userEvent.click(screen.getByText("agents.new.submit"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard/agents"));
  });

  it("links to the Factory", async () => {
    get.mockResolvedValueOnce({});
    render(<NewAgentPage />);
    expect(screen.getByText("agents.factory.link").closest("a")).toHaveAttribute("href", "/dashboard/agents/factory");
  });
});
