"use client";

import {
  ArrowRight,
  BadgeCheck,
  Boxes,
  BrainCircuit,
  CircleGauge,
  GitBranch,
  GitMerge,
  Radar,
  Route,
  ShieldAlert,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Story, SystemSummary } from "@/lib/data-schema";
import { labelSystem } from "@/lib/utils";

type Fact = Story["facts"][number];
type Tone = "cyan" | "rose" | "amber" | "violet" | "green";

const workflow = [
  {
    icon: CircleGauge,
    title: "Measure the capability break",
    copy: "Compare the adapted source and untouched successor against the same operational contract.",
    signal: "Capability retention, contract validity, and safety.",
  },
  {
    icon: GitBranch,
    title: "Test recovery paths",
    copy: "Evaluate retraining, limited-data recovery, behavioral distillation, and anchored transfer.",
    signal: "Performance, data, compute, and complexity.",
  },
  {
    icon: Radar,
    title: "Stress-test the candidates",
    copy: "Separate clean capability retention from adversarial resilience and operational failure modes.",
    signal: "Confirmatory and adversarial surfaces remain distinct.",
  },
  {
    icon: Route,
    title: "Choose under constraints",
    copy: "Receive a recommendation based on data access, teacher availability, safety, complexity, and resilience.",
    signal: "Every recommendation links back to immutable evidence.",
  },
];

const exploration = [
  {
    href: "/lab/opsroute/methods",
    icon: Boxes,
    title: "Compare recovery paths",
    copy: "Explore capability, safety, direct-label use, synthetic dependence, compute, and pipeline complexity.",
    cta: "Compare methods",
  },
  {
    href: "/lab/opsroute/failures",
    icon: ShieldAlert,
    title: "Inspect exact failures",
    copy: "Review selected inputs, expected contracts, raw outputs, parser results, and deterministic failure classifications.",
    cta: "Open failure explorer",
  },
  {
    href: "/lab/opsroute/memo",
    icon: BrainCircuit,
    title: "Read the migration recommendation",
    copy: "Review the validated GPT-5.6 Succession Memo and trace every substantive claim back to evidence.",
    cta: "View recommendation",
  },
  {
    href: "/lab/opsroute/evidence",
    icon: BadgeCheck,
    title: "Verify the evidence",
    copy: "Inspect hashes, commits, artifacts, and the GPU-free replay path behind the published case.",
    cta: "Open evidence",
  },
];

