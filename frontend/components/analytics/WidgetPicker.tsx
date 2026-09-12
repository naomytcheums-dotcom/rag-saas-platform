"use client";

import { useState } from "react";

export interface Widget {
  metric: string;
  chart: "line" | "bar" | "pie" | "area";
  label: string;
}

const AVAILABLE_METRICS = [
  { value: "product.usage", label: "Product usage" },
  { value: "product.adoption", label: "Feature adoption" },
  { value: "product.engagement", label: "Daily active users" },
  { value: "technical.llm_usage", label: "LLM usage" },
];

interface WidgetPickerProps {
  onAdd: (widget: Widget) => void;
}

export function WidgetPicker({ onAdd }: WidgetPickerProps) {
  const [metric, setMetric] = useState(AVAILABLE_METRICS[0].value);
  const [chart, setChart] = useState<Widget["chart"]>("line");

  const add = () => {
    const found = AVAILABLE_METRICS.find((m) => m.value === metric);
    onAdd({ metric, chart, label: found?.label ?? metric });
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface p-4">
      <select value={metric} onChange={(e) => setMetric(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-foreground">
        {AVAILABLE_METRICS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
      </select>
      <select value={chart} onChange={(e) => setChart(e.target.value as Widget["chart"])} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-foreground">
        <option value="line">Line</option>
        <option value="bar">Bar</option>
        <option value="area">Area</option>
        <option value="pie">Pie</option>
      </select>
      <button type="button" onClick={add} className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover">
        Add widget
      </button>
    </div>
  );
}
