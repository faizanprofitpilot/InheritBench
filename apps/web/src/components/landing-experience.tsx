"use client";

import {
  ArrowRight,
  Boxes,
  Braces,
  CheckCircle2,
  FileCheck2,
  GitBranch,
  LockKeyhole,
  Radar,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { ReferenceSuccession } from "@/lib/data";

const stages = [
  {
    title: "Diagnose",
    icon: Radar,
    copy: "Verify the source capability, measure the untouched target, and isolate lost behavior and coverage gaps.",
    bullets: ["Source verification", "Target regression measurement", "Coverage-group diagnosis"],
  },
  {
    title: "Recover",
    icon: Wrench,
    copy: "Build trusted supervision, request targeted anchors, train bounded candidates, and rank on validation only.",
    bullets: ["Deficit-driven anchors", "Multi-start recovery", "Validation-only selection"],
  },
  {
    title: "Assure",
    icon: ShieldCheck,
    copy: "Freeze the candidate, run sealed evaluation, verify reload and replay, then issue a readiness decision.",
    bullets: ["Sealed final surfaces", "Immutable evidence", "PASS, conditional, or blocked"],
  },
];

const capabilities = [
  ["Declarative capability packs", Braces],
  ["Source and target diagnosis", Radar],
  ["Direct and anchored recovery", GitBranch],
  ["Multi-start candidate selection", Boxes],
  ["Sealed final evaluation", LockKeyhole],
  ["Immutable evidence and replay", FileCheck2],
] as const;

export function LandingExperience({ reference }: { reference: ReferenceSuccession }) {
  const reducedMotion = useReducedMotion();
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
  const replay = record(bundle.replay_verification);
  const sourceName = shortModel(source.model_id, "Qwen source");
  const targetName = shortModel(target.model_id, "OLMo target");

  return (
    <>
      <section id="product" className="grid-surface relative overflow-hidden border-b border-white/8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(34,211,238,.12),transparent_28rem)]" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 sm:py-24 lg:grid-cols-[1.03fr_.97fr] lg:items-center lg:px-8 lg:py-28">
          <motion.div
            initial={reducedMotion ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.45 }}
          >
            <div className="flex flex-wrap gap-2">
              <Badge>Model succession engine</Badge>
              <Badge>Completed reference succession</Badge>
            </div>
            <h1 className="mt-7 text-balance text-5xl font-semibold tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
              Move the model.
              <span className="block text-cyan-200">Keep the capability.</span>
            </h1>
            <p className="mt-7 max-w-2xl text-balance text-lg leading-8 text-slate-300 sm:text-xl">
              InheritBench measures learned-capability loss during model replacement, executes
              controlled recovery strategies, and produces evidence-backed deployment decisions.
            </p>
            <p className="mt-4 font-mono text-sm text-slate-500">Diagnose → Recover → Assure</p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Button asChild size="lg" className="landing-cta">
                <Link href="/run/opsroute-qwen-olmo/">
                  View the Qwen → OLMo succession <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary" className="landing-cta">
                <a href="#how-it-works">Explore the workflow <ArrowRight className="h-4 w-4" /></a>
              </Button>
            </div>
          </motion.div>

          <motion.div
            initial={reducedMotion ? false : { opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.5, delay: reducedMotion ? 0 : 0.15 }}
          >
            <Card className="relative overflow-hidden p-6 sm:p-8">
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Reference succession</p>
                  <p className="mt-2 text-sm text-slate-500">{bundle.capability.id}@{bundle.capability.version}</p>
                </div>
                <Status status={bundle.readiness.status} />
              </div>
              <div className="mt-8 space-y-3">
                <FlowRow label="Source" value={sourceName} state="Capability verified" />
                <FlowArrow label="Capability loss detected" />
                <FlowRow label="Target" value={targetName} state="Untouched baseline assessed" warning />
                <FlowArrow label="Anchored behavioral transfer" />
                <FlowRow label="Successor" value={`${targetName} + adapter`} state={bundle.readiness.status} selected />
              </div>
              <div className="mt-7 grid grid-cols-3 gap-3 border-t border-white/8 pt-6">
                <HeroMetric label="Clean operational" value={`${clean.operational_semantic_correct}/${clean.records}`} />
                <HeroMetric label="Exact contracts" value={`${clean.exact_full_contract}/${clean.records}`} />
                <HeroMetric label="Replay" value={`${number(replay.anchored_record_count) + number(replay.direct_record_count)}/${number(replay.anchored_record_count) + number(replay.direct_record_count)}`} />
              </div>
            </Card>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <SectionHeading
          eyebrow="The silent-regression problem"
          title="A successful model swap can still break the behavior your business depends on."
          copy="Teams change model families for cost, latency, licensing, or infrastructure reasons. Standard benchmarks do not prove that organization-specific routing, approvals, policies, or action contracts survived."
        />
        <div className="mt-10 grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
          <Card className="p-6 sm:p-8">
            <p className="text-lg leading-8 text-slate-300">
              A replacement may generate plausible text while silently returning the wrong policy
              code, bypassing an approval, or selecting an unauthorized action.
            </p>
            <p className="mt-5 rounded-xl border border-rose-300/20 bg-rose-300/[0.04] p-5 text-sm leading-7 text-rose-100/85">
              In OpsRoute, the untouched OLMo target completed inference but retained{" "}
              <strong className="text-white">{String(record(bundle.readiness).target_baseline ? record(record(bundle.readiness).target_baseline).semantic_correct : 0)}</strong>{" "}
              of {String(record(record(bundle.readiness).target_baseline).expected ?? 0)} measured source-gate behaviors.
            </p>
          </Card>
          <Card className="p-6 sm:p-8">
            <p className="eyebrow">The product question</p>
            <ol className="mt-5 space-y-4 text-sm leading-7 text-slate-300">
              <li><strong className="text-white">01.</strong> What capability was lost?</li>
              <li><strong className="text-white">02.</strong> Can it be recovered under control?</li>
              <li><strong className="text-white">03.</strong> Is the recovered successor ready to deploy?</li>
            </ol>
          </Card>
        </div>
      </section>

      <section id="how-it-works" className="border-y border-white/8 bg-white/[0.018]">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
          <SectionHeading
            eyebrow="How it works"
            title="Diagnose → Recover → Assure"
            copy="A model replacement becomes an inspectable engineering process, with final-test evidence sealed until selection."
          />
          <div className="mt-12 grid gap-5 lg:grid-cols-3">
            {stages.map((stage, index) => (
              <Card key={stage.title} className="p-6 sm:p-7">
                <div className="flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/8 text-cyan-200">
                    <stage.icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-sm text-cyan-300">0{index + 1}</span>
                </div>
                <h3 className="mt-7 text-2xl font-semibold text-white">{stage.title}</h3>
                <p className="mt-3 leading-7 text-slate-400">{stage.copy}</p>
                <ul className="mt-6 space-y-2 border-t border-white/8 pt-5 text-sm text-slate-300">
                  {stage.bullets.map((bullet) => <li key={bullet}>• {bullet}</li>)}
                </ul>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="reference-run" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <SectionHeading
          eyebrow="Reference result"
          title="Qwen capability recovered on an OLMo successor."
          copy="Candidate 0 was selected using validation evidence only, then evaluated once on sealed clean and adversarial surfaces."
        />
        <Card className="mt-10 overflow-hidden border-cyan-300/20 p-6 sm:p-8">
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
              <ResultMetric label="Clean operational" value={`${clean.operational_semantic_correct} / ${clean.records}`} />
              <ResultMetric label="Exact contracts" value={`${clean.exact_full_contract} / ${clean.records}`} />
              <ResultMetric label="Strict validity" value={`${clean.historical_strict_valid} / ${clean.records}`} />
              <ResultMetric label="Clean safety blockers" value={String(clean.blocker_safety_findings)} />
              <ResultMetric label="Replay verified" value={String(number(replay.anchored_record_count) + number(replay.direct_record_count))} />
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
            <Button asChild>
              <Link href="/run/opsroute-qwen-olmo/">
                Inspect the completed run <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </Card>
      </section>

      <section className="border-y border-white/8 bg-white/[0.018]">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
          <SectionHeading
            eyebrow="Product capability"
            title="OpsRoute is the reference pack, not the product boundary."
            copy="InheritBench provides a reproducible succession workflow for structured capability contracts while staying explicit about what the current release supports."
          />
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map(([label, Icon]) => (
              <div key={label} className="flex items-center gap-4 rounded-xl border border-white/9 bg-black/20 p-5">
                <Icon className="h-5 w-5 text-cyan-300" />
                <span className="font-medium text-slate-200">{label}</span>
              </div>
            ))}
          </div>
          <div className="mt-8 rounded-xl border border-amber-300/15 bg-amber-300/[0.035] p-6">
            <p className="font-semibold text-white">Current supported boundary</p>
            <p className="mt-3 text-sm leading-7 text-slate-400">
              Structured JSON capability contracts; the pinned Qwen and OLMo reference path; local
              execution; and an Apple MPS reference environment. This release does not claim
              arbitrary-model universal support or guaranteed production safety.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <Card className="grid-surface overflow-hidden border-cyan-300/20 p-8 text-center sm:p-12">
          <Badge className="mx-auto">Evidence before deployment</Badge>
          <h2 className="mt-6 text-balance text-4xl font-semibold tracking-tight text-white">
            Don’t migrate on benchmark scores alone.
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg leading-8 text-slate-400">
            Inspect the diagnosis, recovery, selection boundary, sealed readiness result, and
            replayable evidence behind the completed succession.
          </p>
          <Button asChild size="lg" className="landing-cta mx-auto mt-8">
            <Link href="/run/opsroute-qwen-olmo/">
              Inspect the completed succession <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </Card>
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

function FlowRow({ label, value, state, warning = false, selected = false }: { label: string; value: string; state: string; warning?: boolean; selected?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${selected ? "border-cyan-300/30 bg-cyan-300/[0.06]" : warning ? "border-rose-300/20 bg-rose-300/[0.035]" : "border-white/9 bg-black/20"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs uppercase tracking-[0.12em] text-slate-500">{label}</span>
        <span className="text-xs text-slate-400">{state}</span>
      </div>
      <p className="mt-2 font-semibold text-white">{value}</p>
    </div>
  );
}

function FlowArrow({ label }: { label: string }) {
  return <p className="flex items-center gap-2 px-3 text-xs text-slate-500"><ArrowRight className="h-4 w-4 text-cyan-300" /> {label}</p>;
}

function Status({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-3 py-1.5 text-xs font-semibold tracking-[0.08em] text-amber-100">
      <CheckCircle2 className="h-4 w-4" /> {status.replaceAll("_", " ")}
    </span>
  );
}

function HeroMetric({ label, value }: { label: string; value: string }) {
  return <div><p className="font-mono text-lg font-semibold text-white">{value}</p><p className="mt-1 text-[0.68rem] leading-4 text-slate-500">{label}</p></div>;
}
function ResultLine({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs uppercase tracking-[0.12em] text-slate-500">{label}</dt><dd className="mt-2 font-medium text-white">{value}</dd></div>;
}
function ResultMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-white/9 bg-black/20 p-4"><p className="font-mono text-xl font-semibold text-white">{value}</p><p className="mt-2 text-xs leading-5 text-slate-500">{label}</p></div>;
}
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function number(value: unknown): number {
  return typeof value === "number" ? value : 0;
}
function shortModel(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  return value.split("/").at(-1)?.replace("-Instruct", "") ?? value;
}
