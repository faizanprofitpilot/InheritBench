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
    copy: "Compare the replacement with the behavior your application already depends on.",
  },
  {
    title: "Recover",
    icon: Wrench,
    copy: "Target the missing behavior and compare recovery candidates without using final-test results.",
  },
  {
    title: "Assure",
    icon: ShieldCheck,
    copy: "Apply the same evaluation and safety rules to decide whether the recovered successor is ready to ship.",
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
            <Badge>Model succession engine</Badge>
            <h1 className="mt-7 text-balance text-5xl font-semibold tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
              Move the model.
              <span className="block text-cyan-200">Keep the capability.</span>
            </h1>
            <p className="mt-7 max-w-2xl text-balance text-lg leading-8 text-slate-300 sm:text-xl">
              Companies replace models and can silently lose behavior their application depends on.
              InheritBench finds what broke, helps recover it, and proves whether the replacement is
              ready to ship.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Button asChild size="lg" className="landing-cta">
                <Link href="/sandbox/">
                  Try the Assurance Lab <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary" className="landing-cta">
                <Link href="/run/opsroute-qwen-olmo/">
                  View the Qwen → OLMo succession <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>

          <div className="relative">
            <Card className="relative overflow-hidden border-0 bg-slate-950/45 p-6 shadow-inner shadow-black/20 sm:p-8">
              <p className="text-sm font-medium text-slate-300">What InheritBench does</p>
              <div className="mt-6 space-y-6">
                <HeroStep number="1" title="Find what broke" copy="Measure which required behaviors disappeared after the model change." />
                <HeroStep number="2" title="Recover the behavior" copy="Target the gaps and select a recovered successor under control." />
                <HeroStep number="3" title="Decide whether to ship" copy="Run final evaluation and safety checks against explicit readiness rules." />
              </div>
              <p className="mt-7 border-t border-white/8 pt-5 text-xs leading-5 text-slate-500">
                The browser evaluates precomputed predictions. Model training and inference happen
                outside the browser.
              </p>
            </Card>
          </div>
        </div>
      </section>

      <section className="px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/45 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="The replacement risk"
            title="A replacement can sound right and still break your application."
            copy="Teams switch models for cost, latency, licensing, infrastructure, or vendor reasons. General benchmarks do not prove that application-specific rules survived the move."
          />
          <div className="mt-10 grid gap-6 rounded-2xl bg-slate-950/40 p-6 sm:p-8 lg:grid-cols-[1.2fr_.8fr] lg:items-center">
            <p className="text-lg leading-8 text-slate-300">
              Plausible text can still use the wrong policy code, bypass an approval, violate a
              contract, or choose an unsafe action. InheritBench tests the behavior the application
              actually requires.
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

      <section id="how-it-works" className="scroll-mt-24 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/55 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="How it works"
            title="Diagnose → Recover → Assure"
            copy="Turn a model replacement into three clear questions: what was lost, can it be recovered, and is the successor ready to ship?"
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

      <section className="px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <Card className="grid-surface mx-auto grid max-w-7xl gap-7 overflow-hidden rounded-3xl border-0 bg-gradient-to-br from-cyan-300/[0.09] via-slate-900/80 to-slate-900/70 p-6 shadow-[0_24px_80px_rgba(2,8,23,.28)] sm:p-9 lg:grid-cols-[1fr_auto] lg:items-center lg:p-12">
          <div>
            <p className="eyebrow">Try it yourself</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-white">
              Choose → Run → Review
            </h2>
            <p className="mt-3 max-w-2xl leading-7 text-slate-400">
              Choose a built-in candidate, run the evaluation in your browser, and review the
              readiness decision. Then introduce a controlled failure and see the decision change.
            </p>
          </div>
          <Button asChild size="lg" className="landing-cta">
            <Link href="/sandbox/">
              Open the Assurance Lab <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </Card>
      </section>

      <section id="reference-result" className="scroll-mt-24 px-4 py-8 pb-16 sm:px-6 sm:py-10 sm:pb-20 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-3xl bg-slate-900/55 p-6 sm:p-9 lg:p-12">
          <SectionHeading
            eyebrow="Reference result"
            title="Qwen capability recovered on an OLMo successor."
            copy="Four recovery candidates were compared without looking at final-test results. Candidate 0 was selected, then evaluated once on clean and adversarial records."
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
                <Link href="/sandbox/">
                  Test this successor <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href="/run/opsroute-qwen-olmo/">Inspect the full evidence</Link>
              </Button>
            </div>
          </div>
        </Card>
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
