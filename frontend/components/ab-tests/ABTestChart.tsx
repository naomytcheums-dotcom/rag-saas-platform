"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface ABTestChartProps {
  meanA: number;
  meanB: number;
  label: string;
}

export function ABTestChart({ meanA, meanB, label }: ABTestChartProps) {
  const data = [{ name: "Variant A", value: meanA }, { name: "Variant B", value: meanB }];
  return (
    <div>
      <p className="text-xs font-medium uppercase text-foreground-muted">{label}</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="value" fill="#f5842a" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
