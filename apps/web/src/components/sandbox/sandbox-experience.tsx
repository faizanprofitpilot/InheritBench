"use client";

import {
  ArrowUpRight,
  ChevronDown,
  Check,
  CheckCircle2,
  Circle,
  Download,
  FileJson2,
  FlaskConical,
  LoaderCircle,
  Play,
  RotateCcw,
  ShieldCheck,
  TriangleAlert,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { FindingsExplorer } from "@/components/sandbox/findings-explorer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { SandboxPresentation } from "@/lib/data";
import {
  UploadParseError,
  createMutationController,
  createVerificationReceipt,
  downloadJson,
  executeScenario,
  executeUploadedPredictions,
  loadSandboxAssets,
  parsePredictionUpload,
  type IntegrityLoadResult,
  type JsonValue,
  type MutationController,
  type MutationEffect,
  type MutationKind,
  type Receipt,
  type SandboxAssets,
  type Scenario,
  type ScenarioExecution,
  type UploadParseResult,
} from "@/lib/sandbox";

const SCENARIOS = [
  {
    id: "untouched-target",
    label: "Untouched OLMo",
    state: "Diagnostic baseline",
  },
  {
    id: "direct-recovery",
    label: "Direct recovery",
    state: "Readiness eligible",
  },
  {
    id: "anchored-successor",
    label: "Anchored successor",
    state: "Readiness eligible",
  },
] as const;

const MUTATIONS: Array<{ kind: MutationKind; label: string }> = [
  { kind: "unauthorized_action", label: "Unauthorized action" },
  { kind: "approval_bypass", label: "Approval bypass" },
  { kind: "policy_code", label: "Policy code" },
  { kind: "reason_code", label: "Reason code" },
  { kind: "required_argument_corruption", label: "Required argument" },
  { kind: "malformed_contract", label: "Malformed contract" },
];

const PROGRESS = [
  ["integrity", "Verify the evaluation files"],
  ["evaluate", "Evaluate the candidate records"],
  ["coverage", "Check the required behaviors"],
  ["safety", "Check the safety rules"],
  ["readiness", "Check whether this candidate is ready to ship"],
  ["receipt", "Prepare verification details"],
] as const;

type ProgressId = (typeof PROGRESS)[number][0];
type StepState = "pending" | "active" | "complete";
type ProgressState = Record<ProgressId, StepState>;
type EvaluationSource = "frozen" | "mutation" | "upload";

export interface SandboxDependencies {
  loadAssets: (baseUrl: string) => Promise<IntegrityLoadResult>;
  execute: typeof executeScenario;
  executeUpload: typeof executeUploadedPredictions;
  createReceipt: typeof createVerificationReceipt;
  createController: typeof createMutationController;
  parseUpload: typeof parsePredictionUpload;
  download: typeof downloadJson;
}

const defaultDependencies: SandboxDependencies = {
  loadAssets: loadSandboxAssets,
  execute: executeScenario,
  executeUpload: executeUploadedPredictions,
  createReceipt: createVerificationReceipt,
  createController: createMutationController,
  parseUpload: parsePredictionUpload,
  download: downloadJson,
};

const initialProgress = (): ProgressState => ({
  integrity: "pending",
  evaluate: "pending",
  coverage: "pending",
  safety: "pending",
  readiness: "pending",
  receipt: "pending",
});

function formatRate(correct: number, total: number) {
  return `${correct}/${total} · ${total ? ((correct / total) * 100).toFixed(1) : "0.0"}%`;
}

function shortHash(hash: string | null | undefined) {
  return hash ? `${hash.slice(0, 12)}…${hash.slice(-8)}` : "Unavailable";
}

function statusLabel(execution: ScenarioExecution, source: EvaluationSource) {
  if (!execution.readiness_eligible) {
    return source === "upload" ? "EVALUATION ONLY" : "DIAGNOSTIC BASELINE";
  }
  return execution.readiness?.status ?? "READINESS UNAVAILABLE";
}

function statusClass(execution: ScenarioExecution) {
  if (!execution.readiness_eligible) return "bg-slate-900 text-slate-200";
  if (execution.readiness?.status === "MIGRATION_BLOCKED") return "bg-gradient-to-br from-rose-950/70 to-slate-900 text-rose-100";
  if (execution.readiness?.status === "CONDITIONAL_PASS") return "bg-gradient-to-br from-amber-950/55 to-slate-900 text-amber-100";
  return "bg-gradient-to-br from-emerald-950/55 to-slate-900 text-emerald-100";
}

function DefinitionList({ items }: { items: Array<[string, React.ReactNode]> }) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map(([term, value]) => (
        <div key={term} className="min-w-0 rounded-xl bg-white/[0.035] p-4">
          <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">{term}</dt>
          <dd className="mt-1 break-words text-sm text-slate-200">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SurfaceMetrics({ title, summary }: { title: string; summary: ScenarioExecution["summaries"]["adapted_source"] }) {
  const weakest = Object.entries(summary.group_semantic).sort((left, right) => left[1].rate - right[1].rate)[0];
  return (
    <div className="rounded-2xl bg-slate-950/45 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-white">{title}</h3>
        <span className="text-xs text-slate-500">{summary.surface}</span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
        {[
          ["Declared semantic correctness", formatRate(summary.semantic_correct, summary.expected)],
          ["Exact-contract fidelity", formatRate(summary.structural_exact, summary.expected)],
          ["Strict validity", formatRate(summary.strict_valid, summary.expected)],
          ["Vocabulary conformance", formatRate(summary.vocabulary_conformant, summary.expected)],
          ["Cross-field conformance", formatRate(summary.cross_field_conformant, summary.expected)],
          ["Mean field correctness", `${(summary.mean_field_correctness * 100).toFixed(1)}%`],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-0.5 font-mono text-slate-200">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-slate-400">
        Weakest coverage group:{" "}
        <span className="text-slate-200">
          {weakest ? `${weakest[0]} (${formatRate(weakest[1].correct, weakest[1].total)})` : "none"}
        </span>
      </p>
    </div>
  );
}

function ResultsPanel({
  execution,
  receipt,
  source,
  onDownloadReceipt,
}: {
  execution: ScenarioExecution;
  receipt: Receipt;
  source: EvaluationSource;
  onDownloadReceipt: () => void;
}) {
  const selectedSummaries = Object.entries(execution.summaries.selected);
  const safety = execution.records.selected.flatMap((record) => record.evaluation.safety_findings);
  const blockers = safety.filter((finding) => finding.severity === "blocker");
  const safetyCodes = [...new Set(safety.map((finding) => finding.code))];
  const clean = selectedSummaries.find(([name]) => name.includes("confirmatory"));
  const adversarial = selectedSummaries.find(([name]) => name.includes("adversarial"));
  const evidenceScope =
    source === "frozen"
      ? "Frozen reference"
      : source === "mutation"
        ? "Modified locally"
        : "User-provided";
  return (
    <section className="scroll-mt-24 space-y-6" aria-labelledby="results-heading">
      <div className={`overflow-hidden rounded-3xl p-6 shadow-[0_28px_90px_rgba(2,8,23,.34)] sm:p-9 ${statusClass(execution)}`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-slate-300">Assurance decision</p>
            <h2 id="results-heading" className="mt-3 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              {statusLabel(execution, source)}
            </h2>
            <p className="mt-2 text-sm text-slate-300">
              {execution.readiness_eligible
                ? "Derived by the unchanged product readiness contract."
                : "Evaluation evidence only; no formal readiness verdict was issued."}
            </p>
          </div>
          <Badge className="border-white/15 bg-slate-950/50 text-slate-100">
            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
            {evidenceScope}
          </Badge>
        </div>

        {source !== "frozen" ? (
          <div className="mt-5 rounded-xl border border-amber-300/20 bg-amber-300/[0.06] p-4 text-sm text-amber-100">
            {source === "mutation"
              ? "Controlled mutation result — outside the frozen evidence and parity contract."
              : "Local upload result — evaluated locally and separated from frozen integrity/parity evidence."}
          </div>
        ) : null}
        {!execution.readiness_eligible && source === "frozen" ? (
          <div className="mt-5 rounded-xl border border-slate-300/15 bg-slate-300/[0.04] p-4 text-sm text-slate-300">
            This is a diagnostic baseline and is explicitly not readiness-eligible. It cannot support a migration decision.
          </div>
        ) : !execution.readiness_eligible && source === "upload" ? (
          <div className="mt-5 rounded-xl border border-slate-300/15 bg-slate-300/[0.04] p-4 text-sm text-slate-300">
            This partial compatible upload receives record evaluation only; it is not readiness-eligible.
          </div>
        ) : null}

        {execution.readiness_eligible ? (
          <div className="mt-7 grid gap-4 lg:grid-cols-3">
            <SurfaceMetrics title="Source capability gate" summary={execution.summaries.adapted_source} />
            {clean ? <SurfaceMetrics title="Clean evaluation" summary={clean[1]} /> : null}
            {adversarial ? <SurfaceMetrics title="Adversarial evaluation" summary={adversarial[1]} /> : null}
          </div>
        ) : (
          <div className="mt-7 grid gap-4 lg:grid-cols-2">
            {selectedSummaries.map(([surface, summary]) => (
              <SurfaceMetrics key={surface} title="Diagnostic test" summary={summary} />
            ))}
          </div>
        )}

        <dl className="mt-6 grid gap-3 sm:grid-cols-3">
          <ResultSignal
            label="Safety blockers"
            value={String(blockers.length)}
            note={safetyCodes.length ? safetyCodes.join(", ") : "No blocker findings"}
          />
          <ResultSignal
            label="Evidence integrity"
            value={execution.integrity.verified ? "VERIFIED" : "FAILED"}
            note={`${execution.integrity.verified_assets.length} assets checked`}
          />
          <ResultSignal
            label="Evaluation consistency"
            value={source === "frozen" && execution.parity.verified ? "VERIFIED" : "LOCAL"}
            note={
              source === "frozen" && execution.parity.verified
                ? "Matches the verified reference"
                : "Local result"
            }
          />
        </dl>

        {execution.readiness?.reason_codes.length ? (
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-white">Readiness reasons</h3>
            <ul className="mt-2 flex flex-wrap gap-2">
              {execution.readiness.reason_codes.map((reason) => <li key={reason}><Badge>{reason}</Badge></li>)}
            </ul>
          </div>
        ) : null}

        <details className="group mt-6 rounded-2xl bg-slate-950/35 p-5">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
            Verification and receipt details
            <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180 motion-reduce:transition-none" />
          </summary>
          <div className="mt-5">
            <DefinitionList
              items={[
                ["Integrity", execution.integrity.verified ? "Verified" : "Failed"],
                ["Manifest hash", <code key="manifest" className="font-mono text-xs">{shortHash(execution.integrity.manifest_hash)}</code>],
                ["Assets verified", execution.integrity.verified_assets.length],
                ["Evaluation identity", execution.scenario_id],
                ["Input hash", <code key="input" className="font-mono text-xs">{shortHash(execution.input_sha256)}</code>],
                ["Timing", `${execution.timing.duration_ms} ms · ${new Date(execution.timing.completed_at).toLocaleString()}`],
                ["Replay / parity", source === "frozen" && execution.parity.verified ? "Verified against frozen expectations" : "Not frozen parity"],
                ["Safety blocker findings", `${blockers.length}${safetyCodes.length ? ` · ${safetyCodes.join(", ")}` : " · none"}`],
                ["Receipt hash", <code key="receipt" className="font-mono text-xs">{shortHash(receipt.receipt_sha256)}</code>],
              ]}
            />
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-white/8 pt-5">
            <div>
              <p className="text-sm font-medium text-white">Local verification receipt</p>
              <p className="mt-1 text-xs text-slate-400">Fresh local provenance and hash only. This receipt is not signed or notarized.</p>
            </div>
            <Button type="button" variant="secondary" onClick={onDownloadReceipt}>
              <Download className="h-4 w-4" /> Download receipt
            </Button>
          </div>
        </details>
      </div>

      <details className="group rounded-2xl bg-slate-900/45">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 sm:p-6">
          Detailed record inspection
          <ChevronDown className="h-4 w-4 text-cyan-200 transition-transform group-open:rotate-180 motion-reduce:transition-none" />
        </summary>
        <div className="border-t border-white/6">
          <FindingsExplorer records={execution.records.selected} />
        </div>
      </details>
    </section>
  );
}

function ResultSignal({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-2xl bg-slate-950/45 p-5">
      <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-2 font-mono text-xl font-semibold text-white">{value}</dd>
      <dd className="mt-1 text-xs text-slate-400">{note}</dd>
    </div>
  );
}

function SlimStepper({ activeStep, expanded }: { activeStep: number; expanded: boolean }) {
  const steps = expanded
    ? ["Choose", "Run", "Review", "Stress", "Verify"]
    : ["Choose", "Run", "Review"];
  return (
    <nav aria-label="Assurance Lab workflow" className="py-1" tabIndex={0}>
      <ol className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 sm:flex sm:gap-0">
        {steps.map((label, index) => {
          const number = index + 1;
          const active = number === activeStep;
          const complete = number < activeStep;
          return (
            <li
              key={label}
              aria-current={active ? "step" : undefined}
              className="relative flex min-w-0 items-center gap-3 rounded-xl bg-white/[0.025] px-3 py-2.5 sm:flex-1 sm:rounded-none sm:bg-transparent sm:px-0 sm:py-0"
            >
              {index < steps.length - 1 ? (
                <span
                  className={`absolute left-8 right-0 top-4 hidden h-px sm:block ${complete ? "bg-slate-400" : "bg-white/10"}`}
                  aria-hidden
                />
              ) : null}
              <span
                className={`relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold ${
                  active
                    ? "bg-cyan-200 text-slate-950 shadow-[0_0_0_5px_rgba(103,232,249,.08)]"
                    : complete
                      ? "bg-slate-300 text-slate-950"
                      : "bg-slate-900 text-slate-500 ring-1 ring-white/10"
                }`}
              >
                {number}
              </span>
              <span className={`relative z-10 min-w-0 bg-slate-950 pr-3 text-sm font-medium ${active ? "text-white" : complete ? "text-slate-300" : "text-slate-400"}`}>
                {label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function SandboxExperience({
  presentation,
  dependencies = defaultDependencies,
}: {
  presentation: SandboxPresentation;
  dependencies?: SandboxDependencies;
}) {
  const [scenarioId, setScenarioId] = useState<(typeof SCENARIOS)[number]["id"]>("anchored-successor");
  const [assets, setAssets] = useState<SandboxAssets | null>(null);
  const [execution, setExecution] = useState<ScenarioExecution | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [source, setSource] = useState<EvaluationSource>("frozen");
  const [progress, setProgress] = useState<ProgressState>(initialProgress);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mutation, setMutation] = useState<MutationEffect | null>(null);
  const [upload, setUpload] = useState<UploadParseResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [controllerReady, setControllerReady] = useState(false);
  const [frozenReadiness, setFrozenReadiness] = useState<string | null>(null);
  const controller = useRef<MutationController | null>(null);

  useEffect(() => {
    if (!execution) return;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById("results-heading")?.scrollIntoView?.({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [execution]);

  const setStep = (id: ProgressId, state: StepState) =>
    setProgress((current) => ({ ...current, [id]: state }));

  async function ensureAssets() {
    if (assets) {
      setStep("integrity", "complete");
      return assets;
    }
    setStep("integrity", "active");
    const loaded = await dependencies.loadAssets("/data/reference-succession/sandbox/");
    if (!loaded.assets || !loaded.integrity.verified) {
      const failure = loaded.integrity.failed_asset
        ? `${loaded.integrity.failed_asset}: ${loaded.integrity.error ?? "integrity verification failed"}`
        : loaded.integrity.error;
      throw new Error(failure ?? "Sandbox asset integrity verification failed.");
    }
    setAssets(loaded.assets);
    setStep("integrity", "complete");
    return loaded.assets;
  }

  async function finishEvaluation(
    loadedAssets: SandboxAssets,
    resultPromise: Promise<ScenarioExecution>,
    resultSource: EvaluationSource,
  ) {
    setStep("evaluate", "active");
    const result = await resultPromise;
    setStep("evaluate", "complete");
    setStep("coverage", "active");
    void Object.values(result.summaries.selected).flatMap((summary) => Object.keys(summary.group_semantic));
    setStep("coverage", "complete");
    setStep("safety", "active");
    void result.records.selected.flatMap((record) => record.evaluation.safety_findings);
    setStep("safety", "complete");
    setStep("readiness", "active");
    void (result.readiness ?? result.readiness_reason_code);
    setStep("readiness", "complete");
    setStep("receipt", "active");
    const nextReceipt = await dependencies.createReceipt(result, {
      metadata: {
        provenance: "local-browser",
        evidence_scope: resultSource === "frozen" ? "integrity-verified-assets" : `outside-frozen-${resultSource}`,
      },
    });
    setStep("receipt", "complete");
    setExecution(result);
    setReceipt(nextReceipt);
    setSource(resultSource);
    return { result, loadedAssets };
  }

  async function runBuiltIn(target: string | Scenario = scenarioId, resultSource: EvaluationSource = "frozen") {
    setBusy(true);
    setError(null);
    setProgress(initialProgress());
    try {
      const loadedAssets = await ensureAssets();
      const completed = await finishEvaluation(
        loadedAssets,
        dependencies.execute(loadedAssets, target),
        resultSource,
      );
      if (resultSource === "frozen" && target === "anchored-successor") {
        const anchored = loadedAssets.scenarios["anchored-successor"];
        controller.current = dependencies.createController(
          anchored,
          loadedAssets.recordSets[anchored.record_definitions],
          loadedAssets.evaluationContract,
        );
        setControllerReady(true);
        setMutation(null);
        setFrozenReadiness(completed.result.readiness?.status ?? null);
      }
      return completed.result;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Evaluation failed.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function applyMutation(kind: MutationKind) {
    if (!controller.current || !assets) return;
    setBusy(true);
    setError(null);
    setProgress(initialProgress());
    try {
      setStep("integrity", "complete");
      const effect = await controller.current.apply(kind);
      setMutation(effect);
      await finishEvaluation(assets, dependencies.execute(assets, controller.current.scenario), "mutation");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mutation evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resetMutation() {
    if (!controller.current || !assets) return;
    setBusy(true);
    setError(null);
    setProgress(initialProgress());
    try {
      setStep("integrity", "complete");
      const reset = await controller.current.reset();
      setMutation(null);
      await finishEvaluation(assets, dependencies.execute(assets, reset.scenario), "frozen");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mutation reset failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    setUpload(null);
    setUploadError(null);
    try {
      const loadedAssets = await ensureAssets();
      const finalIds = loadedAssets.recordSets["records/final.json"].records.map((record) => record.record_id);
      const parsed = dependencies.parseUpload(new Uint8Array(await file.arrayBuffer()), {
        fileName: file.name,
        compatibleIds: finalIds,
        completeFinalIds: finalIds,
      });
      setUpload(parsed);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Prediction upload failed.";
      setUploadError(reason instanceof UploadParseError ? `[${reason.code}] ${message}` : message);
    }
  }

  async function runUpload() {
    if (!upload) return;
    setBusy(true);
    setError(null);
    setProgress(initialProgress());
    try {
      const loadedAssets = await ensureAssets();
      await finishEvaluation(loadedAssets, dependencies.executeUpload(loadedAssets, upload), "upload");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Uploaded prediction evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  const sample = useMemo(() => assets?.rawAssets?.["sample-predictions.json"], [assets]);
  const scenarioSummary = (id: (typeof SCENARIOS)[number]["id"]) => {
    if (id === "untouched-target") {
      return "Measure capability loss without issuing a readiness verdict.";
    }
    if (id === "direct-recovery") {
      return "Evaluate recovery without targeted anchor intervention.";
    }
    return `Evaluate candidate ${presentation.selectedCandidate ?? "selected by validation"}, selected using validation only.`;
  };
  const scenarioDetail = (id: (typeof SCENARIOS)[number]["id"]) => {
    if (id === "untouched-target") {
      return "This diagnostic test measures which required behaviors survived the model replacement. It does not issue a readiness decision.";
    }
    if (id === "direct-recovery") {
      return "The same evaluation rules test clean and adversarial records without targeted anchor examples.";
    }
    return "This candidate was selected before final evaluation and can be challenged with a controlled failure after the first run.";
  };
  const activeStep = busy && controllerReady ? 4 : mutation ? 5 : execution ? 3 : busy ? 2 : 1;

  return (
    <div className="space-y-10">
      <section className="grid-surface relative overflow-hidden rounded-3xl bg-slate-900/70 px-6 py-9 shadow-[0_30px_100px_rgba(2,8,23,.32)] sm:px-9 lg:px-12 lg:py-11">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(34,211,238,.08),transparent_24rem)]" />
        <div className="relative max-w-4xl">
          <div className="flex items-center gap-2 text-slate-300">
            <FlaskConical className="h-5 w-5 text-cyan-200" />
            <p className="text-sm font-medium">Interactive Assurance Lab</p>
          </div>
          <h1 className="mt-5 max-w-3xl text-balance text-4xl font-semibold tracking-[-0.035em] text-white lg:text-5xl">
            Choose a candidate. Run the evaluation. Review the decision.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
            See whether required behavior survived the model change and whether the selected
            successor is ready to ship.
          </p>
          <p className="mt-5 text-sm leading-6 text-slate-400">
            Runs locally in your browser against precomputed predictions. No model training or
            inference happens here.
          </p>
        </div>
      </section>

      <SlimStepper activeStep={activeStep} expanded={execution !== null} />

      <section aria-labelledby="scenario-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-slate-400">Step 1</p>
            <h2 id="scenario-heading" className="mt-2 text-3xl font-semibold text-white">Choose a candidate</h2>
          </div>
          <p className="text-base text-slate-400">Results remain hidden until evaluation.</p>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {SCENARIOS.map((item) => {
            const selected = scenarioId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                aria-pressed={selected}
                disabled={busy}
                onClick={() => {
                  setScenarioId(item.id);
                  setExecution(null);
                  setReceipt(null);
                  setMutation(null);
                  setError(null);
                  setProgress(initialProgress());
                  controller.current = null;
                  setControllerReady(false);
                  setFrozenReadiness(null);
                }}
                className={`rounded-2xl p-6 text-left shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:opacity-60 ${
                  selected
                    ? "bg-cyan-200/[0.11] ring-2 ring-cyan-200/70 shadow-[0_16px_50px_rgba(8,145,178,.12)]"
                    : "bg-slate-900/70 ring-1 ring-white/6 hover:bg-slate-900 hover:ring-white/12"
                }`}
              >
                <span className="flex items-center justify-between gap-3">
                  <span>
                    <span className="block font-semibold text-white">{item.label}</span>
                    <span className={`mt-1.5 block text-sm font-medium ${selected ? "text-cyan-100" : "text-slate-400"}`}>
                      {item.state}
                    </span>
                  </span>
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full border ${selected ? "border-cyan-200 bg-cyan-200 text-slate-950" : "border-white/20 text-transparent"}`}>
                    <Check className="h-4 w-4" />
                  </span>
                </span>
                <span className="mt-4 block text-base leading-7 text-slate-300">
                  {scenarioSummary(item.id)}
                </span>
                <span className="mt-4 block font-mono text-xs text-slate-400">
                  {item.id === "untouched-target"
                    ? `${presentation.sourceGateRecords} diagnostic records`
                    : `${presentation.finalRecords} final evaluation records`}
                </span>
              </button>
            );
          })}
        </div>
        <details className="mt-4 max-w-3xl text-sm text-slate-400">
          <summary className="w-fit cursor-pointer rounded-md py-1 font-medium text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
            About the selected scenario
          </summary>
          <p className="mt-2 leading-6">{scenarioDetail(scenarioId)}</p>
        </details>
        <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button type="button" size="lg" className="min-w-64" disabled={busy} onClick={() => void runBuiltIn()}>
            {busy ? <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Play className="h-4 w-4" />}
            {busy ? "Running assurance…" : "Run assurance evaluation"}
          </Button>
          <Link href="/run/opsroute-qwen-olmo/" className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-slate-400 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
            Open full succession evidence <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {busy || Object.values(progress).some((value) => value === "complete") ? (
        <div className="rounded-2xl bg-slate-900/45 p-5 sm:p-6" aria-live="polite" aria-busy={busy}>
          <h2 className="text-lg font-semibold text-white">Running the evaluation</h2>
          <ol className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {PROGRESS.map(([id, label]) => {
              const state = progress[id];
              return (
                <li key={id} className="flex items-center gap-3 text-sm">
                  {state === "complete" ? <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-300" /> : state === "active" ? <LoaderCircle className="h-5 w-5 shrink-0 animate-spin text-cyan-200 motion-reduce:animate-none" /> : <Circle className="h-5 w-5 shrink-0 text-slate-700" />}
                  <span className={state === "pending" ? "text-slate-500" : "text-slate-200"}>{label} — {state}</span>
                </li>
              );
            })}
          </ol>
        </div>
      ) : null}

      {error ? (
        <Card role="alert" className="border-rose-300/25 p-5 text-rose-100">
          <div className="flex gap-3"><TriangleAlert className="mt-0.5 h-5 w-5 shrink-0" /><div><h2 className="font-semibold">Evaluation stopped</h2><p className="mt-1 text-sm text-rose-100/80">{error}</p></div></div>
        </Card>
      ) : null}

      {execution && receipt ? (
        <ResultsPanel
          execution={execution}
          receipt={receipt}
          source={source}
          onDownloadReceipt={() => dependencies.download(receipt as unknown as JsonValue, `local-verification-receipt-${execution.scenario_id}.json`)}
        />
      ) : null}

      {controllerReady && execution ? (
        <section className="rounded-3xl bg-slate-900/55 p-6 sm:p-8" aria-labelledby="stress-heading">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-400">Step 4 · Stress</p>
              <h2 id="stress-heading" className="mt-2 text-3xl font-semibold text-white">Challenge the successor</h2>
              <p className="mt-3 max-w-3xl text-base leading-7 text-slate-300">
                The successor has been evaluated. Introduce one controlled failure and run the same
                evaluation rules again. Modified results remain separate from verified evidence.
              </p>
            </div>
            {mutation ? <Badge className="border-amber-300/25 bg-amber-300/8 text-amber-200">Outside frozen evidence</Badge> : null}
          </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {MUTATIONS.map((item) => (
                <Button key={item.kind} type="button" variant="secondary" size="sm" disabled={busy} onClick={() => void applyMutation(item.kind)}>
                  {item.label} · apply and rerun
                </Button>
              ))}
              <Button type="button" size="sm" disabled={busy || !mutation} onClick={() => void resetMutation()}>
                <RotateCcw className="h-4 w-4" /> Reset original
              </Button>
            </div>
            {mutation ? (
              <div className="mt-5 rounded-xl border border-amber-300/20 bg-amber-300/[0.04] p-4">
                <DefinitionList items={[
                  ["Affected record", <code key="record" className="font-mono text-xs">{mutation.record_id}</code>],
                  ["Changed pointers", mutation.changed_fields.join(", ")],
                  ["Hash change", <code key="hash" className="font-mono text-xs">{shortHash(mutation.before_input_sha256)} → {shortHash(mutation.after_input_sha256)}</code>],
                  ["Readiness transition", `${frozenReadiness ?? "Frozen baseline"} → ${execution?.readiness?.status ?? "Evaluation only"}`],
                ]} />
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div><p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">Before output</p><pre className="code-scroll max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/30 p-3 font-mono text-xs text-slate-300">{mutation.before}</pre></div>
                  <div><p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">After output</p><pre className="code-scroll max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/30 p-3 font-mono text-xs text-slate-300">{mutation.after}</pre></div>
                </div>
              </div>
            ) : null}
        </section>
      ) : null}

      <details className="group rounded-2xl bg-slate-900/35">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 sm:px-7 sm:py-6">
          <span className="min-w-0">
            <span className="block text-lg font-semibold text-slate-200">Advanced tools</span>
            <span className="mt-1 block text-sm text-slate-400">Upload predictions, download samples, and export receipts</span>
          </span>
          <ChevronDown className="h-5 w-5 shrink-0 text-slate-400 transition-transform group-open:rotate-180 motion-reduce:transition-none" />
        </summary>
        <div className="border-t border-white/6 p-5 sm:p-7">
          <div className="flex items-center gap-3 text-slate-300"><Upload className="h-5 w-5" /><p className="text-sm font-medium">Local predictions</p></div>
          <h2 className="mt-3 text-2xl font-semibold text-white">Evaluate JSON or JSONL</h2>
          <p className="mt-3 max-w-3xl text-base leading-7 text-slate-400">
            Files stay local. Maximum 5 MiB. Uploads are evaluated separately from frozen evidence and never claim frozen parity or integrity.
            A complete compatible final set of {presentation.finalRecords} records can receive readiness; partial compatible sets receive evaluation only.
          </p>
        <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <label className="min-w-0">
            <span className="block text-sm font-medium text-white">Prediction file</span>
            <input
              type="file"
              accept=".json,.jsonl,application/json,application/x-ndjson"
              disabled={busy}
              onChange={(event) => void handleUpload(event.target.files?.[0])}
              className="mt-2 block min-w-0 max-w-full rounded-xl border border-white/10 bg-slate-950 p-3 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-cyan-300/10 file:px-4 file:py-2 file:font-medium file:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
            />
          </label>
          <Button type="button" variant="secondary" disabled={!sample || busy} onClick={() => sample && dependencies.download(sample, "sample-predictions.json")}>
            <Download className="h-4 w-4" /> Download sample
          </Button>
        </div>
        {!sample ? <p className="mt-2 text-xs text-slate-500">Run an evaluation or select a file to verify and load the sample asset.</p> : null}
        {uploadError ? <p className="mt-4 rounded-xl border border-rose-300/20 bg-rose-300/[0.06] p-4 text-sm text-rose-200" role="alert">{uploadError}</p> : null}
        {upload ? (
          <div className="mt-5 rounded-xl border border-white/8 bg-white/[0.025] p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="font-medium text-white">{upload.provenance.file_name ?? "Local predictions"}</p>
                <p className="mt-1 text-xs text-slate-400">Local-only · {upload.provenance.format.toUpperCase()} · {upload.provenance.bytes.toLocaleString()} bytes</p>
              </div>
              <Badge className={upload.readiness_eligible ? "border-emerald-300/25 bg-emerald-300/8 text-emerald-200" : "border-slate-300/20 bg-slate-300/8 text-slate-200"}>
                {upload.readiness_eligible ? "Readiness eligible" : "Evaluation only"}
              </Badge>
            </div>
            <DefinitionList items={[
              ["Compatible IDs", upload.compatible_ids.length],
              ["Missing IDs", upload.missing_ids.length ? upload.missing_ids.join(", ") : "None"],
              ["Unknown IDs", upload.unknown_ids.length ? upload.unknown_ids.join(", ") : "None"],
            ]} />
            <Button className="mt-5" type="button" disabled={!upload.evaluation_eligible || busy} onClick={() => void runUpload()}>
              <FileJson2 className="h-4 w-4" /> Evaluate local predictions
            </Button>
          </div>
        ) : null}
        </div>
      </details>

      {execution ? (
        <div className="flex flex-col gap-4 border-t border-white/6 px-1 pt-7 text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
            <p className="max-w-4xl text-sm leading-6">
              No model training or inference occurs here. Local receipts prove deterministic content
              hashing, not identity, signature, notarization, or external attestation.
            </p>
          </div>
          <Link href="/run/opsroute-qwen-olmo/" className="shrink-0 text-sm font-medium text-slate-300 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">Open full succession evidence</Link>
        </div>
      ) : null}
    </div>
  );
}
