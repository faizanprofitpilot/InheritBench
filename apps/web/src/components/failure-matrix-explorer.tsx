"use client";

import { ChevronDown, Filter, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { MatrixRow } from "@/lib/data-schema";
import { labelSystem, labelToken, percent } from "@/lib/utils";

type ParsedGroup = { family: string; archetype: string };

export function FailureMatrixExplorer({ rows }: { rows: MatrixRow[] }) {
  const [method, setMethod] = useState("all");
  const [family, setFamily] = useState("all");
  const [archetype, setArchetype] = useState("all");
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [semanticMismatch, setSemanticMismatch] = useState(false);
  const [strictInvalid, setStrictInvalid] = useState(false);
  const [safetyIssue, setSafetyIssue] = useState(false);

  const parsed = useMemo(() => rows.map((row) => ({ row, ...parseGroup(row.group_key) })), [rows]);
  const methods = useMemo(() => [...new Set(rows.map((row) => row.system_id))].sort(), [rows]);
  const families = useMemo(() => [...new Set(parsed.map((item) => item.family))].sort(), [parsed]);
  const archetypes = useMemo(
    () => [...new Set(parsed.filter((item) => family === "all" || item.family === family).map((item) => item.archetype))].sort(),
    [family, parsed],
  );
  const filtered = useMemo(
    () =>
      parsed.filter(({ row, family: rowFamily, archetype: rowArchetype }) => {
        const safetyFailures = safetyCount(row);
        const anyFailure = row.semantic_exact.rate < 1 || row.strict_valid.rate < 1 || safetyFailures > 0;
        return (
          (method === "all" || row.system_id === method) &&
          (family === "all" || rowFamily === family) &&
          (archetype === "all" || rowArchetype === archetype) &&
          (!failuresOnly || anyFailure) &&
          (!semanticMismatch || row.semantic_exact.rate < 1) &&
          (!strictInvalid || row.strict_valid.rate < 1) &&
          (!safetyIssue || safetyFailures > 0)
        );
      }),
    [archetype, failuresOnly, family, method, parsed, safetyIssue, semanticMismatch, strictInvalid],
  );
  const summary = useMemo(() => compareTargetMethods(rows), [rows]);

  function resetFilters(): void {
    setMethod("all");
    setFamily("all");
    setArchetype("all");
    setFailuresOnly(false);
    setSemanticMismatch(false);
    setStrictInvalid(false);
    setSafetyIssue(false);
  }

  return (
    <div className="space-y-7">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <InsightCard
          label="Full retraining performs better"
          value={`${summary.fullBetter.length} / ${summary.groups}`}
          detail={formatArchetypes(summary.fullBetter)}
          tone="violet"
        />
        <InsightCard
          label="Anchored transfer performs better"
          value={`${summary.hybridBetter.length} / ${summary.groups}`}
          detail={formatArchetypes(summary.hybridBetter)}
          tone="cyan"
        />
        <InsightCard
          label="Shared semantic failures"
          value={`${summary.sharedFailures.length} / ${summary.groups}`}
          detail="Both target methods miss exact contracts in these archetypes."
          tone="amber"
        />
        <InsightCard
          label="Safety failures"
          value={`${summary.fullSafety} full · ${summary.hybridSafety} anchored`}
          detail="False action, unauthorized action, and approval-bypass counts."
          tone="rose"
        />
      </div>

      {summary.largestDisagreements.length > 0 && (
        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5 text-amber-300" />
            <div>
              <h3 className="font-semibold text-white">Largest full-versus-anchored disagreements</h3>
              <p className="mt-1 text-sm text-slate-400">Semantic-exactness deltas from the frozen adversarial archetype matrix.</p>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {summary.largestDisagreements.map((item) => (
              <Badge key={item.group} className="border-amber-300/15 bg-amber-300/5 text-amber-100">
                {labelGroup(item.group)} · {percent(item.delta)}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      <details className="group rounded-2xl border border-white/10 bg-slate-950/55">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 sm:px-6">
          <div>
            <p className="font-semibold text-white">View all archetype results</p>
            <p className="mt-1 text-sm text-slate-400">Filter the complete frozen matrix; no rows are removed from the data bundle.</p>
          </div>
          <ChevronDown className="h-5 w-5 shrink-0 text-cyan-300 transition group-open:rotate-180" />
        </summary>
        <div className="border-t border-white/8 p-4 sm:p-6">
          <div className="grid gap-4 rounded-2xl border border-white/8 bg-white/[0.02] p-4 lg:grid-cols-3">
            <FilterSelect label="Method" value={method} onChange={setMethod} options={methods} render={labelSystem} />
            <FilterSelect label="Policy family" value={family} onChange={(value) => { setFamily(value); setArchetype("all"); }} options={families} render={labelToken} />
            <FilterSelect label="Archetype" value={archetype} onChange={setArchetype} options={archetypes} render={labelToken} />
            <div className="flex flex-wrap gap-2 lg:col-span-3" aria-label="Failure filters">
              <FilterToggle label="Failures only" active={failuresOnly} onChange={setFailuresOnly} />
              <FilterToggle label="Semantic mismatch" active={semanticMismatch} onChange={setSemanticMismatch} />
              <FilterToggle label="Strict-invalid output" active={strictInvalid} onChange={setStrictInvalid} />
              <FilterToggle label="Safety issue" active={safetyIssue} onChange={setSafetyIssue} />
              <button type="button" onClick={resetFilters} className="rounded-full px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/5 hover:text-white">
                Reset filters
              </button>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-2 text-sm text-slate-300" role="status" aria-live="polite">
            <Filter className="h-4 w-4 text-cyan-300" />
            Showing {filtered.length} of {rows.length} rows
          </div>

          {filtered.length === 0 ? (
            <div className="mt-5 rounded-xl border border-dashed border-white/12 p-8 text-center">
              <p className="font-medium text-white">No archetype rows match these filters.</p>
              <button type="button" onClick={resetFilters} className="mt-3 text-sm font-medium text-cyan-200 hover:text-cyan-100">
                Clear filters
              </button>
            </div>
          ) : (
            <>
              <div className="mt-5 hidden max-h-[680px] overflow-auto md:block" tabIndex={0} aria-label="Archetype matrix scroll area">
                <table className="w-full min-w-[980px] border-separate border-spacing-0 text-left text-[0.9375rem]">
                  <thead className="sticky top-0 z-20 bg-slate-950 text-xs uppercase tracking-wider text-slate-300">
                    <tr>
                      <th className="sticky left-0 z-30 border-b border-white/10 bg-slate-950 px-5 py-4">System</th>
                      <th className="border-b border-white/10 px-5 py-4">Family</th>
                      <th className="border-b border-white/10 px-5 py-4">Archetype</th>
                      <th className="border-b border-white/10 px-5 py-4">n</th>
                      <th className="border-b border-white/10 px-5 py-4">Semantic</th>
                      <th className="border-b border-white/10 px-5 py-4">Strict</th>
                      <th className="border-b border-white/10 px-5 py-4">Argument F1</th>
                      <th className="border-b border-white/10 px-5 py-4">Safety</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(({ row, family: rowFamily, archetype: rowArchetype }) => (
                      <tr key={`${row.system_id}:${row.group_key}`} className="border-b border-white/6">
                        <td className="sticky left-0 bg-slate-950 px-5 py-4 font-medium text-white">{labelSystem(row.system_id)}</td>
                        <td className="px-5 py-4 text-slate-300">{labelToken(rowFamily)}</td>
                        <td className="px-5 py-4 text-slate-300">{labelToken(rowArchetype)}</td>
                        <td className="px-5 py-4 font-mono text-slate-300">{row.prediction_count}</td>
                        <td className="px-5 py-4 font-mono text-cyan-200">{percent(row.semantic_exact.rate)}</td>
                        <td className="px-5 py-4 font-mono text-violet-200">{percent(row.strict_valid.rate)}</td>
                        <td className="px-5 py-4 font-mono text-slate-200">{percent(row.argument_f1.rate)}</td>
                        <td className="px-5 py-4 font-mono text-amber-200">{safetyCount(row)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-5 grid gap-3 md:hidden">
                {filtered.map(({ row, family: rowFamily, archetype: rowArchetype }) => (
                  <Card key={`${row.system_id}:${row.group_key}`} className="p-4">
                    <p className="font-semibold text-white">{labelSystem(row.system_id)}</p>
                    <p className="mt-1 text-sm text-slate-400">{labelToken(rowFamily)} · {labelToken(rowArchetype)} · n={row.prediction_count}</p>
                    <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <MetricCell label="Semantic" value={percent(row.semantic_exact.rate)} tone="cyan" />
                      <MetricCell label="Strict" value={percent(row.strict_valid.rate)} tone="violet" />
                      <MetricCell label="Argument F1" value={percent(row.argument_f1.rate)} tone="slate" />
                      <MetricCell label="Safety failures" value={String(safetyCount(row))} tone="amber" />
                    </dl>
                  </Card>
                ))}
              </div>
            </>
          )}
        </div>
      </details>
    </div>
  );
}

function parseGroup(groupKey: string): ParsedGroup {
  const [, family = "unknown", archetype = "unknown"] = groupKey.split(":");
  return { family, archetype };
}

function safetyCount(row: MatrixRow): number {
  return row.false_actions + row.unauthorized_actions + row.approval_bypasses;
}

function compareTargetMethods(rows: MatrixRow[]) {
  const full = new Map(rows.filter((row) => row.system_id === "target_full_retrain").map((row) => [row.group_key, row]));
  const hybrid = new Map(rows.filter((row) => row.system_id === "target_hybrid_anchored_distillation_10").map((row) => [row.group_key, row]));
  const groups = [...full.keys()].filter((group) => hybrid.has(group));
  const fullBetter = groups.filter((group) => full.get(group)!.semantic_exact.rate > hybrid.get(group)!.semantic_exact.rate);
  const hybridBetter = groups.filter((group) => hybrid.get(group)!.semantic_exact.rate > full.get(group)!.semantic_exact.rate);
  const sharedFailures = groups.filter((group) => full.get(group)!.semantic_exact.rate < 1 && hybrid.get(group)!.semantic_exact.rate < 1);
  const largestDisagreements = groups
    .map((group) => ({ group, delta: Math.abs(full.get(group)!.semantic_exact.rate - hybrid.get(group)!.semantic_exact.rate) }))
    .filter((item) => item.delta > 0)
    .sort((left, right) => right.delta - left.delta || left.group.localeCompare(right.group))
    .slice(0, 4);
  return {
    groups: groups.length,
    fullBetter,
    hybridBetter,
    sharedFailures,
    largestDisagreements,
    fullSafety: [...full.values()].reduce((total, row) => total + safetyCount(row), 0),
    hybridSafety: [...hybrid.values()].reduce((total, row) => total + safetyCount(row), 0),
  };
}

function formatArchetypes(groups: string[]): string {
  if (groups.length === 0) return "No archetype advantage on semantic exactness.";
  return groups.slice(0, 2).map(labelGroup).join(" · ") + (groups.length > 2 ? ` · +${groups.length - 2} more` : "");
}

function labelGroup(group: string): string {
  const { archetype } = parseGroup(group);
  return labelToken(archetype);
}

function InsightCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: "violet" | "cyan" | "amber" | "rose" }) {
  const colors = { violet: "text-violet-200", cyan: "text-cyan-200", amber: "text-amber-200", rose: "text-rose-200" };
  return (
    <Card className="p-5">
      <p className="text-sm font-medium text-slate-300">{label}</p>
      <p className={`mt-3 font-mono text-2xl font-semibold ${colors[tone]}`}>{value}</p>
      <p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p>
    </Card>
  );
}

function FilterSelect({ label, value, onChange, options, render }: { label: string; value: string; onChange: (value: string) => void; options: string[]; render: (value: string) => string }) {
  return (
    <label className="text-sm font-medium text-slate-300">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-slate-950 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-300">
        <option value="all">All</option>
        {options.map((option) => <option key={option} value={option}>{render(option)}</option>)}
      </select>
    </label>
  );
}

function FilterToggle({ label, active, onChange }: { label: string; active: boolean; onChange: (active: boolean) => void }) {
  return (
    <button type="button" aria-pressed={active} onClick={() => onChange(!active)} className={`rounded-full border px-3 py-2 text-sm font-medium transition ${active ? "border-cyan-300/30 bg-cyan-300/10 text-cyan-100" : "border-white/10 text-slate-300 hover:border-white/20 hover:text-white"}`}>
      {label}
    </button>
  );
}

function MetricCell({ label, value, tone }: { label: string; value: string; tone: "cyan" | "violet" | "slate" | "amber" }) {
  const colors = { cyan: "text-cyan-200", violet: "text-violet-200", slate: "text-slate-200", amber: "text-amber-200" };
  return <div><dt className="text-xs text-slate-400">{label}</dt><dd className={`mt-1 font-mono font-semibold ${colors[tone]}`}>{value}</dd></div>;
}
