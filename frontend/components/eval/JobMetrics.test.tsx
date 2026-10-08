import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvalJob } from "@/lib/services/eval";
import { JobMetrics } from "./JobMetrics";

function makeJob(overrides: Partial<EvalJob> = {}): EvalJob {
  return {
    id: "job-1",
    dataset_id: "dataset-1",
    question_set_id: null,
    agent_id: null,
    model_config: {},
    status: "running",
    progress: 0,
    total_questions: 12,
    completed_questions: 0,
    results: null,
    error: null,
    created_by: null,
    created_at: "2026-10-08T00:00:00Z",
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

describe("evaluation job metrics", () => {
  it("does not report pending results as zero failures or completed questions", () => {
    render(<JobMetrics job={makeJob()} />);

    expect(screen.getByText("Succeeded").nextElementSibling).toHaveTextContent("—");
    expect(screen.getByText("Failed").nextElementSibling).toHaveTextContent("—");
  });

  it("uses completed API results when they are available", () => {
    render(
      <JobMetrics
        job={makeJob({
          id: "job-2",
          status: "completed",
          progress: 100,
          completed_questions: 8,
          results: { result_ids: [], total_questions: 12, completed_questions: 8, failed_questions: 3 },
        })}
      />,
    );

    expect(screen.getByText("Succeeded").nextElementSibling).toHaveTextContent("5");
    expect(screen.getByText("Failed").nextElementSibling).toHaveTextContent("3");
  });
});
