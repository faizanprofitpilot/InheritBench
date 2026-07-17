"use client";

import {
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  Clipboard,
  Cpu,
  FileSearch,
  LockKeyhole,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useReducer, useRef } from "react";

import { SuccessionResult } from "@/components/succession-result";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  runBrowserSuccessionReplay,
  type ReplayStage,
  type SuccessionReplayResult,
} from "@/lib/succession-replay";
import { operationOrder } from "@/lib/succession-schema";
import { labelToken } from "@/lib/utils";

type View = "CONFIGURATION" | "PREFLIGHT" | "VERIFYING" | "RESULT" | "FAILED";
type State = {
  view: View;
  completed: ReplayStage[];
  result: SuccessionReplayResult | null;
  error: string | null;
};
type Action =
  | { type: "SHOW"; view: "CONFIGURATION" | "PREFLIGHT" }
  | { type: "START" }
  | { type: "PROGRESS"; stage: ReplayStage }
  | { type: "COMPLETE"; result: SuccessionReplayResult }
  | { type: "FAIL"; error: string };

const initialState: State = {
  view: "CONFIGURATION",
  completed: [],
  result: null,
  error: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "SHOW":
      return { ...initialState, view: action.view };
    case "START":
      return { view: "VERIFYING", completed: [], result: null, error: null };
    case "PROGRESS":
      return state.completed.includes(action.stage)
        ? state
        : { ...state, completed: [...state.completed, action.stage] };
    case "COMPLETE":
      return { ...state, view: "RESULT", result: action.result, error: null };
    case "FAIL":
      return { ...state, view: "FAILED", result: null, error: action.error };
  }
}

