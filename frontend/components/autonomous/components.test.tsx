// Partie 23 -- real render/interaction tests for the autonomous agent
// components. `@/lib/api` is mocked (no real network call in a
// component test) -- same convention as media/ab-tests: tests/frontend/
// (this part's own literal spec suggestion) sits outside vitest's
// project root and would never actually run.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AgentCard } from "./AgentCard";
import { AgentRunPanel } from "./AgentRunPanel";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { AgentStepView } from "./AgentStepView";
import type { AgentStep, AutonomousAgent } from "@/lib/services/autonomous-agents";

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

const BASE_AGENT: AutonomousAgent = {
  id: "11111111-1111-1111-1111-111111111111", organization_id: "org-1", created_by: null,
  name: "Researcher", description: null, goal: "Find real facts about a topic", status: "idle",
  max_steps: 20, current_step: 0, tools_enabled: [], guardrails: {}, memory_config: {}, error: null,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

describe("AgentStatusBadge", () => {
  it("renders the real status text", () => {
    render(<AgentStatusBadge status="executing" />);
    expect(screen.getByText("executing")).toBeInTheDocument();
  });
});

describe("AgentCard", () => {
  it("shows the name, goal, status, and step progress", () => {
    render(<AgentCard agent={{ ...BASE_AGENT, current_step: 3, max_steps: 10 }} />);
    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText("Find real facts about a topic")).toBeInTheDocument();
    expect(screen.getByText("idle")).toBeInTheDocument();
    expect(screen.getByText("Step 3/10")).toBeInTheDocument();
  });
});

describe("AgentRunPanel", () => {
  it("shows Run for an idle agent and calls onRun", async () => {
    const onRun = vi.fn();
    render(<AgentRunPanel agent={BASE_AGENT} onRun={onRun} onPause={vi.fn()} onResume={vi.fn()} onStop={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onRun).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Pause" })).not.toBeInTheDocument();
  });

  it("shows Pause and Stop for an executing agent", () => {
    render(<AgentRunPanel agent={{ ...BASE_AGENT, status: "executing" }} onRun={vi.fn()} onPause={vi.fn()} onResume={vi.fn()} onStop={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run" })).not.toBeInTheDocument();
  });

  it("shows Resume for a paused agent", () => {
    render(<AgentRunPanel agent={{ ...BASE_AGENT, status: "paused" }} onRun={vi.fn()} onPause={vi.fn()} onResume={vi.fn()} onStop={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });
});

describe("AgentStepView", () => {
  const BASE_STEP: AgentStep = {
    id: "s1", plan_id: "p1", step_number: 1, action: "calculator", parameters: { description: "Compute 2+2" },
    result: { output: "4" }, status: "completed", error: null, started_at: null, completed_at: null,
  };

  it("renders the real step number, action, description, and result", () => {
    render(<AgentStepView step={BASE_STEP} />);
    expect(screen.getByText("#1 — calculator")).toBeInTheDocument();
    expect(screen.getByText("Compute 2+2")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders a real error for a failed step", () => {
    render(<AgentStepView step={{ ...BASE_STEP, status: "failed", error: "a real tool outage", result: null }} />);
    expect(screen.getByText("a real tool outage")).toBeInTheDocument();
  });
});
