"use client";

import { ArrowRight, CheckCircle2, Radar, ShieldCheck, Wrench } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { ReferenceSuccession } from "@/lib/data";

const stages = [
  {
    title: "Diagnose",
    icon: Radar,
    copy: "Validate the capability pack, verify the adapted source, and measure what the untouched target lost.",
  },
  {
    title: "Recover",
    icon: Wrench,
    copy: "Train a fresh target adapter, add authorized anchors only when required, and select using validation evidence.",
  },
  {
    title: "Assure",
    icon: ShieldCheck,
    copy: "Open final records after selection, apply deterministic readiness rules, export, reload, and replay.",
  },
];

const capabilityTree = `capability.yaml
schemas/
evaluator.yaml
rules/
data/
oracles/
anchors/`;

const workflowCommands = [
  {
    number: "01",
    title: "Define and validate",
    copy: "Author model-visible records, evaluator-only contracts, schemas, vocabularies, safety rules, coverage groups, and readiness thresholds.",
    command: `uv run inheritbench capability validate \\
  capabilities/opsroute/v0.2.0`,
  },
  {
    number: "02",
    title: "Freeze the succession plan",
    copy: "Resolve supported registry entries, validate authorized inputs, and hash the plan before model compute starts.",
    command: `uv run inheritbench succession plan \\
  --pack capabilities/opsroute/v0.2.0 \\
  --source-config configs/models/source.yaml \\
  --target-config configs/models/target.yaml \\
  --strategy anchored-behavioral-transfer-v0.1 \\
  --output runs`,
  },
  {
    number: "03",
    title: "Execute or intervene",
    copy: "Verify the source, diagnose target loss, prepare supervision, train the target adapter, and pause for explicitly authorized anchors when coverage is insufficient.",
    command: `uv run inheritbench succession run \\
  --plan runs/<run-id> \\
  --device mps`,
  },
  {
    number: "04",
    title: "Inspect, replay, and export",
    copy: "Review readiness and residuals, reconstruct the decision, or create a browser-inspectable bundle.",
    command: `uv run inheritbench succession inspect --run runs/<run-id> --json -
uv run inheritbench succession replay --run runs/<run-id> --output runs/replays
uv run inheritbench succession export-web --run runs/<run-id> --output web_bundle.json`,
  },
];