export function SuccessionWorkflow() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const search = useSearchParams();
  const router = useRouter();
  const running = useRef(false);
  const completedInSession = useRef(false);

  const execute = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    dispatch({ type: "START" });
    try {
      const result = await runBrowserSuccessionReplay((stage) =>
        dispatch({ type: "PROGRESS", stage }),
      );
      dispatch({ type: "COMPLETE", result });
      completedInSession.current = true;
      router.replace("/run/opsroute-qwen-olmo/?stage=result", { scroll: false });
    } catch (error) {
      dispatch({
        type: "FAIL",
        error: error instanceof Error ? error.message : "Succession replay failed closed.",
      });
    } finally {
      running.current = false;
    }
  }, [router]);

  useEffect(() => {
    const stage = search.get("stage");
    if (stage === "replay" || stage === "result") {
      if (!completedInSession.current) void execute();
    } else if (stage === "preflight") {
      completedInSession.current = false;
      dispatch({ type: "SHOW", view: "PREFLIGHT" });
    } else {
      completedInSession.current = false;
      dispatch({ type: "SHOW", view: "CONFIGURATION" });
    }
  }, [execute, search]);

  if (state.view === "RESULT" && state.result) {
    return <SuccessionResult result={state.result} />;
  }

  if (state.view === "FAILED") {
    return (
      <Card className="mx-auto max-w-3xl border-rose-300/25 p-6 sm:p-8" role="alert">
        <p className="eyebrow text-rose-300">Replay failed closed</p>
        <h1 tabIndex={-1} className="mt-4 text-3xl font-semibold text-white">Frozen evidence could not be verified.</h1>
        <p className="mt-4 leading-7 text-slate-400">{state.error}</p>
        <Button
          type="button"
          className="mt-6"
          onClick={() => {
            router.push("/run/opsroute-qwen-olmo/?stage=preflight");
            dispatch({ type: "SHOW", view: "PREFLIGHT" });
          }}
        >
          <RotateCcw className="h-4 w-4" /> Retry from preflight
        </Button>
      </Card>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[.68fr_1.32fr] lg:items-start">
      <aside className="lg:sticky lg:top-24">
        <p className="eyebrow">Supported succession case</p>
        <h1 className="mt-4 text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          Verify the published Qwen → OLMo succession.
        </h1>
        <p className="mt-5 text-lg leading-8 text-slate-400">
          Run a deterministic, GPU-free evidence replay and receive a fresh migration-readiness report in this browser.
        </p>
        <ol className="mt-8 space-y-3" aria-label="Workflow stages">
          {[
            ["CONFIGURATION", "Supported configuration"],
            ["PREFLIGHT", "Replay preflight"],
            ["VERIFYING", "Verified replay"],
            ["RESULT", "Readiness outcome"],
          ].map(([view, label], index) => {
            const order = ["CONFIGURATION", "PREFLIGHT", "VERIFYING", "RESULT"];
            const current = order.indexOf(state.view === "FAILED" ? "VERIFYING" : state.view);
            const item = order.indexOf(view);
            return (
              <li
                key={view}
                aria-current={current === item ? "step" : undefined}
                className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${
                  current === item
                    ? "border-cyan-300/25 bg-cyan-300/7 text-cyan-100"
                    : item < current
                      ? "border-emerald-300/15 text-emerald-200"
                      : "border-white/8 text-slate-500"
                }`}
              >
                {item < current ? <Check className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
                <span>{index + 1}. {label}</span>
              </li>
            );
          })}
        </ol>
      </aside>

      {state.view === "CONFIGURATION" && (
        <Card className="p-6 sm:p-8" data-testid="succession-configuration">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="eyebrow">Locked configuration</p>
              <h2 className="mt-3 text-2xl font-semibold text-white">OpsRoute v0.1.0</h2>
            </div>
            <Badge>First supported case</Badge>
          </div>
          <dl className="mt-7 divide-y divide-white/8 border-y border-white/8">
            <Configuration label="Source" value="Adapted Qwen2.5 0.5B Instruct" />
            <Configuration label="Target" value="OLMo-2 1B Instruct" />
            <Configuration label="Transfer" value="Anchored Behavioral Transfer" />
            <Configuration label="Supervision" value="214 teacher outputs + 10 direct anchors" />
            <Configuration label="Profile" value="Maximum confirmed capability" />
            <Configuration label="Execution" value="Verified replay — no model execution" />
          </dl>
          <p className="mt-5 text-sm leading-6 text-slate-500">
            The supported configuration is intentionally read-only. Arbitrary models, uploads, and hosted training are not enabled in v0.1.
          </p>
          <Button
            type="button"
            size="lg"
            className="mt-7"
            onClick={() => router.push("/run/opsroute-qwen-olmo/?stage=preflight")}
          >
            Review replay preflight <ArrowRight className="h-4 w-4" />
          </Button>
        </Card>
      )}

      {state.view === "PREFLIGHT" && (
        <Card className="p-6 sm:p-8" data-testid="succession-preflight">
          <p className="eyebrow">Replay preflight</p>
          <h2 className="mt-3 text-3xl font-semibold text-white">Understand precisely what will run.</h2>
          <div className="mt-7 grid gap-4 sm:grid-cols-2">
            <PreflightItem icon={<FileSearch className="h-5 w-5" />} title="Verifies frozen evidence" copy="Hashes committed atomic records and derives the migration outcome." />
            <PreflightItem icon={<ShieldCheck className="h-5 w-5" />} title="Generates fresh outputs" copy="Creates a readiness report and replay receipt in your browser." />
            <PreflightItem icon={<Cpu className="h-5 w-5" />} title="No model execution" copy="No training, inference, GPU, model download, or API key is required." />
            <PreflightItem icon={<LockKeyhole className="h-5 w-5" />} title="Fails closed" copy="Any schema, record, manifest, adapter, or hash mismatch stops the replay." />
          </div>
          <div className="mt-7 rounded-xl border border-violet-300/15 bg-violet-300/5 p-4 text-sm leading-6 text-violet-100/80">
            The full phased CLI performs supervision preparation, training, evaluation, checkpoint selection, and export locally. This hosted action verifies the already published succession.
          </div>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button
              type="button"
              size="lg"
              onClick={() => {
                router.push("/run/opsroute-qwen-olmo/?stage=replay", { scroll: false });
                void execute();
              }}
            >
              Run verified succession replay <ArrowRight className="h-4 w-4" />
            </Button>
            <Button type="button" size="lg" variant="secondary" onClick={() => router.push("/run/opsroute-qwen-olmo/")}>Back</Button>
          </div>
        </Card>
      )}

      {state.view === "VERIFYING" && (
        <Card className="p-6 sm:p-8" aria-live="polite" data-testid="succession-progress">
          <p className="eyebrow">Verified replay in progress</p>
          <h2 tabIndex={-1} className="mt-3 text-3xl font-semibold text-white">Deriving readiness from frozen evidence.</h2>
          <ol className="mt-7 divide-y divide-white/8 border-y border-white/8">
            {operationOrder.map((operation) => {
              const passed = state.completed.includes(operation);
              return (
                <li key={operation} className="flex items-center gap-3 py-3 text-sm">
                  {passed ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                  ) : (
                    <Circle className="h-4 w-4 text-slate-700" />
                  )}
                  <span className={passed ? "text-slate-200" : "text-slate-500"}>{labelToken(operation)}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-5 text-sm text-slate-500">No timers or simulated work. Each item marks a completed validation operation.</p>
        </Card>
      )}
    </div>
  );
}

function Configuration({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr] sm:gap-5">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-100">{value}</dd>
    </div>
  );
}

function PreflightItem({ icon, title, copy }: { icon: React.ReactNode; title: string; copy: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] p-5">
      <span className="text-cyan-300">{icon}</span>
      <h3 className="mt-4 font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-400">{copy}</p>
    </div>
  );
}

export function FullWorkflowInstructions() {
  const command = "uv run inheritbench succession preflight --case opsroute-qwen-olmo --mode full --json -";
  return (
    <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(command)}>
      <Clipboard className="h-4 w-4" /> Copy full-workflow preflight
    </Button>
  );
}
