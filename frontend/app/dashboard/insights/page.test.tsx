// Specs 11.2.x: the insights page shows the success rate, most asked and failed questions, documentation gaps and document usage.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();

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
  return { api: { get: (...a: unknown[]) => get(...a) }, ApiError };
});

import { ApiError } from "@/lib/api";
import InsightsPage from "./page";

function answer(path: string) {
  if (path.includes("most-asked")) return { items: [{ question: "How to export invoices?", count: 3 }] };
  if (path.includes("failed-questions")) return { items: [{ question: "Where is my contract?", reasons: ["no_answer"] }] };
  if (path.includes("documentation-gaps")) return { items: [{ suggested_topic: "invoices, export", times_asked: 3, example_questions: ["How to export invoices?"], related_documents: [], status: "missing" }] };
  if (path.includes("documents/top")) return { items: [{ document_id: "d1", name: "Handbook.pdf", citations: 5, average_relevance: 0.9 }] };
  if (path.includes("documents/worst")) return { items: [{ document_id: "d2", name: "Misc.pdf", citations: 2, average_relevance: 0.1 }] };
  if (path.includes("retrieval-success")) return { answered_questions: 4, refused: 1, success_rate: 0.75 };
  return { negative_feedback: 2, by_category: { RETRIEVAL_FAILURE: 2 } };
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(answer(path)));
});

describe("InsightsPage", () => {
  it("renders every section from the API", async () => {
    render(<InsightsPage />);
    expect(await screen.findByText("75 %")).toBeInTheDocument();
    expect(screen.getByText(/How to export invoices\?/, { selector: "li" })).toBeInTheDocument();
    expect(screen.getByText(/Where is my contract\?/)).toBeInTheDocument();
    expect(screen.getByText("invoices, export")).toBeInTheDocument();
    expect(screen.getByText(/Handbook\.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/Misc\.pdf/)).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/organizations/org-1/insights/most-asked?days=30");
  });

  it("reloads when the period changes", async () => {
    render(<InsightsPage />);
    await screen.findByText("75 %");
    await userEvent.selectOptions(screen.getByLabelText("insights.period"), "90");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/organizations/org-1/insights/most-asked?days=90"));
  });

  it("shows the server error", async () => {
    get.mockRejectedValue(new ApiError(403, "Forbidden"));
    render(<InsightsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Forbidden");
  });
});
