// Partie 24 -- real render/interaction tests for the fine-tuning
// components. `@/lib/api` is mocked (no real network call in a
// component test) -- same convention as media/autonomous-agents:
// tests/frontend/fine-tuning/ (this part's own literal spec
// suggestion) sits outside vitest's project root and would never
// actually run.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DatasetCard } from "./DatasetCard";
import { JobCard } from "./JobCard";
import { JobMetrics } from "./JobMetrics";
import { ModelDeploy } from "./ModelDeploy";
import type { FineTunedModel, FineTuningDataset, FineTuningJob } from "@/lib/services/fine-tuning";

const mockApi = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), postMultipart: vi.fn(), putMultipart: vi.fn(), postFile: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: mockApi,
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
    }
  },
  fileUrl: (path: string) => `http://localhost:8000${path}`,
}));

const BASE_DATASET: FineTuningDataset = {
  id: "d1", organization_id: "org-1", created_by: null, name: "Support chats", description: null, dataset_type: "llm",
  format: "jsonl", size: 20480, status: "ready", validation_errors: null, example_count: 250, created_at: "2026-01-01T00:00:00Z",
};

const BASE_JOB: FineTuningJob = {
  id: "j1", organization_id: "org-1", dataset_id: "d1", created_by: null, name: "Support tone", base_model: "gpt-4o-mini-2024-07-18",
  provider: "openai", status: "running", hyperparameters: {}, metrics: { trained_tokens: 12000 }, provider_job_id: "ftjob-1",
  error_message: null, started_at: "2026-01-01T00:00:00Z", completed_at: null, created_at: "2026-01-01T00:00:00Z",
};

const BASE_MODEL: FineTunedModel = {
  id: "m1", organization_id: "org-1", job_id: "j1", name: "Support tone", provider: "openai",
  provider_model_id: "ft:gpt-4o-mini-2024-07-18:acme::abc123", base_model: "gpt-4o-mini-2024-07-18", status: "available",
  deployed: false, metrics: {}, created_at: "2026-01-01T00:00:00Z",
};

describe("DatasetCard", () => {
  it("shows the real name, status, and example count", () => {
    render(<DatasetCard dataset={BASE_DATASET} onDelete={vi.fn()} onValidated={vi.fn()} />);
    expect(screen.getByText("Support chats")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("250 examples")).toBeInTheDocument();
  });

  it("shows real validation errors when present", () => {
    render(<DatasetCard dataset={{ ...BASE_DATASET, status: "error", validation_errors: [{ line: 4, error: "invalid JSON" }] }} onDelete={vi.fn()} onValidated={vi.fn()} />);
    expect(screen.getByText("Line 4: invalid JSON")).toBeInTheDocument();
  });

  it("calls onDelete with the real dataset id", async () => {
    const onDelete = vi.fn();
    render(<DatasetCard dataset={BASE_DATASET} onDelete={onDelete} onValidated={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith("d1");
  });
});

describe("JobCard", () => {
  it("shows the real job name, status, provider, and base model", () => {
    render(<JobCard job={BASE_JOB} />);
    expect(screen.getByText("Support tone")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini-2024-07-18")).toBeInTheDocument();
  });

  it("shows the real error message for a failed job", () => {
    render(<JobCard job={{ ...BASE_JOB, status: "failed", error_message: "training file contained invalid examples" }} />);
    expect(screen.getByText("training file contained invalid examples")).toBeInTheDocument();
  });
});

describe("JobMetrics", () => {
  it("renders every real metric key/value pair", () => {
    render(<JobMetrics job={BASE_JOB} />);
    expect(screen.getByText("trained_tokens")).toBeInTheDocument();
    expect(screen.getByText("12000")).toBeInTheDocument();
  });

  it("shows a real, honest empty state with no metrics yet", () => {
    render(<JobMetrics job={{ ...BASE_JOB, metrics: {} }} />);
    expect(screen.getByText("No metrics yet.")).toBeInTheDocument();
  });
});

describe("ModelDeploy", () => {
  it("shows Deploy for an undeployed, available model and calls onDeploy", async () => {
    const onDeploy = vi.fn();
    render(<ModelDeploy model={BASE_MODEL} onDeploy={onDeploy} onUndeploy={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Deploy" }));
    expect(onDeploy).toHaveBeenCalledWith("m1");
  });

  it("shows Undeploy for a deployed model", () => {
    render(<ModelDeploy model={{ ...BASE_MODEL, deployed: true }} onDeploy={vi.fn()} onUndeploy={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Undeploy" })).toBeInTheDocument();
  });

  it("shows a real, honest disabled state for a deprecated model", () => {
    render(<ModelDeploy model={{ ...BASE_MODEL, status: "deprecated" }} onDeploy={vi.fn()} onUndeploy={vi.fn()} />);
    expect(screen.getByText(/Deprecated/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
