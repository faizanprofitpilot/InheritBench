"use client";

import { CheckCircle2, CircleSlash2, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { CaseDetails } from "@/lib/data-schema";
import { labelSystem, labelToken } from "@/lib/utils";

export function CaseExplorer({ details }: { details: CaseDetails }) {
  const priority = useMemo(
    () => new Map([
      ["cross_system_disagreement", 0],
      ["hybrid_vs_direct_training_contrast", 1],
      ["parser_schema_failure", 2],
      ["prompt_injection_resilience", 3],
      ["refund_family_contrast", 4],
      ["subscription_family_contrast", 5],
    ]),
    [],
  );
  const ordered = useMemo(
    () => [...details.cases].sort((left, right) => {
      if (left.status !== right.status) return left.status === "SELECTED" ? -1 : 1;
      return (priority.get(left.slot) ?? 99) - (priority.get(right.slot) ?? 99);
    }),
    [details.cases, priority],
  );
  const available = useMemo(
    () => ordered.filter((item) => item.status === "SELECTED"),
    [ordered],
  );
  const [selectedSlot, setSelectedSlot] = useState(available[0]?.slot ?? "");
  const selected = available.find((item) => item.slot === selectedSlot) ?? available[0];
  if (!selected) return null;
  return (
    <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
      <div className="space-y-2" aria-label="Representative case slots">
        {ordered.map((item) => (
          <button
            key={item.slot}
            type="button"
            disabled={item.status === "NO_ELIGIBLE_CASE"}
            onClick={() => setSelectedSlot(item.slot)}
            className={`flex min-h-14 w-full items-start gap-3 rounded-xl border p-3 text-left transition enabled:hover:border-cyan-300/30 enabled:hover:bg-white/5 ${
              item.status === "SELECTED"
                ? item.slot === selectedSlot
                  ? "border-cyan-300/30 bg-cyan-300/[0.07]"
                  : "border-white/8 bg-white/[0.025]"
                : "cursor-not-allowed border-white/5 bg-transparent opacity-35"
            }`}
          >
            {item.status === "SELECTED" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
            ) : (
              <CircleSlash2 className="mt-0.5 h-4 w-4 shrink-0 text-slate-600" />
            )}
            <span>
              <span className="block text-sm font-medium text-slate-200">{labelToken(item.slot)}</span>
              <span className="mt-1 block text-sm text-slate-400">
                {item.status === "SELECTED" ? labelToken(item.evaluation_surface ?? "") : "No eligible case in frozen selection"}
              </span>
            </span>
          </button>
        ))}
      </div>
      <div className="min-w-0 space-y-5">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{selected.evaluation_surface}</Badge>
            <Badge className="border-white/10 bg-white/5 text-slate-300">
              {selected.scenario_family?.replaceAll("_", " ")}
            </Badge>
          </div>
          <h2 className="mt-4 text-2xl font-semibold text-white">{labelToken(selected.slot)}</h2>
          <p className="mt-2 break-all font-mono text-sm text-slate-400">{selected.example_id}</p>
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <EvidenceBlock title="Prompt-visible input" value={selected.input} />
            <EvidenceBlock title="Expected contract" value={selected.expected_contract} />
          </div>
        </Card>
        <div className="grid gap-4 lg:grid-cols-2">
          {selected.system_predictions.map((prediction) => (
            <Card key={prediction.system_id} className="overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-white/8 px-5 py-4">
                <div>
                  <p className="font-medium text-white">{labelSystem(prediction.system_id)}</p>
                  <p className="mt-1 text-sm text-slate-400">
                    {String(prediction.parser_result.classification ?? "unknown")}
                  </p>
                </div>
                <FailureBadge failure={prediction.primary_failure} />
              </div>
              <details className="group">
                <summary className="cursor-pointer list-none px-5 py-4 text-sm font-medium text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
                  Inspect exact raw output
                </summary>
                <div className="space-y-4 border-t border-white/8 p-5">
                  <pre
                    className="code-scroll max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-black/30 p-4 font-mono text-sm leading-6 text-slate-200"
                    tabIndex={0}
                    aria-label={`${labelSystem(prediction.system_id)} raw output`}
                  >
                    {prediction.raw_output || "<empty output>"}
                  </pre>
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    <KeyValue label="Semantic exact" value={String(prediction.metrics.semantic_decision_score_v0)} />
                    <KeyValue label="Strict contract" value={String(prediction.metrics.strict_contract_score_v0)} />
                    <KeyValue label="Run" value={prediction.run_id.slice(-12)} />
                    <KeyValue label="Prediction hash" value={prediction.prediction_content_sha256.slice(0, 12)} />
                  </dl>
                </div>
              </details>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

function FailureBadge({ failure }: { failure: string }) {
  const passed = failure === "NONE";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wider ${
        passed ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-200"
      }`}
    >
      {!passed && <ShieldAlert className="h-3 w-3" />}
      {passed ? "Exact" : labelToken(failure)}
    </span>
  );
}

function EvidenceBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</p>
      <pre
        className="code-scroll max-h-80 overflow-auto whitespace-pre-wrap rounded-xl border border-white/8 bg-black/30 p-4 font-mono text-sm leading-6 text-slate-200"
        tabIndex={0}
        aria-label={`${title} scroll area`}
      >
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-400">{label}</dt>
      <dd className="mt-1 truncate font-mono text-slate-300">{value}</dd>
    </div>
  );
}
