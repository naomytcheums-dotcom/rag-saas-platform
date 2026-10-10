// Specs 6.2.12, 11.2.6: the quality scores page shows the averages, the per-answer scores and a disabled notice.
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
const currentOrg = { org: { id: "org-1" } };
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => currentOrg }));
vi.mock("@/components/LoadingState", () => ({ default: () => <p>loading</p> }));
vi.mock("@/lib/download", () => ({ downloadWithAuth: vi.fn() }));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) { super(String(detail)); this.status = status; this.detail = detail; }
  }
  return { api: { get: (...a: unknown[]) => get(...a) }, ApiError };
});

import QualityScoresPage from "./page";

const metrics = { avg_confidence_score: 0.8, avg_groundedness_score: 0.9, avg_faithfulness_score: 0.85, avg_hallucination_score: 0.05, citation_rate: 0.7, supported_claims_rate: 0.9, contradiction_rate: 0.1, total_responses: 12 };
const item = { id: "r1", query: "What is the refund policy?", answer: "30 days", created_at: "2026-10-01T10:00:00Z", confidence_score: 0.77, groundedness_score: 0.66, faithfulness_score: 0.55, hallucination_score: 0.11, has_contradictions: true, has_unsupported_claims: false };

function answer(enabled: boolean) {
  return (path: string) => {
    if (path.includes("/dashboard")) return Promise.resolve({ enabled, metrics: enabled ? metrics : null, status_distribution: { low: 1, medium: 2, high: 9 } });
    if (path.includes("/trends")) return Promise.resolve({ metric: "groundedness_score", points: [{ date: "2026-10-01", value: 0.9 }] });
    return Promise.resolve({ items: [item], total: 1, limit: 25, offset: 0 });
  };
}

beforeEach(() => { get.mockReset(); });

describe("Quality scores page", () => {
  it("shows the averages and one row of per-answer scores", async () => {
    get.mockImplementation(answer(true));
    render(<QualityScoresPage />);
    expect(await screen.findByText("What is the refund policy?")).toBeInTheDocument();
    expect(screen.getByText("77 %")).toBeInTheDocument();
    expect(screen.getByText("quality_scores.contradiction")).toBeInTheDocument();
  });

  it("explains that the scores are off when the feature is disabled", async () => {
    get.mockImplementation(answer(false));
    render(<QualityScoresPage />);
    await waitFor(() => expect(screen.getByText("quality_scores.disabled")).toBeInTheDocument());
  });
});
