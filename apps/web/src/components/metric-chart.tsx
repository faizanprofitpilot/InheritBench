"use client";

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
  return (
    <div>
      <div className="space-y-5" aria-label={`${surface} system comparison`}>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium">
          <span className="inline-flex items-center gap-2 text-cyan-100">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-300" /> Semantic exactness
          </span>
          <span className="inline-flex items-center gap-2 text-violet-100">
            <span className="h-2.5 w-2.5 rounded-full bg-violet-400" /> Strict validity
          </span>
        </div>
        {systems.map((system) => (
          <div key={system.system_id} className="grid gap-3 border-t border-white/8 pt-5 lg:grid-cols-[13rem_1fr] lg:items-center">
            <div>
              <p className="font-semibold text-white">{labelSystem(system.system_id)}</p>
              <p className="mt-1 break-all font-mono text-xs text-slate-500">{system.system_id}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <MetricBar label="Semantic" value={system[semanticKey]} tone="semantic" />
              <MetricBar label="Strict" value={system[strictKey]} tone="strict" />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-8 overflow-x-auto" tabIndex={0} aria-label={`${surface} metric table scroll area`}>
        <table className="w-full min-w-[680px] text-left text-[0.9375rem]">
          <caption className="sr-only">Accessible {surface} metric table</caption>
          <thead className="text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="py-3">System</th>
              <th className="py-3">Semantic exactness</th>
              <th className="py-3">Strict validity</th>
            </tr>
          </thead>
          <tbody>
            {systems.map((system) => (
              <tr key={system.system_id} className="border-t border-white/8">
                <td className="py-4 font-medium text-white">{labelSystem(system.system_id)}</td>
                <td className="py-4 font-mono text-cyan-200">{percent(system[semanticKey])}</td>
                <td className="py-4 font-mono text-violet-200">{percent(system[strictKey])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricBar({ label, value, tone }: { label: string; value: number; tone: "semantic" | "strict" }) {
  const width = `${Math.max(value * 100, value > 0 ? 2 : 0)}%`;
  const color = tone === "semantic" ? "bg-cyan-300" : "bg-violet-400";
  const text = tone === "semantic" ? "text-cyan-100" : "text-violet-100";
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-slate-300">{label}</span>
        <span className={`font-mono font-semibold tabular-nums ${text}`}>{percent(value)}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-white/7">
        <div className={`h-full rounded-full ${color}`} style={{ width }} />
      </div>
    </div>
  );
}
