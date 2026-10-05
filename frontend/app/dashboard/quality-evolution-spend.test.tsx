// Hardening Mission (§13/§12/§6, §26) -- the UI for Guardian (quality alerts),
// the retrieval Evolution cycle (run / apply / roll back) and the spending
// limits form. Backend client, org hook and i18n are mocked: the assertions are
// about what each screen sends and shows.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();

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
  return {
    api: {
      get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a),
      patch: (...a: unknown[]) => patch(...a), delete: (...a: unknown[]) => del(...a),
    },
    ApiError,
  };
});

import QualityAlertsPage from "./quality/page";
import EvolutionPage from "./eval/evolution/page";
import SpendLimits from "@/components/SpendLimits";

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
  del.mockReset();
});

describe("Quality alerts page (Guardian)", () => {
  function mockLoad(rules: unknown[] = [], history: unknown[] = []) {
    get.mockImplementation(async (url: string) => {
      if (url.endsWith("/metrics")) return { metrics: ["recall_at_5", "mrr"] };
      if (url.endsWith("/rules")) return rules;
      if (url.endsWith("/history")) return history;
      return [];
    });
  }

  it("offers only the RAG-quality metrics the backend returns and creates a rule with a numeric threshold", async () => {
    mockLoad();
    post.mockResolvedValue({});
    render(<QualityAlertsPage />);

    await screen.findByText("quality.no_rules");
    expect(screen.getByRole("option", { name: "recall_at_5" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/quality.name/), "Recall guard");
    await userEvent.click(screen.getByText("quality.create"));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/quality-alerts/rules", { name: "Recall guard", metric: "recall_at_5", operator: "lt", threshold: 0.8 }));
  });

  it("shows the explained alert history", async () => {
    mockLoad([], [{ id: "h1", rule_id: "r1", triggered_at: "2026-10-02T10:00:00Z", value_at_trigger: 0.4, message: "Alert 'Recall guard': recall_at_5=0.4. Autopsy of job J: retrieval=3. Suggested action: ..." }]);
    render(<QualityAlertsPage />);
    expect(await screen.findByText(/Autopsy of job J: retrieval=3/)).toBeInTheDocument();
  });

  it("checks a rule now and reports honestly when nothing has been measured yet", async () => {
    mockLoad([{ id: "r1", name: "Recall guard", metric: "recall_at_5", operator: "lt", threshold: 0.8, enabled: true }]);
    post.mockResolvedValue({ current_value: null, would_trigger: false });
    render(<QualityAlertsPage />);

    await userEvent.click(await screen.findByText("quality.test"));

    expect(await screen.findByText(/quality.no_measurement/)).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/organizations/org-1/quality-alerts/rules/r1/test", {});
  });

  it("deletes a rule and reloads", async () => {
    mockLoad([{ id: "r1", name: "Recall guard", metric: "recall_at_5", operator: "lt", threshold: 0.8, enabled: true }]);
    del.mockResolvedValue(undefined);
    render(<QualityAlertsPage />);

    await userEvent.click(await screen.findByText("quality.delete"));

    await waitFor(() => expect(del).toHaveBeenCalledWith("/organizations/org-1/quality-alerts/rules/r1"));
  });
});

describe("Evolution page", () => {
  const CYCLE = {
    decision: "candidate_recommended", target_metric: "recall_at_5", corpus_constrained: false, recommended_config: { top_k: 10 },
    candidates: [
      { config: { top_k: 10 }, job_id: "j1", accepted: true, target_delta: 0.12, reasons: [] },
      { config: { strategy: "hybrid_reranked" }, job_id: "j2", accepted: false, target_delta: 0.2, reasons: ["mrr regressed by -0.1200 (allowed: 0.0500)"] },
    ],
  };

  function mockLists() {
    get.mockImplementation(async (url: string) => (url.endsWith("/datasets") ? { items: [{ id: "ds1", name: "FAQ set" }] } : [{ id: "ag1", name: "Support bot" }]));
  }

  it("runs the comparison on the chosen dataset and shows every candidate with its delta and rejection reason", async () => {
    mockLists();
    post.mockResolvedValueOnce(CYCLE);
    render(<EvolutionPage />);

    await userEvent.click(await screen.findByText("evolution.run"));

    expect(await screen.findByText("evolution.decision_recommended")).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/organizations/org-1/evolution/retrieval/run", { dataset_id: "ds1", target_metric: "recall_at_5" });
    expect(screen.getByText("+0.120")).toBeInTheDocument();
    expect(screen.getByText(/mrr regressed by -0.1200/)).toBeInTheDocument();
    expect(screen.getByText("evolution.accepted")).toBeInTheDocument();
    expect(screen.getByText("evolution.rejected")).toBeInTheDocument();
  });

  it("applies the recommended setting only on an explicit click, then offers a one-click undo that restores the previous config", async () => {
    mockLists();
    post.mockResolvedValueOnce(CYCLE).mockResolvedValueOnce({ previous: { top_k: 5 }, current: { top_k: 10 } }).mockResolvedValueOnce({ previous: { top_k: 10 }, current: { top_k: 5 } });
    render(<EvolutionPage />);

    await userEvent.click(await screen.findByText("evolution.run"));
    expect(post).toHaveBeenCalledTimes(1); // nothing applied by running the comparison

    await userEvent.click(await screen.findByText("evolution.apply"));
    await waitFor(() => expect(post).toHaveBeenLastCalledWith("/organizations/org-1/agents/ag1/retrieval-config/apply", { config: { top_k: 10 }, replace: false }));
    expect(await screen.findByText("evolution.applied")).toBeInTheDocument();

    await userEvent.click(screen.getByText("evolution.rollback"));
    await waitFor(() => expect(post).toHaveBeenLastCalledWith("/organizations/org-1/agents/ag1/retrieval-config/apply", { config: { top_k: 5 }, replace: true }));
    expect(await screen.findByText("evolution.rolled_back")).toBeInTheDocument();
  });

  it("does not offer to apply anything when no candidate was good enough", async () => {
    mockLists();
    post.mockResolvedValueOnce({ ...CYCLE, decision: "baseline_kept", recommended_config: null });
    render(<EvolutionPage />);

    await userEvent.click(await screen.findByText("evolution.run"));

    expect(await screen.findByText("evolution.decision_kept")).toBeInTheDocument();
    expect(screen.queryByText("evolution.apply")).not.toBeInTheDocument();
  });

  it("tells the user to create a dataset first when there is none", async () => {
    get.mockImplementation(async (url: string) => (url.endsWith("/datasets") ? { items: [] } : []));
    render(<EvolutionPage />);
    expect(await screen.findByText("evolution.no_datasets")).toBeInTheDocument();
    expect(screen.queryByText("evolution.run")).not.toBeInTheDocument();
  });
});

describe("SpendLimits", () => {
  it("loads the current caps and saves them; an emptied field is sent as an explicit null (clears the cap)", async () => {
    get.mockResolvedValueOnce({ daily_credit_limit: 500, monthly_credit_limit: 10000 });
    patch.mockResolvedValue({});
    render(<SpendLimits orgId="org-1" canEdit />);

    const daily = await screen.findByLabelText(/spend.daily/);
    await waitFor(() => expect(daily).toHaveValue(500));
    await userEvent.clear(screen.getByLabelText(/spend.monthly/));
    await userEvent.click(screen.getByText("spend.save"));

    await waitFor(() => expect(patch).toHaveBeenCalledWith("/organizations/org-1/settings", { daily_credit_limit: 500, monthly_credit_limit: null }));
    expect(await screen.findByText("spend.saved")).toBeInTheDocument();
  });

  it("is read-only for anyone who is not the Owner (no save button, disabled inputs)", async () => {
    get.mockResolvedValueOnce({ daily_credit_limit: null, monthly_credit_limit: null });
    render(<SpendLimits orgId="org-1" canEdit={false} />);

    expect(await screen.findByLabelText(/spend.daily/)).toBeDisabled();
    expect(screen.queryByText("spend.save")).not.toBeInTheDocument();
    expect(within(document.body).queryByRole("alert")).not.toBeInTheDocument();
  });
});
