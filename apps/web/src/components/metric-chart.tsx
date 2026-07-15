"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SystemSummary } from "@/lib/data-schema";
import { labelSystem, percent } from "@/lib/utils";

export function MetricChart({
  systems,
  surface,
}: {
  systems: SystemSummary[];
  surface: "confirmatory" | "adversarial";
}) {
  const semanticKey = `${surface}_semantic` as const;
  const strictKey = `${surface}_strict` as const;
  const data = systems.map((system) => ({
    system: labelSystem(system.system_id).replace(" · ", "\n"),
    semantic: system[semanticKey],
    strict: system[strictKey],
  }));
  return (
    <div>
      <div className="h-[360px] w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            accessibilityLayer={false}
            margin={{ top: 16, right: 16, left: -8, bottom: 56 }}
          >
            <CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} />
            <XAxis
              dataKey="system"
              stroke="#64748b"
              fontSize={11}
              interval={0}
              angle={-24}
              textAnchor="end"
            />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
              stroke="#64748b"
              fontSize={11}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,.03)" }}
              contentStyle={{
                background: "#020617",
                border: "1px solid rgba(255,255,255,.12)",
                borderRadius: 12,
              }}
              formatter={(value) => percent(Number(value))}
            />
            <Bar dataKey="semantic" name="Semantic exactness" fill="#67e8f9" radius={[4, 4, 0, 0]} />
            <Bar dataKey="strict" name="Strict validity" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="overflow-x-auto" tabIndex={0} aria-label={`${surface} metric table scroll area`}>
        <table className="w-full min-w-[680px] text-left text-sm">
          <caption className="sr-only">Accessible {surface} metric table</caption>
          <thead className="text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-3">System</th>
              <th className="py-3">Semantic exactness</th>
              <th className="py-3">Strict validity</th>
            </tr>
          </thead>
          <tbody>
            {systems.map((system) => (
              <tr key={system.system_id} className="border-t border-white/8">
                <td className="py-3 font-medium text-white">{labelSystem(system.system_id)}</td>
                <td className="py-3 font-mono text-cyan-200">{percent(system[semanticKey])}</td>
                <td className="py-3 font-mono text-violet-200">{percent(system[strictKey])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