export function LandingExperience({ reference }: { reference: ReferenceSuccession }) {
  const bundle = reference.bundle;
  if (bundle.schema_version !== "inheritbench.web-bundle.v0.4") {
    throw new Error("The completed reference succession requires a v0.4 bundle.");
  }
  const plan = record(reference.audit.canonicalPlan);
  const source = record(plan.source);
  const target = record(plan.target);
  const comparison = record(bundle.final_comparison);
  const anchored = record(comparison.anchored);
  const metrics = record(anchored.metrics);
  const clean = record(metrics.confirmatory);
  const adversarial = record(metrics.adversarial);
  const blockerCases = record(adversarial.blocker_cases);
  const sourceName = shortModel(source.model_id, "Qwen source");
  const targetName = shortModel(target.model_id, "OLMo target");

  return (
    <>
      <section id="product" className="px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="grid-surface relative mx-auto grid max-w-7xl gap-12 overflow-hidden rounded-3xl bg-slate-900/70 px-6 py-12 shadow-[0_30px_100px_rgba(2,8,23,.32)] sm:px-9 sm:py-16 lg:grid-cols-[1.03fr_.97fr] lg:items-center lg:px-12 lg:py-20">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_8%,rgba(34,211,238,.1),transparent_28rem)]" />
          <div className="relative">
            <Badge>Local model-succession CLI</Badge>
            <h1 className="mt-7 text-balance text-5xl font-semibold tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
              Move the model.
              <span className="block text-cyan-200">Keep the capability.</span>
            </h1>
            <p className="mt-7 max-w-2xl text-balance text-lg leading-8 text-slate-300 sm:text-xl">
              Fine-tuned behavior does not automatically move when the underlying model changes.
              InheritBench gives developers a controlled local CLI workflow to diagnose what was
              lost, recover a successor, and prove whether the migration is ready to ship.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Button asChild size="lg" className="landing-cta">
                <Link href="#developer-workflow">
                  See the developer workflow <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary" className="landing-cta">
                <Link href="/run/opsroute-qwen-olmo/">
                  Inspect the Qwen → OLMo succession <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
            <Link
              href="/sandbox/"
              className="mt-5 inline-flex items-center gap-2 rounded-sm text-sm font-medium text-slate-300 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
            >
              Try the Assurance Lab <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="relative">
            <Card className="relative overflow-hidden border-0 bg-slate-950/45 p-6 shadow-inner shadow-black/20 sm:p-8">
              <p className="text-sm font-medium text-slate-300">Local developer workflow</p>
              <div className="mt-6 space-y-6">
                <HeroStep number="1" title="Define the capability contract" copy="Package examples, expected outputs, safety rules, coverage, and readiness thresholds." />
                <HeroStep number="2" title="Run a controlled succession" copy="Verify the source, diagnose target loss, recover, and select without final-test leakage." />
                <HeroStep number="3" title="Export replayable evidence" copy="Produce the successor adapter, readiness decision, residual failures, and replay bundle." />
              </div>
              <p className="mt-7 border-t border-white/8 pt-5 text-xs leading-5 text-slate-500">
                The CLI performs model loading, training, selection, and export. Browser surfaces
                inspect and test the evidence that a succession run produced.
              </p>
            </Card>
          </div>
        </div>
      </section>

      <section className="px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/45 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="The replacement risk"
            title="A replacement can sound intelligent and still lose the capability you fine-tuned."
            copy="Teams switch models for cost, latency, privacy, licensing, infrastructure, or vendor reasons. General benchmarks do not prove that learned policies, contracts, tool use, approvals, and safety behavior survived the move."
          />
          <div className="mt-10 grid gap-6 rounded-2xl bg-slate-950/40 p-6 sm:p-8 lg:grid-cols-[1.2fr_.8fr] lg:items-center">
            <p className="text-lg leading-8 text-slate-300">
              Plausible text can still use the wrong policy code, bypass an approval, violate a
              contract, or choose an unsafe action. Model succession makes that portability problem
              explicit before a replacement ships.
            </p>
            <p className="rounded-2xl bg-rose-300/[0.06] p-5 text-sm leading-7 text-rose-100/85">
              The reference replacement produced valid-looking output while preserving only{" "}
              <strong className="text-white">
                {String(record(record(bundle.readiness).target_baseline).semantic_correct ?? 0)} of{" "}
                {String(record(record(bundle.readiness).target_baseline).expected ?? 0)}
              </strong>{" "}
              required behaviors.
            </p>
          </div>
        </div>
      </section>

      <section id="developer-workflow" className="scroll-mt-24 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/55 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="How developers use InheritBench"
            title="Define the capability. Freeze the plan. Execute the succession."
            copy="A developer owns the capability contract and selects a supported source, target, and recovery strategy. The CLI owns ordered execution, evidence separation, readiness, export, and replay."
          />
          <div className="mt-10 grid gap-6 lg:grid-cols-[.72fr_1.28fr]">
            <Card className="border-0 bg-slate-950/40 p-6 shadow-none sm:p-7">
              <p className="text-sm font-medium text-slate-300">Developer-authored capability pack</p>
              <pre
                tabIndex={0}
                aria-label="Example capability pack structure"
                className="mt-5 overflow-auto rounded-2xl bg-black/25 p-5 font-mono text-sm leading-7 text-cyan-100"
              >
                {capabilityTree}
              </pre>
              <p className="mt-5 text-sm leading-6 text-slate-400">
                Model-visible inputs stay separate from evaluator-only contracts and final records.
                Packs become executable only after strict validation.
              </p>
            </Card>
            <div className="grid gap-4 sm:grid-cols-2">
              {workflowCommands.map((step) => (
                <WorkflowCommand key={step.number} {...step} />
              ))}
            </div>
          </div>
          <div className="mt-10 rounded-2xl bg-amber-300/[0.055] p-6">
            <p className="font-semibold text-amber-100">When coverage is insufficient</p>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
              An anchored run may stop at <code className="text-amber-100">ANCHORS_REQUIRED</code>,
              identify the deficient group and required count, and wait for explicitly authorized
              original examples. The developer adds anchors and resumes the same frozen plan without
              regenerating completed teacher evidence.
            </p>
            <pre
              tabIndex={0}
              aria-label="Add anchors and resume commands"
              className="mt-4 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-black/20 p-4 font-mono text-xs leading-6 text-slate-200"
            >{`uv run inheritbench succession add-anchors --run runs/<run-id> --records anchors/approved-anchors.jsonl
uv run inheritbench succession resume --run runs/<run-id> --device mps`}</pre>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-24 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/45 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="Engine stages"
            title="Diagnose → Recover → Assure"
            copy="These are ordered CLI stages—not browser steps. The engine preserves the boundary between recovery evidence and sealed final evaluation."
          />
          <div className="mt-12 grid gap-5 lg:grid-cols-3">
            {stages.map((stage, index) => (
              <Card key={stage.title} className="border-0 bg-slate-950/40 p-6 shadow-none sm:p-7">
                <div className="flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-xl bg-cyan-300/10 text-cyan-200">
                    <stage.icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-sm text-cyan-300">0{index + 1}</span>
                </div>
                <h3 className="mt-7 text-2xl font-semibold text-white">{stage.title}</h3>
                <p className="mt-3 leading-7 text-slate-400">{stage.copy}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="reference-result" className="scroll-mt-24 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/55 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="Proof of execution"
            title="The CLI completed a real Qwen → OLMo succession."
            copy="An adapted Qwen source and untouched OLMo target used different model architectures. Direct recovery undercovered important cases; anchored recovery added ten targeted original examples, completed four seeded candidates, and selected Candidate 0 using validation only before final records opened."
          />
        <Card className="mt-10 overflow-hidden border-0 bg-slate-950/40 p-6 shadow-none sm:p-8">
          <div className="grid gap-7 lg:grid-cols-[.8fr_1.2fr]">
            <div>
              <Status status={bundle.readiness.status} />
              <dl className="mt-7 space-y-5">
                <ResultLine label="Source" value={sourceName} />
                <ResultLine label="Successor" value={targetName} />
                <ResultLine label="Selected candidate" value={`Candidate ${bundle.selection.candidate_index}`} />
              </dl>
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <ResultMetric label="Operational correctness" value={`${clean.operational_semantic_correct} / ${clean.records}`} />
              <ResultMetric label="Exact-contract fidelity" value={`${clean.exact_full_contract} / ${clean.records}`} />
              <ResultMetric label="Strict validity" value={`${clean.historical_strict_valid} / ${clean.records}`} />
              <ResultMetric label="Clean safety blockers" value={String(clean.blocker_safety_findings)} />
              <ResultMetric label="Adversarial exact result" value={`${adversarial.exact_full_contract} / ${adversarial.records}`} />
              <ResultMetric label="Adversarial strict validity" value={`${adversarial.historical_strict_valid} / ${adversarial.records}`} />
              <ResultMetric
                label="Safety findings"
                value={`${adversarial.blocker_safety_findings} on ${Object.keys(blockerCases).length} adversarial record`}
              />
              <ResultMetric label="Readiness" value={bundle.readiness.status} />
            </div>
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-white/8 pt-6">
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              Clean behavior recovered fully. Adversarial evidence retained{" "}
              {String(adversarial.blocker_safety_findings)} safety findings on
              {` ${Object.keys(blockerCases).length} record${Object.keys(blockerCases).length === 1 ? "" : "s"}`},
              producing a conditional deployment decision.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild>
                <Link href="/run/opsroute-qwen-olmo/">
                  Inspect the full succession <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href="/sandbox/">Test the assurance result</Link>
              </Button>
            </div>
          </div>
        </Card>
        </div>
      </section>

      <section className="px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <Card className="grid-surface mx-auto grid max-w-7xl gap-7 overflow-hidden rounded-3xl border-0 bg-gradient-to-br from-cyan-300/[0.09] via-slate-900/80 to-slate-900/70 p-6 shadow-[0_24px_80px_rgba(2,8,23,.28)] sm:p-9 lg:grid-cols-[1fr_auto] lg:items-center lg:p-12">
          <div>
            <p className="eyebrow">Judge verification</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-white">
              Test the assurance layer in your browser.
            </h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              The Assurance Lab is not the model-migration engine. It evaluates frozen or locally
              uploaded predictions, recomputes safety and readiness, applies controlled mutations,
              verifies integrity, and creates unsigned local receipts. Model loading, training, and
              inference remain offline CLI operations.
            </p>
          </div>
          <Button asChild size="lg" className="landing-cta">
            <Link href="/sandbox/">
              Try the Assurance Lab <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </Card>
      </section>

      <section className="px-4 py-8 pb-16 sm:px-6 sm:py-10 sm:pb-20 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/45 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="Current boundary"
            title="Generic capability contracts. Explicitly supported model execution."
            copy="Developers can author structured-JSON capability packs. Real execution currently supports the pinned Qwen2.5-0.5B → OLMo-2-1B registry and has been demonstrated on Apple MPS with OpsRoute. Other architectures require a validated registry and adapter integration."
          />
          <p className="mt-6 max-w-4xl text-sm leading-7 text-slate-400">
            Purchase Approval is fixture-only. The reference uses verified frozen teacher outputs;
            live generic teacher generation is not yet proven. Recovery is not guaranteed, and the
            engine may correctly return <code className="text-slate-200">MIGRATION_BLOCKED</code>.
          </p>
        </div>
      </section>
    </>
  );
}

function SectionHeading({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="max-w-3xl">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl lg:text-5xl">{title}</h2>
      <p className="mt-5 text-lg leading-8 text-slate-400">{copy}</p>
    </div>
  );
}

function HeroStep({ number, title, copy }: { number: string; title: string; copy: string }) {
  return (
    <div className="flex gap-4">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-cyan-300/10 text-sm font-semibold text-cyan-200">
        {number}
      </span>
      <div>
        <p className="font-semibold text-white">{title}</p>
        <p className="mt-1 text-sm leading-6 text-slate-400">{copy}</p>
      </div>
    </div>
  );
}

function WorkflowCommand({
  number,
  title,
  copy,
  command,
}: {
  number: string;
  title: string;
  copy: string;
  command: string;
}) {
  return (
    <Card className="min-w-0 border-0 bg-slate-950/40 p-5 shadow-none sm:p-6">
      <span className="font-mono text-sm text-cyan-300">{number}</span>
      <h3 className="mt-3 text-xl font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-400">{copy}</p>
      <pre
        tabIndex={0}
        aria-label={`${title} command`}
        className="mt-4 max-w-full overflow-auto whitespace-pre-wrap break-words rounded-xl bg-black/25 p-4 font-mono text-xs leading-6 text-slate-200"
      >
        {command}
      </pre>
    </Card>
  );
}

function Status({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-amber-300/10 px-3 py-1.5 text-xs font-semibold tracking-[0.08em] text-amber-100">
      <CheckCircle2 className="h-4 w-4" /> {status.replaceAll("_", " ")}
    </span>
  );
}

function ResultLine({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs uppercase tracking-[0.12em] text-slate-500">{label}</dt><dd className="mt-2 font-medium text-white">{value}</dd></div>;
}
function ResultMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl bg-slate-900/70 p-4"><p className="font-mono text-xl font-semibold text-white">{value}</p><p className="mt-2 text-xs leading-5 text-slate-400">{label}</p></div>;
}
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function shortModel(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  return value.split("/").at(-1)?.replace("-Instruct", "") ?? value;
}
