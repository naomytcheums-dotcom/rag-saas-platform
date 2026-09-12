"use client";

import { useState } from "react";
import { WidgetPicker } from "@/components/analytics/WidgetPicker";
import type { Widget } from "@/components/analytics/WidgetPicker";
import { useDashboards } from "@/lib/hooks/useDashboards";

interface DashboardBuilderProps {
  orgId: string;
}

export function DashboardBuilder({ orgId }: DashboardBuilderProps) {
  const { dashboards, loading, error, create, update, remove } = useDashboards(orgId);
  const [newName, setNewName] = useState("");
  const [pendingWidgets, setPendingWidgets] = useState<Widget[]>([]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await create({ name: newName.trim(), widgets: pendingWidgets });
    setNewName("");
    setPendingWidgets([]);
  };

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">New dashboard</h2>
        <div className="mt-3 flex gap-2">
          <input
            type="text" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Dashboard name"
            className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
          />
          <button type="button" onClick={() => void handleCreate()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
            Save
          </button>
        </div>
        <div className="mt-3">
          <WidgetPicker onAdd={(widget) => setPendingWidgets((prev) => [...prev, widget])} />
        </div>
        {pendingWidgets.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-2">
            {pendingWidgets.map((w, i) => (
              <li key={i} className="rounded-full bg-surface-muted px-3 py-1 text-xs text-foreground-muted">{w.label} ({w.chart})</li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {dashboards.map((dashboard) => (
          <div key={dashboard.id} className="flex items-center justify-between rounded-xl border border-border bg-surface p-4">
            <div>
              <p className="text-sm font-medium text-foreground">{dashboard.name}{dashboard.is_default && <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-xs text-accent">Default</span>}</p>
              <p className="text-xs text-foreground-muted">{Array.isArray(dashboard.widgets) ? dashboard.widgets.length : 0} widget(s)</p>
            </div>
            <div className="flex gap-2">
              {!dashboard.is_default && (
                <button type="button" onClick={() => void update(dashboard.id, { is_default: true })} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground-muted hover:bg-surface-muted">
                  Set as default
                </button>
              )}
              <button type="button" onClick={() => void remove(dashboard.id)} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground-muted hover:text-danger">
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
