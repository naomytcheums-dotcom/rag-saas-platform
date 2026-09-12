// Partie 21 -- real render/interaction tests for the A/B testing
// components. `@/lib/api` is mocked (no real network call in a
// component test). Placed alongside the components, same convention
// as plugins/integrations/whitelabel/analytics -- not at the spec's
// own suggested tests/frontend/ab-tests/ path, which sits outside
// vitest's project root (frontend/) and would never actually run.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ABTestChart } from "./ABTestChart";
import { ABTestFilters } from "./ABTestFilters";
import { ABTestStatistics } from "./ABTestStatistics";
import { ABTestStatusBadge } from "./ABTestStatusBadge";
import { ABTestTrafficSplit } from "./ABTestTrafficSplit";
import { ABTestVariantSelector } from "./ABTestVariantSelector";
import type { ABTestMetricResult } from "@/lib/services/ab-tests";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), postMultipart: vi.fn(), putMultipart: vi.fn(), postFile: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
    }
  },
  fileUrl: (path: string) => `http://localhost:8000${path}`,
}));

describe("ABTestStatusBadge", () => {
  it("renders the real status text", () => {
    render(<ABTestStatusBadge status="running" />);
    expect(screen.getByText("running")).toBeInTheDocument();
  });
});

describe("ABTestTrafficSplit", () => {
  it("shows the A/B percentage split and calls onChange", async () => {
    const onChange = vi.fn();
    render(<ABTestTrafficSplit value={70} onChange={onChange} />);
    expect(screen.getByText("70% A / 30% B")).toBeInTheDocument();
  });
});

describe("ABTestVariantSelector", () => {
  it("calls onChange as the textarea is edited", async () => {
    const onChange = vi.fn();
    render(<ABTestVariantSelector label="Variant A" value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole("textbox"), "x");
    expect(onChange).toHaveBeenCalled();
  });
});

describe("ABTestFilters", () => {
  it("lists every real status plus 'all'", () => {
    render(<ABTestFilters status="all" onStatusChange={vi.fn()} />);
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(5);
  });
});

describe("ABTestChart", () => {
  it("renders a chart container for the two real variant means", () => {
    const { container } = render(<ABTestChart meanA={1.0} meanB={2.0} label="conversion_rate" />);
    expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
  });
});

describe("ABTestStatistics", () => {
  const RESULT: ABTestMetricResult = {
    variant_a: { count: 10, mean: 1.0, std_dev: 0.5 },
    variant_b: { count: 10, mean: 2.0, std_dev: 0.5 },
    lift: 1.0, p_value: 0.01, significant: true,
    confidence_interval_lower: 0.5, confidence_interval_upper: 1.5,
    effect_size_cohens_d: 2.0, statistical_power: 0.95, min_sample_size_reached: true,
  };

  it("shows a Significant badge when significant is true", () => {
    render(<ABTestStatistics metric="conversion_rate" result={RESULT} />);
    expect(screen.getByText("Significant")).toBeInTheDocument();
  });

  it("shows real, honest em-dashes for null statistics", () => {
    const sparse: ABTestMetricResult = {
      variant_a: { count: 1, mean: 1.0, std_dev: 0 }, variant_b: { count: 1, mean: 2.0, std_dev: 0 },
      lift: 1.0, p_value: null, significant: null,
      confidence_interval_lower: null, confidence_interval_upper: null,
      effect_size_cohens_d: null, statistical_power: null, min_sample_size_reached: false,
    };
    render(<ABTestStatistics metric="conversion_rate" result={sparse} />);
    expect(screen.queryByText("Significant")).not.toBeInTheDocument();
    expect(screen.queryByText("Not significant")).not.toBeInTheDocument(); // significant is null, not false -- neither badge shown
  });
});