export function LandingExperience({ story, systems }: { story: Story; systems: SystemSummary[] }) {
  const reducedMotion = useReducedMotion();
  const facts = new Map(story.facts.map((fact) => [fact.fact_id, fact]));
  const source = getSystem(systems, "source_adapted_full");
  const untouched = getSystem(systems, "target_untouched");
  const full = getSystem(systems, "target_full_retrain");
  const anchored = getSystem(systems, "target_hybrid_anchored_distillation_10");
  const independentAccepted = getFact(facts, "independent-accepted");
  const independentCandidates = getFact(facts, "independent-candidates");
  const independentArchetypes = getFact(facts, "independent-archetypes");
  const matchedAccepted = getFact(facts, "matched-accepted");
  const blindspotAccepted = getFact(facts, "blindspot-accepted");
  const teacherLabels = getFact(facts, "hybrid-teacher-labels");
  const anchorLabels = getFact(facts, "hybrid-anchor-labels");
  const upstreamLabels = getFact(facts, "upstream-teacher-labels");
  const distributionLabels = getFact(facts, "distribution-design-labels");

  const heroTransition = reducedMotion
    ? { duration: 0.01 }
    : { duration: 0.48, ease: [0.22, 1, 0.36, 1] as const };
  const heroItem = {
    hidden: reducedMotion ? { opacity: 1 } : { opacity: 0, y: 18 },
    visible: { opacity: 1, y: 0, transition: heroTransition },
  };

  const caseStages = [
    {
      eyebrow: "Capability established",
      metrics: [formatPercent(source.confirmatory_semantic)],
      labels: ["Adapted Qwen confirmatory capability"],
      copy: "The source model learned the OpsRoute operational contract.",
      tone: "cyan" as Tone,
    },
    {
      eyebrow: "Family replaced",
      metrics: [formatPercent(untouched.confirmatory_semantic)],
      labels: ["Untouched OLMo confirmatory capability"],
      copy: "The replacement model ran successfully but did not preserve the learned behavior.",
      tone: "rose" as Tone,
    },
    {
      eyebrow: "Pure transfer tested",
      metrics: [
        `${independentAccepted.display_value} / ${independentCandidates.display_value} accepted`,
        slashRatio(independentArchetypes),
      ],
      labels: ["Accepted independent teacher outputs", "Archetypes covered"],
      copy: "Independent behavioral distillation failed at the data gate.",
      tone: "amber" as Tone,
    },
    {
      eyebrow: "Blind spot localized",
      metrics: [`${slashRatio(matchedAccepted)} accepted`, slashRatio(blindspotAccepted)],
      labels: ["Distribution-matched teacher outputs", "Duplicate auto-refund outputs accepted"],
      copy: "Matching the training distribution repaired the broad coverage failure and exposed one concentrated teacher blind spot.",
      tone: "violet" as Tone,
    },
    {
      eyebrow: "Anchored recovery",
      metrics: [formatPercent(anchored.confirmatory_semantic)],
      labels: ["Anchored-transfer confirmatory capability"],
      copy: `${anchorLabels.display_value} direct original anchors and ${teacherLabels.display_value} teacher-generated labels repaired the missing branch.`,
      tone: "green" as Tone,
    },
  ];

  return (
    <>
      <section className="grid-surface relative overflow-hidden border-b border-white/8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_28%_18%,rgba(34,211,238,0.12),transparent_30rem),radial-gradient(circle_at_88%_60%,rgba(139,92,246,0.1),transparent_28rem)]" />
        <div className="relative mx-auto grid max-w-7xl gap-14 px-4 pb-20 pt-10 sm:px-6 sm:pb-24 sm:pt-14 lg:grid-cols-[1.05fr_.95fr] lg:items-center lg:px-8 lg:pb-28 lg:pt-16">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: reducedMotion ? 0 : 0.09 } } }}
          >
            <motion.div
              variants={heroItem}
              data-testid="hero-proof-badges"
              className="grid grid-cols-[max-content_max-content_max-content] items-center justify-between gap-1 overflow-hidden"
            >
              <Badge className="whitespace-nowrap px-1 py-1 text-[clamp(0.36rem,1.1vw,0.62rem)] tracking-[0.04em] sm:px-1.5 sm:tracking-[0.08em]">
                MODEL SUCCESSION LAB
              </Badge>
              <Badge className="whitespace-nowrap px-1 py-1 text-[clamp(0.36rem,1.1vw,0.62rem)] tracking-[0.04em] sm:px-1.5 sm:tracking-[0.08em]">
                PUBLISHED QWEN → OLMO CASE
              </Badge>
              <Badge className="whitespace-nowrap px-1 py-1 text-[clamp(0.36rem,1.1vw,0.62rem)] tracking-[0.04em] sm:px-1.5 sm:tracking-[0.08em]">
                VALIDATED GPT-5.6 ANALYSIS
              </Badge>
            </motion.div>
            <motion.p variants={heroItem} className="mt-7 font-mono text-sm text-cyan-200/80">
              Move the model. Keep the capability.
            </motion.p>
            <motion.h1
              variants={heroItem}
              className="mt-4 max-w-4xl text-balance text-5xl font-semibold tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl"
            >
              Your successor model does not inherit capability by default.
            </motion.h1>
            <motion.p variants={heroItem} className="mt-7 max-w-2xl text-balance text-lg leading-8 text-slate-300 sm:text-xl">
              InheritBench helps AI teams evaluate a model-family replacement before production. It measures capability loss, compares recovery strategies, stress-tests safety, and produces a replayable migration recommendation.
            </motion.p>
            <motion.p variants={heroItem} className="mt-4 max-w-2xl text-sm leading-6 text-slate-500">
              Built for AI platform engineers, ML engineers, applied AI teams, and model infrastructure teams.
            </motion.p>
            <motion.div variants={heroItem} className="mt-9 flex flex-wrap gap-3">
              <Button asChild size="lg" className="landing-cta">
                <Link href="/run/opsroute-qwen-olmo/">
                  Run verified succession replay <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary" className="landing-cta">
                <Link href="/lab/opsroute">
                  Explore the published case <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </motion.div>
          </motion.div>

          <motion.div
            initial={reducedMotion ? false : { opacity: 0, x: 28 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ ...heroTransition, delay: reducedMotion ? 0 : 0.34 }}
          >
            <Card className="relative overflow-hidden p-6 sm:p-8">
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="eyebrow">Capability break detected</p>
                  <p className="mt-2 text-xs text-slate-500">Confirmatory surface · N={story.confirmatory_denominator}</p>
                </div>
                <span className="rounded-full border border-emerald-300/20 bg-emerald-300/7 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-emerald-200">
                  Reproduced from frozen evidence
                </span>
              </div>
              <div className="mt-8 grid grid-cols-[1fr_3.5rem_1fr] items-center gap-2 sm:gap-4">
                <MetricBlock
                  title={labelSystem(source.system_id)}
                  semantic={source.confirmatory_semantic}
                  strict={source.confirmatory_strict}
                  tone="source"
                  reducedMotion={Boolean(reducedMotion)}
                />
                <div className="relative flex h-12 items-center justify-center" aria-hidden="true">
                  <svg className="h-8 w-full overflow-visible text-slate-500" viewBox="0 0 64 20">
                    <motion.path
                      d="M2 10H56"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      initial={reducedMotion ? false : { pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ duration: reducedMotion ? 0.01 : 0.55, delay: reducedMotion ? 0 : 0.72 }}
                    />
                    <path d="m50 4 8 6-8 6" fill="none" stroke="currentColor" strokeWidth="1.5" />
                  </svg>
                </div>
                <motion.div
                  animate={
                    reducedMotion
                      ? undefined
                      : { boxShadow: ["0 0 0 rgba(251,113,133,0)", "0 0 34px rgba(251,113,133,.14)", "0 0 0 rgba(251,113,133,0)"] }
                  }
                  transition={{ duration: 0.58, delay: 1.15 }}
                  className="rounded-xl"
                >
                  <MetricBlock
                    title={labelSystem(untouched.system_id)}
                    semantic={untouched.confirmatory_semantic}
                    strict={untouched.confirmatory_strict}
                    tone="target"
                    reducedMotion={Boolean(reducedMotion)}
                  />
                </motion.div>
              </div>
              <div className="mt-8 rounded-xl border border-amber-300/15 bg-amber-300/5 p-4 text-sm leading-6 text-amber-100/80">
                Same operational contract. Different model architecture. The untouched successor preserved none of the measured capability.
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-600">Published evidence, not a live model run.</p>
            </Card>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <Reveal reducedMotion={Boolean(reducedMotion)}>
          <SectionHeading
            eyebrow="Model migration workflow"
            title="From model replacement to a defensible migration decision."
            copy="InheritBench turns a model swap into a measurable engineering process instead of a leap of faith."
          />
        </Reveal>
        <div className="relative mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <motion.div
            aria-hidden="true"
            className="absolute left-[8%] right-[8%] top-7 hidden h-px origin-left bg-gradient-to-r from-cyan-300/10 via-cyan-300/45 to-violet-300/10 xl:block"
            initial={reducedMotion ? false : { scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: reducedMotion ? 0.01 : 0.6 }}
          />
          {workflow.map((step, index) => (
            <Reveal key={step.title} reducedMotion={Boolean(reducedMotion)} delay={index * 0.07}>
              <Card className="group relative h-full p-6 transition duration-300 hover:-translate-y-1 hover:border-cyan-300/30 focus-within:border-cyan-300/40 focus-within:shadow-[0_18px_60px_rgba(34,211,238,.08)]">
                <div className="relative flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-300/8 text-cyan-200">
                    <step.icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-sm text-cyan-300">0{index + 1}</span>
                </div>
                <h3 className="mt-7 text-xl font-semibold text-white">{step.title}</h3>
                <p className="mt-3 text-[0.9375rem] leading-7 text-slate-400">{step.copy}</p>
                <p className="mt-6 border-t border-white/8 pt-4 text-[0.8125rem] leading-5 text-slate-400">{step.signal}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="border-y border-white/8 bg-white/[0.018]">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
          <Reveal reducedMotion={Boolean(reducedMotion)}>
            <SectionHeading
              eyebrow="See it working"
              title="One real Qwen → OLMo succession case."
              copy="OpsRoute is the first packaged capability inside InheritBench, covering refund routing and subscription cancellation and retention."
            />
          </Reveal>

          <div className="relative mt-14">
            <motion.div
              aria-hidden="true"
              className="absolute bottom-0 left-[1.15rem] top-0 w-px origin-top bg-gradient-to-b from-cyan-300/50 via-amber-300/35 to-emerald-300/50 md:bottom-auto md:left-[5%] md:right-[5%] md:top-6 md:h-px md:w-auto md:origin-left"
              initial={reducedMotion ? false : { scaleY: 0, scaleX: 0 }}
              whileInView={{ scaleY: 1, scaleX: 1 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: reducedMotion ? 0.01 : 0.65 }}
            />
            <div className="grid gap-5 md:grid-cols-5">
              {caseStages.map((stage, index) => (
                <Reveal key={stage.eyebrow} reducedMotion={Boolean(reducedMotion)} delay={index * 0.08}>
                  <CaseStage
                    {...stage}
                    index={index}
                    reducedMotion={Boolean(reducedMotion)}
                    emphasized={[0, 3, 4].includes(index)}
                    highlightedMetricIndex={index === 3 ? 1 : undefined}
                  />
                </Reveal>
              ))}
            </div>
          </div>

          <Reveal reducedMotion={Boolean(reducedMotion)}>
            <div className="mt-8 grid items-center gap-3 rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.035] p-5 sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:p-6">
              <RepairStep value={slashRatio(blindspotAccepted)} label="teacher outputs covered the isolated branch" tone="violet" />
              <ArrowRight className="mx-auto hidden h-5 w-5 text-slate-500 sm:block" aria-hidden="true" />
              <RepairStep value={anchorLabels.display_value} label="original anchors filled the diagnosed gap" tone="amber" icon={<GitMerge className="h-4 w-4" />} />
              <ArrowRight className="mx-auto hidden h-5 w-5 text-slate-500 sm:block" aria-hidden="true" />
              <RepairStep value={formatPercent(anchored.confirmatory_semantic)} label="confirmatory capability after anchored repair" tone="green" />
            </div>
          </Reveal>

          <Reveal reducedMotion={Boolean(reducedMotion)}>
            <div className="mt-10 rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.045] p-6 sm:p-7">
              <div className="flex items-start gap-4">
                <BadgeCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
                <div>
                  <p className="text-sm font-semibold text-emerald-100">Full label accounting</p>
                  <p className="mt-2 max-w-5xl text-[0.9375rem] leading-7 text-slate-300">
                    Anchored transfer used {anchorLabels.display_value} original labels directly in target training, {teacherLabels.display_value} teacher-generated labels, and depended upstream on a teacher trained with {upstreamLabels.display_value} original labels. The matched distribution was designed from {distributionLabels.display_value} labeled records.
                  </p>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <Reveal reducedMotion={Boolean(reducedMotion)}>
          <SectionHeading
            eyebrow="Constraint-aware decision"
            title="The best recovery path changes with the operating environment."
            copy="InheritBench keeps clean capability and adversarial resilience on separate evaluation surfaces, then recommends under your constraints."
          />
        </Reveal>
        <div className="mt-12 grid gap-5 lg:grid-cols-2">
          <TradeoffPanel
            eyebrow="Clean capability retention"
            denominator={story.confirmatory_denominator}
            rows={[
              { label: "Anchored transfer", value: anchored.confirmatory_semantic, tone: "cyan" },
              { label: "Full retraining", value: full.confirmatory_semantic, tone: "violet" },
            ]}
            conclusion="Anchored transfer preserved more capability on the clean confirmatory surface."
            reducedMotion={Boolean(reducedMotion)}
          />
          <TradeoffPanel
            eyebrow="Adversarial resilience"
            denominator={story.adversarial_denominator}
            rows={[
              { label: "Full retraining", value: full.adversarial_semantic, tone: "violet" },
              { label: "Anchored transfer", value: anchored.adversarial_semantic, tone: "cyan" },
            ]}
            conclusion="Full retraining was more resilient under adversarial pressure."
            reducedMotion={Boolean(reducedMotion)}
          />
        </div>
        <Reveal reducedMotion={Boolean(reducedMotion)}>
          <div className="mt-8 flex flex-col items-start justify-between gap-5 rounded-2xl border border-white/10 bg-slate-950/60 p-6 sm:flex-row sm:items-center">
            <div>
              <p className="text-sm font-semibold text-white">No blended score. No universal winner.</p>
              <p className="mt-2 text-sm text-slate-400">The recommendation changes with label access, teacher availability, safety, complexity, and resilience.</p>
            </div>
            <Button asChild variant="secondary" className="landing-cta shrink-0">
              <Link href="/lab/opsroute/memo">
                See the constraint-based recommendation <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </Reveal>
      </section>

      <section className="border-t border-white/8 bg-slate-950/40">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
          <Reveal reducedMotion={Boolean(reducedMotion)}>
            <div className="grid gap-5 md:grid-cols-2">
              {exploration.map((item, index) => (
                <ExplorationCard key={item.href} {...item} delay={index * 0.05} reducedMotion={Boolean(reducedMotion)} />
              ))}
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}

function Reveal({ children, reducedMotion, delay = 0 }: { children: React.ReactNode; reducedMotion: boolean; delay?: number }) {
  return (
    <motion.div
      initial={reducedMotion ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-70px" }}
      transition={{ duration: reducedMotion ? 0.01 : 0.45, delay: reducedMotion ? 0 : delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function SectionHeading({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="max-w-3xl">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.025em] text-white sm:text-4xl lg:text-5xl">{title}</h2>
      <p className="mt-5 text-lg leading-8 text-slate-400">{copy}</p>
    </div>
  );
}

function MetricBlock({
  title,
  semantic,
  strict,
  tone,
  reducedMotion,
}: {
  title: string;
  semantic: number;
  strict: number;
  tone: "source" | "target";
  reducedMotion: boolean;
}) {
  const color = tone === "source" ? "text-cyan-200" : "text-rose-200";
  return (
    <div className="min-w-0">
      <p className="min-h-8 text-xs font-medium leading-4 text-slate-400">{title}</p>
      <MetricReveal value={formatPercent(semantic)} className={`mt-3 text-3xl sm:text-4xl ${color}`} reducedMotion={reducedMotion} />
      <p className="mt-2 text-[0.68rem] text-slate-500">semantic exactness</p>
      <MetricReveal value={formatPercent(strict)} className={`mt-5 text-lg sm:text-xl ${color}`} reducedMotion={reducedMotion} delay={0.08} />
      <p className="mt-1 text-[0.68rem] text-slate-500">strict validity</p>
    </div>
  );
}

function MetricReveal({ value, className, reducedMotion, delay = 0 }: { value: string; className?: string; reducedMotion: boolean; delay?: number }) {
  return (
    <span className={`block overflow-hidden font-mono font-semibold tabular-nums ${className ?? ""}`}>
      <motion.span
        className="block"
        initial={reducedMotion ? false : { y: "75%", opacity: 0 }}
        whileInView={{ y: 0, opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: reducedMotion ? 0.01 : 0.42, delay: reducedMotion ? 0 : delay, ease: [0.22, 1, 0.36, 1] }}
      >
        {value}
      </motion.span>
    </span>
  );
}

function CaseStage({
  eyebrow,
  metrics,
  labels,
  copy,
  tone,
  index,
  reducedMotion,
  emphasized,
  highlightedMetricIndex,
}: {
  eyebrow: string;
  metrics: string[];
  labels: string[];
  copy: string;
  tone: Tone;
  index: number;
  reducedMotion: boolean;
  emphasized: boolean;
  highlightedMetricIndex?: number;
}) {
  const toneClasses: Record<Tone, string> = {
    cyan: "border-cyan-300/35 bg-cyan-300/10 text-cyan-200",
    rose: "border-rose-300/35 bg-rose-300/10 text-rose-200",
    amber: "border-amber-300/35 bg-amber-300/10 text-amber-200",
    violet: "border-violet-300/35 bg-violet-300/10 text-violet-200",
    green: "border-emerald-300/35 bg-emerald-300/10 text-emerald-200",
  };
  return (
    <article className="relative pl-14 md:pl-0 md:pt-14">
      <div className={`absolute left-0 top-0 grid h-10 w-10 place-items-center rounded-full border font-mono text-xs md:left-1/2 md:-translate-x-1/2 ${toneClasses[tone]}`}>
        {String(index + 1).padStart(2, "0")}
      </div>
      <Card className={`h-full p-5 ${emphasized ? "border-cyan-300/20 bg-slate-950/85 shadow-[0_20px_60px_rgba(34,211,238,.07)]" : "border-white/7 bg-slate-950/45 opacity-80"}`}>
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-slate-500">{eyebrow}</p>
        <div className="mt-5 space-y-4">
          {metrics.map((metric, metricIndex) => (
            <div key={`${metric}-${labels[metricIndex]}`}>
              <MetricReveal
                value={metric}
                className={`${toneText(tone)} ${highlightedMetricIndex === metricIndex ? "text-2xl" : ""}`}
                reducedMotion={reducedMotion}
                delay={metricIndex * 0.06}
              />
              <p className="mt-1 text-xs leading-5 text-slate-500">{labels[metricIndex]}</p>
            </div>
          ))}
        </div>
        <p className="mt-5 border-t border-white/8 pt-4 text-[0.9375rem] leading-7 text-slate-400">{copy}</p>
      </Card>
    </article>
  );
}

function RepairStep({
  value,
  label,
  tone,
  icon,
}: {
  value: string;
  label: string;
  tone: "violet" | "amber" | "green";
  icon?: React.ReactNode;
}) {
  const colors = {
    violet: "text-violet-200",
    amber: "text-amber-200",
    green: "text-emerald-200",
  };
  return (
    <div className="text-center sm:text-left">
      <div className={`flex items-center justify-center gap-2 font-mono text-xl font-semibold sm:justify-start ${colors[tone]}`}>
        {icon}
        {value}
      </div>
      <p className="mt-1 text-sm leading-6 text-slate-400">{label}</p>
    </div>
  );
}

function TradeoffPanel({
  eyebrow,
  denominator,
  rows,
  conclusion,
  reducedMotion,
}: {
  eyebrow: string;
  denominator: number;
  rows: Array<{ label: string; value: number; tone: "cyan" | "violet" }>;
  conclusion: string;
  reducedMotion: boolean;
}) {
  return (
    <Reveal reducedMotion={reducedMotion}>
      <Card className="h-full p-6 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="eyebrow">{eyebrow}</p>
          <span className="rounded-full border border-white/10 px-3 py-1 font-mono text-[0.68rem] text-slate-400">Semantic exactness · N={denominator}</span>
        </div>
        <div className="mt-8 space-y-7">
          {rows.map((row, index) => (
            <div key={row.label}>
              <div className="flex items-end justify-between gap-4">
                <p className="text-sm font-medium text-slate-300">{row.label}</p>
                <MetricReveal value={formatPercent(row.value)} className={row.tone === "cyan" ? "text-cyan-200" : "text-violet-200"} reducedMotion={reducedMotion} delay={index * 0.08} />
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
                <motion.div
                  className={`h-full origin-left rounded-full ${row.tone === "cyan" ? "bg-cyan-300" : "bg-violet-300"}`}
                  style={{ width: `${row.value * 100}%` }}
                  initial={reducedMotion ? false : { scaleX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: reducedMotion ? 0.01 : 0.5, delay: reducedMotion ? 0 : index * 0.08 }}
                />
              </div>
            </div>
          ))}
        </div>
        <p className="mt-8 rounded-xl border border-white/8 bg-white/[0.025] p-4 text-sm leading-6 text-slate-300">{conclusion}</p>
      </Card>
    </Reveal>
  );
}

function ExplorationCard({
  href,
  icon: Icon,
  title,
  copy,
  cta,
  reducedMotion,
}: {
  href: string;
  icon: typeof Boxes;
  title: string;
  copy: string;
  cta: string;
  delay: number;
  reducedMotion: boolean;
}) {
  return (
    <Link href={href} className="group rounded-2xl border border-white/10 bg-slate-950/60 p-6 transition duration-300 hover:-translate-y-1 hover:border-cyan-300/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 sm:p-7">
      <div className="flex items-start justify-between gap-6">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-cyan-300/10 text-cyan-200">
          <Icon className="h-5 w-5" />
        </span>
        <motion.span aria-hidden="true" whileHover={reducedMotion ? undefined : { x: 3 }} className="text-slate-600 group-hover:text-cyan-200">
          <ArrowRight className="h-5 w-5" />
        </motion.span>
      </div>
      <h3 className="mt-6 text-xl font-semibold text-white">{title}</h3>
      <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">{copy}</p>
      <span className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-cyan-200">
        {cta} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
      </span>
    </Link>
  );
}

function getSystem(systems: SystemSummary[], systemId: string): SystemSummary {
  const system = systems.find((item) => item.system_id === systemId);
  if (!system) throw new Error(`missing system summary: ${systemId}`);
  return system;
}

function getFact(facts: Map<string, Fact>, factId: string): Fact {
  const fact = facts.get(factId);
  if (!fact) throw new Error(`missing frozen story fact: ${factId}`);
  return fact;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(3)}%`;
}

function slashRatio(fact: Fact): string {
  return fact.display_value.replace(" of ", " / ");
}

function toneText(tone: Tone): string {
  const colors: Record<Tone, string> = {
    cyan: "text-cyan-200",
    rose: "text-rose-200",
    amber: "text-amber-200",
    violet: "text-violet-200",
    green: "text-emerald-200",
  };
  return colors[tone];
}
