"use client";

import { Search, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { GenerationEvaluation } from "@/lib/sandbox";

interface FindingsExplorerProps {
  records: GenerationEvaluation[];
}

function coverageGroup(record: GenerationEvaluation) {
  const coverage = record.evaluation.coverage;
  return String(coverage.group ?? coverage.archetype ?? coverage.family ?? "all");
}

function json(value: unknown) {
  return JSON.stringify(value, null, 2);
}

const selectClass =
  "h-11 rounded-xl border border-white/10 bg-slate-950 px-3 text-sm text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300";

export function FindingsExplorer({ records }: FindingsExplorerProps) {
  const [query, setQuery] = useState("");
  const [surface, setSurface] = useState("all");
  const [outcome, setOutcome] = useState("all");
  const [parser, setParser] = useState("all");
  const [safety, setSafety] = useState("all");
  const [group, setGroup] = useState("all");

  const surfaces = useMemo(() => [...new Set(records.map((record) => record.surface))].sort(), [records]);
  const groups = useMemo(() => [...new Set(records.map(coverageGroup))].sort(), [records]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return records.filter((record) => {
      const evaluation = record.evaluation;
      const searchable = [
        evaluation.record_id,
        evaluation.raw_output,
        json(evaluation.expected),
        json(evaluation.parsed_output),
        ...evaluation.parser_findings.map((finding) => `${finding.code} ${finding.message}`),
        ...evaluation.safety_findings.map((finding) => `${finding.code} ${finding.message}`),
      ]
        .join(" ")
        .toLowerCase();
      return (
        (!needle || searchable.includes(needle)) &&
        (surface === "all" || record.surface === surface) &&
        (outcome === "all" ||
          (outcome === "correct" ? evaluation.semantic_match : !evaluation.semantic_match)) &&
        (parser === "all" ||
          (parser === "parser" ? evaluation.parser_findings.length > 0 : !evaluation.strict_valid)) &&
        (safety === "all" ||
          (safety === "any"
            ? evaluation.safety_findings.length > 0
            : evaluation.safety_findings.some((finding) => finding.severity === "blocker"))) &&
        (group === "all" || coverageGroup(record) === group)
      );
    });
  }, [group, outcome, parser, query, records, safety, surface]);

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-white/10 p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Record findings</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Inspect every evaluated record</h2>
          </div>
          <p className="text-sm text-slate-400" aria-live="polite">
            Showing {filtered.length} of {records.length} records
          </p>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <label className="relative xl:col-span-2">
            <span className="sr-only">Search record findings</span>
            <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search IDs, outputs, or findings"
              className={`${selectClass} w-full pl-9`}
            />
          </label>
          <label>
            <span className="sr-only">Surface</span>
            <select className={`${selectClass} w-full`} value={surface} onChange={(event) => setSurface(event.target.value)}>
              <option value="all">All surfaces</option>
              {surfaces.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            <span className="sr-only">Outcome</span>
            <select className={`${selectClass} w-full`} value={outcome} onChange={(event) => setOutcome(event.target.value)}>
              <option value="all">All outcomes</option>
              <option value="correct">Correct</option>
              <option value="incorrect">Incorrect</option>
            </select>
          </label>
          <label>
            <span className="sr-only">Parser and strict validity</span>
            <select className={`${selectClass} w-full`} value={parser} onChange={(event) => setParser(event.target.value)}>
              <option value="all">All parser states</option>
              <option value="parser">Parser findings</option>
              <option value="strict">Strict-invalid</option>
            </select>
          </label>
          <label>
            <span className="sr-only">Safety findings</span>
            <select className={`${selectClass} w-full`} value={safety} onChange={(event) => setSafety(event.target.value)}>
              <option value="all">All safety states</option>
              <option value="any">Any safety finding</option>
              <option value="blocker">Blockers only</option>
            </select>
          </label>
          <label className="xl:col-start-5 xl:col-span-2">
            <span className="sr-only">Coverage group</span>
            <select className={`${selectClass} w-full`} value={group} onChange={(event) => setGroup(event.target.value)}>
              <option value="all">All coverage groups</option>
              {groups.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className="code-scroll max-h-[46rem] overflow-auto" tabIndex={0} aria-label="Scrollable record findings table">
        <table className="w-full min-w-[72rem] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-950 text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-5 py-4 font-medium">Record</th>
              <th className="px-5 py-4 font-medium">Outcome</th>
              <th className="px-5 py-4 font-medium">Expected / parsed</th>
              <th className="px-5 py-4 font-medium">Field correctness</th>
              <th className="px-5 py-4 font-medium">Findings</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/8">
            {filtered.map(({ surface: recordSurface, evaluation }) => (
              <tr key={`${recordSurface}-${evaluation.record_id}`} className="align-top hover:bg-white/[0.025]">
                <td className="max-w-64 px-5 py-5">
                  <p className="break-all font-mono text-xs text-white">{evaluation.record_id}</p>
                  <p className="mt-2 text-xs text-slate-400">{recordSurface} · {coverageGroup({ surface: recordSurface, evaluation, generation: { record_id: evaluation.record_id, raw_output: evaluation.raw_output, status: "COMPLETED" } })}</p>
                </td>
                <td className="px-5 py-5">
                  <Badge className={evaluation.semantic_match ? "" : "border-rose-300/20 bg-rose-300/8 text-rose-200"}>
                    {evaluation.semantic_match ? "Correct" : "Incorrect"}
                  </Badge>
                  <p className="mt-3 text-xs text-slate-400">{evaluation.parser_classification.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-xs text-slate-400">Strict: {evaluation.strict_valid ? "valid" : "invalid"}</p>
                </td>
                <td className="w-[34rem] px-5 py-5">
                  <details>
                    <summary className="cursor-pointer font-medium text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
                      Compare output
                    </summary>
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-400">Expected</p>
                        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/30 p-3 font-mono text-xs text-slate-300">{json(evaluation.expected)}</pre>
                      </div>
                      <div>
                        <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-400">{evaluation.parsed_output ? "Parsed" : "Raw"}</p>
                        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/30 p-3 font-mono text-xs text-slate-300">{evaluation.parsed_output ? json(evaluation.parsed_output) : evaluation.raw_output}</pre>
                      </div>
                    </div>
                  </details>
                </td>
                <td className="px-5 py-5">
                  <ul className="space-y-1">
                    {Object.entries(evaluation.field_correctness).map(([field, correct]) => (
                      <li key={field} className={correct ? "text-emerald-300" : "text-rose-300"}>
                        <span aria-hidden="true">{correct ? "✓" : "×"}</span> {field}
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="max-w-sm px-5 py-5">
                  {evaluation.parser_findings.length + evaluation.safety_findings.length === 0 ? (
                    <span className="text-slate-400">None</span>
                  ) : (
                    <ul className="space-y-2">
                      {evaluation.parser_findings.map((finding) => (
                        <li key={finding.code} className="text-amber-200">
                          <span className="font-mono text-xs">{finding.code}</span>
                          <span className="block text-xs text-slate-400">{finding.message}</span>
                        </li>
                      ))}
                      {evaluation.safety_findings.map((finding) => (
                        <li key={`${finding.code}-${finding.message}`} className={finding.severity === "blocker" ? "text-rose-200" : "text-amber-200"}>
                          <span className="flex items-center gap-1 font-mono text-xs"><ShieldAlert className="h-3.5 w-3.5" />{finding.code}</span>
                          <span className="block text-xs text-slate-400">{finding.message}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
