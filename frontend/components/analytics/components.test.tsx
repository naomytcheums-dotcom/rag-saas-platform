// Partie 20 -- real render/interaction tests for the analytics
// components. `@/lib/api` is mocked (no real network call in a
// component test). Placed alongside the components, same convention
// as plugins/integrations/whitelabel -- not at the spec's own
// suggested tests/frontend/analytics/ path, which sits outside
// vitest's project root (frontend/) and would never actually run.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DateRangePicker } from "./DateRangePicker";
import { MetricCard } from "./MetricCard";
import { MetricChart } from "./MetricChart";
import { MetricTable } from "./MetricTable";
import { SegmentSelector } from "./SegmentSelector";
import { WidgetPicker } from "./WidgetPicker";

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

describe("MetricCard", () => {
  it("renders the label and value", () => {
    render(<MetricCard label="MRR" value="$1,000" />);
    expect(screen.getByText("MRR")).toBeInTheDocument();
    expect(screen.getByText("$1,000")).toBeInTheDocument();
  });

  it("shows an em dash for a null value, not the literal word null", () => {
    render(<MetricCard label="LTV" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("appends a suffix only when a real value is present", () => {
    render(<MetricCard label="Retention" value={82} suffix="%" />);
    expect(screen.getByText("82%")).toBeInTheDocument();
  });
});

describe("MetricChart", () => {
  it("shows a real empty state instead of an empty chart for no data", () => {
    render(<MetricChart data={[]} />);
    expect(screen.getByText("No data for this period.")).toBeInTheDocument();
  });

  it("renders a chart container when given real data", () => {
    const { container } = render(<MetricChart data={[{ label: "Mon", value: 5 }, { label: "Tue", value: 8 }]} type="bar" />);
    expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
  });
});

describe("MetricTable", () => {
  it("shows a real empty state with no rows", () => {
    render(<MetricTable columns={["Metric", "Total"]} rows={[]} />);
    expect(screen.getByText("No data for this period.")).toBeInTheDocument();
  });

  it("renders every real row and column", () => {
    render(<MetricTable columns={["Metric", "Total"]} rows={[["documents", 12], ["agents", 3]]} />);
    expect(screen.getByText("documents")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("agents")).toBeInTheDocument();
  });
});

describe("DateRangePicker", () => {
  it("calls onChange with the selected range", async () => {
    const onChange = vi.fn();
    render(<DateRangePicker value="30d" onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "90d");
    expect(onChange).toHaveBeenCalledWith("90d");
  });
});

describe("SegmentSelector", () => {
  it("only offers the one real, working segment today", () => {
    render(<SegmentSelector value="all" onChange={vi.fn()} />);
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("All users");
  });
});

describe("WidgetPicker", () => {
  it("calls onAdd with the selected metric and chart type", async () => {
    const onAdd = vi.fn();
    render(<WidgetPicker onAdd={onAdd} />);
    await userEvent.click(screen.getByRole("button", { name: "Add widget" }));
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ metric: "product.usage", chart: "line" }));
  });
});
