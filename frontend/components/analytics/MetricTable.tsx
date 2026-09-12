"use client";

interface MetricTableProps {
  columns: string[];
  rows: (string | number)[][];
}

export function MetricTable({ columns, rows }: MetricTableProps) {
  if (rows.length === 0) {
    return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No data for this period.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase text-foreground-muted">
            {columns.map((col) => <th key={col} className="px-4 py-3">{col}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {row.map((cell, j) => <td key={j} className="px-4 py-3 text-foreground">{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
