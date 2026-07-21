"use client";

import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  Check,
  CheckCircle2,
  Clipboard,
  FileCheck2,
  GitBranch,
  LockKeyhole,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { LocalRunBundle } from "@/lib/local-run-schema";

export type RunAuditEvidence = {
  canonicalPlan?: Record<string, unknown>;
  candidateRanking?: Record<string, unknown>;
  repairReport?: Record<string, unknown>;
  repairLineage?: Record<string, unknown>;
  evidenceManifest?: Record<string, unknown>;
  replayManifest?: Record<string, unknown>;
};

export function RunInspector({
  bundle,
  verifiedHash,
  audit,
  showBackLink = false,
}: {
  bundle: LocalRunBundle;
  verifiedHash?: string;
  audit?: RunAuditEvidence;
  showBackLink?: boolean;
}) {
  if (bundle.schema_version === "inheritbench.intervention-web-bundle.v0.2") {
    return <InterventionInspector bundle={bundle} verifiedHash={verifiedHash} />;
  }
  if (bundle.schema_version !== "inheritbench.web-bundle.v0.4") {
    return <LegacyInspector bundle={bundle} verifiedHash={verifiedHash} />;
  }
  return (
    <MultistartInspector
      bundle={bundle}
      verifiedHash={verifiedHash}
      audit={audit}
      showBackLink={showBackLink}
    />
  );
}

function MultistartInspector({
  bundle,
  verifiedHash,
  audit,
  showBackLink,
}: {
  bundle: Extract<LocalRunBundle, { schema_version: "inheritbench.web-bundle.v0.4" }>;
  verifiedHash?: string;
  audit?: RunAuditEvidence;
  showBackLink: boolean;
}) {
  const readiness = bundle.readiness.status;
  const completedReadiness =
    bundle.readiness.schema_version === "inheritbench.readiness-report.v0.2"
      ? bundle.readiness
      : null;
  const plan = asRecord(audit?.canonicalPlan);
  const source = asRecord(plan.source);
  const target = asRecord(plan.target);
  const targetModel = asRecord(bundle.adapter).model;
  const selectedIndex = bundle.selection.candidate_index;
  const finalComparison = asRecord(bundle.final_comparison);
  const anchored = asRecord(finalComparison.anchored);
  const direct = asRecord(finalComparison.direct);
  const anchoredMetrics = asRecord(anchored.metrics);
  const directMetrics = asRecord(direct.metrics);
  const adversarialMetrics = asRecord(anchoredMetrics.adversarial);
  const safetyCaseCount = Object.keys(asRecord(adversarialMetrics.blocker_cases)).length;
  const replay = asRecord(bundle.replay_verification);
  const repair = asRecord(audit?.repairLineage);
  const ranking = asRecord(audit?.candidateRanking);
  const rankedCandidates = Array.isArray(ranking.candidates) ? ranking.candidates : [];
  const repairReport = asRecord(audit?.repairReport);
  const repairedCandidates = Array.isArray(repairReport.candidates)
    ? repairReport.candidates
    : [];
  const statusInvalid = ![
    "PASS",
    "CONDITIONAL_PASS",
    "MIGRATION_BLOCKED",
    "NOT_RUN",
  ].includes(readiness);
  const validationRecords =
    numberValue(asRecord(plan.recovery_validation).records) ||
    Math.max(
      0,
      ...bundle.candidates.map((candidate) => candidate.validation_historical_strict_valid ?? 0),
    );
  const decisionHeadline =
    readiness === "CONDITIONAL_PASS"
      ? ["Capability recovered.", "Migration remains conditional."]
      : readiness === "PASS"
        ? ["Capability recovered.", "Successor is ready."]
        : readiness === "NOT_RUN"
          ? ["Recovery stopped.", "Final evaluation did not run."]
          : readiness === "MIGRATION_BLOCKED"
            ? ["Recovery completed.", "Migration remains blocked."]
            : ["Succession evaluated.", "Review the recorded decision."];
  const decisionCopy =
    readiness === "CONDITIONAL_PASS"
      ? "The successor recovered every required clean behavior. One adversarial record still produced two safety findings, so the evidence supports a conditional decision—not an unconditional launch."
      : readiness === "PASS"
        ? "The successor satisfied the recorded capability, safety, and readiness requirements."
        : readiness === "NOT_RUN"
          ? "Recovery did not reach final evaluation. InheritBench preserved the stopped run instead of manufacturing a readiness result."
          : readiness === "MIGRATION_BLOCKED"
            ? "The successor did not satisfy the recorded readiness requirements, so migration remains blocked."
            : "The final decision follows from the recorded evaluation and safety evidence.";

  return (
    <div className="space-y-8 sm:space-y-10" data-testid="run-inspector">
      {showBackLink ? (
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-cyan-200 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
        >
          ← Back to InheritBench
        </Link>
      ) : null}

      <Card className={`grid-surface relative overflow-hidden rounded-3xl border-0 px-6 py-10 shadow-[0_30px_100px_rgba(2,8,23,.32)] sm:px-9 sm:py-12 lg:px-12 ${readinessTone(readiness)}`}>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_8%,rgba(34,211,238,.08),transparent_28rem)]" />
        <div className="relative flex flex-wrap items-center gap-3">
          <Badge>Completed local CLI succession</Badge>
          <StatusBadge status={readiness} />
        </div>
        <div className="relative mt-8 grid gap-8 lg:grid-cols-[1.08fr_.92fr] lg:items-center">
          <div>
            <p className="eyebrow">Qwen → OLMo result</p>
            <h1 className="mt-4 text-balance text-4xl font-semibold tracking-[-0.04em] text-white sm:text-5xl lg:text-6xl">
              {decisionHeadline[0]}{" "}
              <span className="block text-amber-200">{decisionHeadline[1]}</span>
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
              {decisionCopy}
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
              This browser projection comes from a completed local InheritBench CLI run. The engine
              verified adapted Qwen, measured what untouched OLMo lost, executed direct and anchored
              recovery, selected Candidate {selectedIndex} using validation only, opened sealed
              final records, exported and reloaded the adapter, and replayed the decision.
            </p>
          </div>
          <div className="rounded-2xl bg-slate-950/45 p-6 shadow-inner shadow-black/20 sm:p-7">
            <p className="text-sm font-medium text-slate-300">Final decision</p>
            <h2 className="mt-3 text-2xl font-semibold text-white">
              {readiness.replaceAll("_", " ")}
            </h2>
            <dl className="mt-6 grid gap-5 text-sm sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <Metric label="Operational correctness" value={surfaceRatio(anchoredMetrics, "confirmatory", "operational")} />
              <Metric label="Exact-contract fidelity" value={surfaceRatio(anchoredMetrics, "confirmatory", "exact")} />
              <Metric
                label="Safety findings"
                value={
                  completedReadiness
                    ? `${completedReadiness.adversarial.blocker_safety_findings} on ${safetyCaseCount} adversarial record${safetyCaseCount === 1 ? "" : "s"}`
                    : "Not available"
                }
              />
            </dl>
          </div>
        </div>
        {statusInvalid ? (
          <p role="alert" className="mt-5 flex items-center gap-2 text-sm text-rose-200">
            <AlertTriangle className="h-4 w-4" /> Invalid readiness state
          </p>
        ) : null}
      </Card>

      <section
        aria-labelledby="run-summary-heading"
        className="rounded-3xl bg-slate-900/55 p-6 sm:p-9 lg:p-12"
      >
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">At a glance</p>
            <h2 id="run-summary-heading" className="mt-2 text-2xl font-semibold text-white">
              What happened in this model succession
            </h2>
          </div>
          <span className="text-sm text-slate-400">
            {verifiedHash ? "Uploaded evidence verified" : "Committed evidence verified"}
          </span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <SummaryCard
            question="What changed?"
            answer={`${shortModel(stringValue(source.model_id, "Source model"))} → ${shortModel(
              stringValue(target.model_id ?? asRecord(targetModel).model_id, "Target model"),
            )}`}
          />
          <SummaryCard
            question="What failed?"
            answer={
              completedReadiness
                ? `${completedReadiness.target_baseline.semantic_correct}/${completedReadiness.target_baseline.expected} required behaviors survived.`
                : "Recovery did not reach final evaluation."
            }
          />
          <SummaryCard
            question="How was it recovered?"
            answer={`${bundle.label_accounting.anchor_labels} targeted examples; Candidate ${selectedIndex ?? "not selected"}.`}
          />
          <SummaryCard
            question="Why conditional?"
            answer={
              completedReadiness
                ? `${completedReadiness.adversarial.blocker_safety_findings} safety findings on ${safetyCaseCount} adversarial record${safetyCaseCount === 1 ? "" : "s"}.`
                : "No conditional decision was issued."
            }
          />
          <SummaryCard
            question="Can I trust selection?"
            answer={
              bundle.decision.final_evaluation_exactly_once
                ? "Validation-only ranking; final evaluation run once."
                : "Selection and final evaluation evidence remain below."
            }
          />
        </div>
      </section>

      <Card className="grid-surface flex flex-col gap-5 overflow-hidden rounded-3xl border-0 bg-gradient-to-br from-cyan-300/[0.09] via-slate-900/80 to-slate-900/70 p-6 shadow-[0_24px_80px_rgba(2,8,23,.28)] sm:flex-row sm:items-center sm:justify-between sm:p-9">
        <div>
          <p className="font-semibold text-white">CLI-produced evidence and browser assurance</p>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            This page shows how the local succession engine produced and selected the successor.
            The Assurance Lab separately lets you test its evaluation and readiness evidence.
          </p>
          <Link
            href="/#developer-workflow"
            className="mt-3 inline-flex items-center gap-2 rounded-sm text-sm font-medium text-cyan-200 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
          >
            View CLI workflow <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button asChild>
            <Link href="/sandbox/">
              Test this successor in the Assurance Lab <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href="/lab/opsroute/evidence/">Open full evidence</Link>
          </Button>
        </div>
      </Card>

      <Section
        eyebrow="Succession journey"
        title="Diagnose → Recover → Assure"
        copy="The evidence path stays ordered from source verification through model-free replay."
      >
        <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {journey(bundle).map((stage, index) => (
            <li key={stage.title} className="rounded-xl border border-white/9 bg-black/20 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-xs text-cyan-300">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <StatusBadge status={stage.status} compact />
              </div>
              <h3 className="mt-4 font-semibold text-white">{stage.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{stage.copy}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section
        eyebrow="Model lineage"
        title="Three identities. One controlled succession."
        copy="The adapted source, untouched target, and recovered successor remain explicitly separate."
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr_auto_1fr] lg:items-stretch">
          <LineageCard
            label="Source model"
            model={stringValue(source.model_id, "Source model recorded in canonical plan")}
            details={[
              "Adapted source",
              "Capability verified",
              stringValue(source.revision, "Revision unavailable"),
            ]}
          />
          <LineageArrow label="loss measured" />
          <LineageCard
            label="Target baseline"
            model={stringValue(
              target.model_id ?? asRecord(targetModel).model_id,
              "Target model recorded in adapter evidence",
            )}
            details={[
              "Untouched target",
              "Capability loss measured",
              stringValue(target.revision, "Revision unavailable"),
            ]}
          />
          <LineageArrow label="adapter recovered" />
          <LineageCard
            label="Recovered successor"
            model={stringValue(
              target.model_id ?? asRecord(targetModel).model_id,
              "Target base + selected adapter",
            )}
            details={[
              selectedIndex === null ? "No candidate selected" : `Candidate ${selectedIndex}`,
              "Validation-selected checkpoint",
              readiness.replaceAll("_", " "),
            ]}
            selected
          />
        </div>
      </Section>

      {completedReadiness ? (
        <section className="grid gap-5 lg:grid-cols-2">
          <Card className="rounded-3xl border-0 bg-slate-900/55 p-6 shadow-none sm:p-9">
            <p className="eyebrow">Diagnosis</p>
            <h2 className="mt-3 text-2xl font-semibold text-white">Capability loss detected</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <MetricCard
                label="Source capability"
                value={`${completedReadiness.source_gate.semantic_correct}/${completedReadiness.source_gate.expected}`}
                note="Source-gate semantic correctness"
              />
              <MetricCard
                label="Untouched target"
                value={`${completedReadiness.target_baseline.semantic_correct}/${completedReadiness.target_baseline.expected}`}
                note={`${completedReadiness.target_baseline.blocker_safety_findings} safety blockers`}
                warning
              />
            </div>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              The target produced valid-looking responses while failing the learned operational
              contract. Recovery was required before deployment.
            </p>
          </Card>
          <Card className="rounded-3xl border-0 bg-gradient-to-br from-amber-300/[0.07] to-slate-900/60 p-6 shadow-none sm:p-9">
            <p className="eyebrow">Coverage intervention</p>
            <h2 className="mt-3 text-2xl font-semibold text-white">Targeted supervision required</h2>
            <p className="mt-4 text-sm leading-7 text-slate-300">
              The engine detected that required capability branches lacked enough trusted
              supervision, requested targeted anchors, and then resumed recovery.
            </p>
            <dl className="mt-6 grid grid-cols-2 gap-4">
              <Metric label="Teacher candidates" value={String(bundle.label_accounting.candidate_inputs)} />
              <Metric label="Accepted outputs" value={String(bundle.label_accounting.accepted_teacher_outputs)} />
              <Metric label="Teacher labels" value={String(bundle.label_accounting.teacher_labels)} />
              <Metric label="Human anchors" value={String(bundle.label_accounting.anchor_labels)} />
            </dl>
          </Card>
        </section>
      ) : null}

      <Section
        eyebrow="Recovery flow"
        title="A deficit-driven intervention, then bounded recovery."
        copy="Every count below comes from the run bundle’s label and compute accounting."
      >
        <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-8">
          {[
            ["Teacher examples", bundle.label_accounting.candidate_inputs],
            ["Accepted supervision", bundle.label_accounting.accepted_teacher_outputs],
            ["Selected examples", bundle.label_accounting.teacher_labels],
            ["Anchor deficit", "Detected"],
            ["Human anchors", bundle.label_accounting.anchor_labels],
            ["Candidates", bundle.candidates.length],
            ["Validation ranking", "Only"],
            ["Candidate freeze", selectedIndex === null ? "None" : `#${selectedIndex}`],
          ].map(([label, value], index) => (
            <div key={label} className="relative rounded-2xl bg-slate-950/40 p-4">
              <p className="text-sm font-medium text-slate-400">{label}</p>
              <p className="mt-3 font-mono text-lg font-semibold text-white">{String(value)}</p>
              {index < 7 ? (
                <ArrowDown className="mx-auto mt-3 h-4 w-4 text-cyan-300 md:hidden" aria-hidden />
              ) : null}
            </div>
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Candidate selection"
        title={`${bundle.candidates.length} frozen seeds, ranked without final-test evidence.`}
        copy="Selected using validation evidence only. Final evaluation was unavailable during ranking."
      >
        <div className="grid gap-4 lg:hidden" data-testid="candidate-comparison-mobile">
          {bundle.candidates.map((candidate) => {
            const ranked = findCandidate(rankedCandidates, candidate.candidate_index);
            const repaired = findCandidate(repairedCandidates, candidate.candidate_index);
            const selected = selectedIndex === candidate.candidate_index;
            return (
              <article
                key={candidate.candidate_index}
                data-selected={selected || undefined}
                className={`min-w-0 rounded-2xl p-5 ${
                  selected
                    ? "bg-cyan-300/[0.1] ring-1 ring-inset ring-cyan-300/25"
                    : "bg-slate-950/40"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="font-semibold text-white">
                    Candidate {candidate.candidate_index}
                    {selected ? <span className="ml-2 text-xs text-cyan-200">Selected</span> : null}
                  </h3>
                  <StatusBadge status={candidate.training_status} compact />
                </div>
                <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                  <CandidateMetric label="Seed" value={String(candidate.initialization_seed)} mono />
                  <CandidateMetric label="Restart" value={stringValue(repaired.restart_or_resume, "Not recorded")} />
                  <CandidateMetric
                    label="Validation ops"
                    value={ratio(candidate.validation_operational_semantic_correct, validationRecords)}
                  />
                  <CandidateMetric
                    label="Exact contract"
                    value={ratio(optionalNumber(ranked.validation_exact_full_contract), validationRecords)}
                  />
                  <CandidateMetric
                    label="Weakest group"
                    value={formatRate(candidate.validation_minimum_group_operational_semantic_rate)}
                  />
                  <CandidateMetric
                    label="Strict valid"
                    value={ratio(candidate.validation_historical_strict_valid, validationRecords)}
                  />
                  <CandidateMetric label="Safety" value={candidate.safety_eligible ? "Eligible" : "Ineligible"} />
                  <CandidateMetric label="Loss" value={formatNumber(candidate.validation_loss)} mono />
                  <div className="col-span-2 min-w-0">
                    <dt className="text-xs font-medium text-slate-400">Checkpoint</dt>
                    <dd className="mt-1 break-all font-mono text-xs leading-5 text-slate-300">
                      {candidate.selected_checkpoint_id ?? "None"}
                    </dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>
        <div
          className="hidden overflow-x-auto rounded-2xl bg-slate-950/35 lg:block"
          tabIndex={0}
          role="region"
          aria-label="Candidate comparison table"
          data-testid="candidate-comparison-table"
        >
          <table className="w-full min-w-[1050px] text-left text-sm">
            <thead className="bg-white/[0.04] text-xs font-medium text-slate-400">
              <tr>
                {["Candidate", "Seed", "Restart", "Checkpoint", "Validation ops", "Exact contract", "Weakest group", "Strict valid", "Safety", "Loss", "Status"].map(
                  (label) => <th key={label} className="px-4 py-3">{label}</th>,
                )}
              </tr>
            </thead>
            <tbody>
              {bundle.candidates.map((candidate) => {
                const ranked = findCandidate(rankedCandidates, candidate.candidate_index);
                const repaired = findCandidate(repairedCandidates, candidate.candidate_index);
                const selected = selectedIndex === candidate.candidate_index;
                return (
                  <tr
                    key={candidate.candidate_index}
                    data-selected={selected || undefined}
                    className={selected ? "bg-cyan-300/[0.08]" : "border-t border-white/7"}
                  >
                    <td className="px-4 py-4 font-semibold text-white">
                      Candidate {candidate.candidate_index}
                      {selected ? <span className="ml-2 text-xs text-cyan-200">Selected</span> : null}
                    </td>
                    <td className="px-4 py-4 font-mono text-xs">{candidate.initialization_seed}</td>
                    <td className="px-4 py-4">{stringValue(repaired.restart_or_resume, "Not recorded")}</td>
                    <td className="max-w-48 break-all px-4 py-4 font-mono text-xs">
                      {candidate.selected_checkpoint_id ?? "None"}
                    </td>
                    <td className="px-4 py-4">{ratio(candidate.validation_operational_semantic_correct, validationRecords)}</td>
                    <td className="px-4 py-4">{ratio(optionalNumber(ranked.validation_exact_full_contract), validationRecords)}</td>
                    <td className="px-4 py-4">{formatRate(candidate.validation_minimum_group_operational_semantic_rate)}</td>
                    <td className="px-4 py-4">{ratio(candidate.validation_historical_strict_valid, validationRecords)}</td>
                    <td className="px-4 py-4">{candidate.safety_eligible ? "Eligible" : "Ineligible"}</td>
                    <td className="px-4 py-4 font-mono text-xs">{formatNumber(candidate.validation_loss)}</td>
                    <td className="px-4 py-4"><StatusBadge status={candidate.training_status} compact /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {completedReadiness ? (
        <Card className={`rounded-3xl border-0 p-6 shadow-[0_24px_80px_rgba(2,8,23,.25)] sm:p-9 lg:p-12 ${readinessTone(readiness)}`}>
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="eyebrow">Final readiness</p>
              <h2 className="mt-3 text-3xl font-semibold text-white">{readiness}</h2>
              <p className="mt-3 max-w-3xl leading-7 text-slate-300">
                Clean operational behavior reached {operational(anchoredMetrics, "confirmatory")}/
                {numberValue(asRecord(anchoredMetrics.confirmatory).records)}; exact contracts
                reached {exact(anchoredMetrics, "confirmatory")}/
                {numberValue(asRecord(anchoredMetrics.confirmatory).records)}; clean safety
                blockers were {completedReadiness.confirmatory.blocker_safety_findings}.
                Adversarial evaluation produced {completedReadiness.adversarial.blocker_safety_findings} safety
                findings, so the result is conditional rather than unconditional.
              </p>
            </div>
            <StatusBadge status={readiness} />
          </div>
          <dl className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Contract" value={completedReadiness.rule_version} mono />
            <Metric label="Clean operational correctness" value={surfaceRatio(anchoredMetrics, "confirmatory", "operational")} />
            <Metric label="Clean exact-contract fidelity" value={surfaceRatio(anchoredMetrics, "confirmatory", "exact")} />
            <Metric label="Clean strict validity" value={surfaceRatio(anchoredMetrics, "confirmatory", "strict")} />
            <Metric label="Clean safety blockers" value={String(completedReadiness.confirmatory.blocker_safety_findings)} />
            <Metric label="Adversarial exact-contract fidelity" value={surfaceRatio(anchoredMetrics, "adversarial", "exact")} />
            <Metric label="Adversarial strict validity" value={surfaceRatio(anchoredMetrics, "adversarial", "strict")} />
            <Metric label="Adversarial blocker findings" value={String(completedReadiness.adversarial.blocker_safety_findings)} />
          </dl>
          <details className="mt-7 rounded-2xl bg-slate-950/40 p-5">
            <summary className="cursor-pointer font-medium text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
              Why this decision?
            </summary>
            <div className="mt-4 grid gap-4 text-sm leading-6 text-slate-300 sm:grid-cols-2">
              <p>Reason codes: {completedReadiness.reason_codes.map(humanize).join(", ")}</p>
              <p>Weakest clean group: {formatRate(completedReadiness.confirmatory.minimum_group_semantic_rate)}</p>
              <p>Fresh-base reload: {bundle.selection.fresh_base_reload_verified ? "Verified" : "Not verified"}</p>
              <p>Replay integrity: {bundle.decision.replay_verified ? "Verified" : "Not verified"}</p>
            </div>
          </details>
        </Card>
      ) : null}

      <Section
        eyebrow="Results comparison"
        title="Untouched target, direct recovery, anchored recovery."
        copy="Final results are shown only after selection and remain separate from candidate ranking."
      >
        <div className="grid gap-4 lg:grid-cols-3">
          {completedReadiness ? (
            <ComparisonCard
              title="Untouched target"
              readiness="DIAGNOSTIC BASELINE"
              metrics={[
                ["Source-gate semantic correctness", `${completedReadiness.target_baseline.semantic_correct}/${completedReadiness.target_baseline.expected}`],
                ["Source-gate exact-contract fidelity", `${completedReadiness.target_baseline.structural_exact}/${completedReadiness.target_baseline.expected}`],
                ["Strict validity", `${completedReadiness.target_baseline.strict_valid}/${completedReadiness.target_baseline.expected}`],
                ["Blocker safety findings", String(completedReadiness.target_baseline.blocker_safety_findings)],
              ]}
            />
          ) : null}
          <ComparisonCard
            title="Direct recovery"
            readiness={stringValue(direct.readiness, "Not available")}
            metrics={comparisonMetrics(directMetrics)}
          />
          <ComparisonCard
            title="Anchored recovery"
            readiness={stringValue(anchored.readiness, readiness)}
            metrics={comparisonMetrics(anchoredMetrics)}
            selected
          />
        </div>
      </Section>

      <Card className="rounded-3xl border-0 bg-gradient-to-br from-emerald-300/[0.06] to-slate-900/55 p-6 shadow-none sm:p-9 lg:p-12">
        <div className="flex items-start gap-4">
          <FileCheck2 className="mt-1 h-7 w-7 shrink-0 text-emerald-300" />
          <div className="min-w-0 flex-1">
            <p className="eyebrow">Replay proof</p>
            <h2 className="mt-3 text-3xl font-semibold text-white">Replay verified</h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              {numberValue(replay.anchored_record_count) + numberValue(replay.direct_record_count)} predictions replayed.
              The same readiness decision, evidence references, and adapter identity were reproduced
              without loading a model or retraining.
            </p>
            <dl className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="Anchored records" value={String(replay.anchored_record_count ?? "Not recorded")} />
              <Metric label="Direct records" value={String(replay.direct_record_count ?? "Not recorded")} />
              <Metric label="Replay status" value={stringValue(replay.status, "Not recorded")} />
              <Metric label="Readiness reproduced" value={readiness} />
            </dl>
            <CopyField
              label="Final adapter SHA-256"
              value={stringValue(bundle.selection.exported_adapter_sha256, "Not recorded")}
            />
            <p className="mt-4 text-sm text-slate-400">
              Replay verifies the decision path from frozen evidence, making the succession result independently inspectable.
            </p>
          </div>
        </div>
      </Card>

      <Section
        eyebrow="Evidence"
        title="Audit detail, available on demand."
        copy="Technical lineage stays accessible without dominating the product overview."
      >
        <div className="grid gap-3 md:grid-cols-2">
          <EvidenceDisclosure label="Protocol and plan" value={audit?.canonicalPlan ?? bundle.protocol} />
          <EvidenceDisclosure label="Candidate ranking" value={audit?.candidateRanking ?? bundle.selection} />
          <EvidenceDisclosure label="Numerical-guard repair lineage" value={audit?.repairLineage ?? { status: "Not included in this bundle" }} />
          <EvidenceDisclosure label="Repair execution" value={audit?.repairReport ?? { status: "Not included in this bundle" }} />
          <EvidenceDisclosure label="Artifact manifest" value={audit?.evidenceManifest ?? { status: "Not included in this bundle" }} />
          <EvidenceDisclosure label="Replay receipt" value={bundle.replay_verification} />
          <EvidenceDisclosure label="Historical comparison" value={bundle.historical_comparison} />
          <EvidenceDisclosure label="Raw residual metrics" value={bundle.residuals} />
        </div>
        {repair.created_at ? (
          <p className="mt-5 text-xs text-slate-400">
            Repair lineage recorded {String(repair.created_at)} · scientific protocol changed:{" "}
            {String(repair.scientific_protocol_changed)}
          </p>
        ) : null}
      </Section>
    </div>
  );
}

function LegacyInspector({
  bundle,
  verifiedHash,
}: {
  bundle: Extract<
    LocalRunBundle,
    { schema_version: "inheritbench.web-bundle.v0.2" | "inheritbench.web-bundle.v0.3" }
  >;
  verifiedHash?: string;
}) {
  return (
    <div className="space-y-6">
      <Card className={`p-6 sm:p-8 ${readinessTone(bundle.readiness.status)}`}>
        <StatusBadge status={bundle.readiness.status} />
        <h2 className="mt-5 text-3xl font-semibold text-white">Succession bundle verified</h2>
        <p className="mt-3 text-slate-300">
          {bundle.capability.id}@{bundle.capability.version} · {humanize(bundle.strategy)}
        </p>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Clean operational" value={`${bundle.summaries.confirmatory.semantic_correct}/${bundle.summaries.confirmatory.expected}`} />
          <Metric label="Adversarial operational" value={`${bundle.summaries.adversarial.semantic_correct}/${bundle.summaries.adversarial.expected}`} />
          <Metric label="Residual records" value={String(bundle.residuals.length)} />
          <Metric label="Bundle SHA-256" value={verifiedHash ?? bundle.content_sha256} mono />
        </dl>
      </Card>
      <Section eyebrow="Execution" title="Recorded stages" copy="Legacy bundle stages remain readable.">
        <ol className="grid gap-2 sm:grid-cols-2">
          {bundle.stages.map((stage, index) => (
            <li key={`${stage}-${index}`} className="rounded-lg border border-white/8 p-3 font-mono text-xs">
              {String(index + 1).padStart(2, "0")} · {stage}
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

function InterventionInspector({
  bundle,
  verifiedHash,
}: {
  bundle: Extract<LocalRunBundle, { schema_version: "inheritbench.intervention-web-bundle.v0.2" }>;
  verifiedHash?: string;
}) {
  return (
    <Card className="border-amber-300/25 bg-amber-300/5 p-6 sm:p-8">
      <StatusBadge status="warning" />
      <h2 className="mt-5 text-3xl font-semibold text-white">Targeted supervision required</h2>
      <p className="mt-3 max-w-3xl leading-7 text-slate-300">
        The run paused at a declared coverage deficit. Add validated anchors, then resume the same
        immutable run without repeating completed generation.
      </p>
      <dl className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="Capability" value={`${bundle.capability.id}@${bundle.capability.version}`} />
        <Metric label="Run ID" value={bundle.run_id} mono />
        <Metric label="Bundle SHA-256" value={verifiedHash ?? bundle.content_sha256} mono />
      </dl>
      <EvidenceDisclosure label="Declared intervention" value={bundle.intervention} />
    </Card>
  );
}

function Section({
  eyebrow,
  title,
  copy,
  children,
}: {
  eyebrow: string;
  title: string;
  copy: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="rounded-3xl border-0 bg-slate-900/55 p-6 shadow-none sm:p-9 lg:p-12">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-2xl font-semibold text-white sm:text-3xl">{title}</h2>
      <p className="mt-3 max-w-3xl leading-7 text-slate-400">{copy}</p>
      <div className="mt-7">{children}</div>
    </Card>
  );
}

function StatusBadge({ status, compact = false }: { status: string; compact?: boolean }) {
  const normalized = status.toUpperCase();
  const Icon = ["PASS", "VERIFIED", "COMPLETED", "CONDITIONAL_PASS"].includes(normalized)
    ? CheckCircle2
    : ["FAILED", "MIGRATION_BLOCKED", "NOT_RUN"].includes(normalized)
      ? AlertTriangle
      : LockKeyhole;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-slate-950/45 font-semibold text-slate-200 ring-1 ring-inset ring-white/10 ${compact ? "px-2 py-1 text-[0.68rem]" : "px-3 py-1.5 text-xs"}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {humanize(status)}
    </span>
  );
}

function LineageCard({
  label,
  model,
  details,
  selected = false,
}: {
  label: string;
  model: string;
  details: string[];
  selected?: boolean;
}) {
  return (
    <article className={`rounded-2xl p-5 ${selected ? "bg-cyan-300/[0.09] ring-1 ring-inset ring-cyan-300/20" : "bg-slate-950/40"}`}>
      <p className="text-sm font-medium text-slate-400">{label}</p>
      <h3 className="mt-3 break-words font-semibold text-white">{model}</h3>
      <ul className="mt-4 space-y-2 text-sm text-slate-400">
        {details.map((detail) => <li key={detail}>• {detail}</li>)}
      </ul>
    </article>
  );
}

function LineageArrow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-2 text-xs text-slate-400 lg:flex-col">
      <GitBranch className="h-5 w-5 text-cyan-300" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

function MetricCard({ label, value, note, warning = false }: { label: string; value: string; note: string; warning?: boolean }) {
  return (
    <div className={`rounded-2xl p-5 ${warning ? "bg-rose-300/[0.07]" : "bg-slate-950/40"}`}>
      <p className="text-sm font-medium text-slate-400">{label}</p>
      <p className="mt-3 font-mono text-3xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-sm text-slate-400">{note}</p>
    </div>
  );
}

function SummaryCard({ question, answer }: { question: string; answer: string }) {
  return (
    <article className="rounded-2xl bg-slate-950/40 p-5">
      <h3 className="text-sm font-semibold text-white">{question}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-400">{answer}</p>
    </article>
  );
}

function ComparisonCard({
  title,
  readiness,
  metrics,
  selected = false,
}: {
  title: string;
  readiness: string;
  metrics: Array<[string, string]>;
  selected?: boolean;
}) {
  return (
    <article className={`rounded-2xl p-5 ${selected ? "bg-cyan-300/[0.09] ring-1 ring-inset ring-cyan-300/20" : "bg-slate-950/40"}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold text-white">{title}</h3>
        <StatusBadge status={readiness} compact />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-4">
        {metrics.map(([label, value]) => <Metric key={label} label={label} value={value} />)}
      </dl>
    </article>
  );
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return (
    <div className="mt-6">
      <p className="text-sm font-medium text-slate-400">{label}</p>
      <div className="mt-2 flex items-center gap-2 rounded-2xl bg-slate-950/45 p-3">
        <code className="min-w-0 flex-1 break-all text-xs text-cyan-100">{value}</code>
        <Button type="button" size="sm" variant="secondary" onClick={() => void copy()} aria-label={`Copy ${label}`}>
          {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <span className="sr-only" role="status" aria-live="polite">{copied ? `${label} copied` : ""}</span>
    </div>
  );
}

function EvidenceDisclosure({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="rounded-2xl bg-slate-950/40 p-5">
      <summary className="cursor-pointer font-medium text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
        {label}
      </summary>
      <pre className="code-scroll mt-4 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-slate-400">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-sm font-medium text-slate-400">{label}</dt>
      <dd className={`mt-2 text-slate-100 ${mono ? "break-all font-mono text-xs" : "text-sm"}`}>{value}</dd>
    </div>
  );
}

function CandidateMetric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-slate-400">{label}</dt>
      <dd className={`mt-1 break-words text-slate-200 ${mono ? "font-mono text-xs" : "text-sm"}`}>
        {value}
      </dd>
    </div>
  );
}

function journey(bundle: Extract<LocalRunBundle, { schema_version: "inheritbench.web-bundle.v0.4" }>) {
  const selected = bundle.selection.candidate_index;
  return [
    { title: "Source verified", status: "verified", copy: "Source gate evidence recorded." },
    { title: "Target assessed", status: "verified", copy: "Untouched target baseline measured." },
    { title: "Capability loss detected", status: "warning", copy: "Replacement failed required behavior." },
    { title: "Recovery planned", status: "verified", copy: humanize(bundle.strategy) },
    { title: "Anchors requested", status: "verified", copy: `${bundle.label_accounting.anchor_labels} targeted labels.` },
    { title: `${bundle.candidates.length} candidates trained`, status: bundle.candidates.every((candidate) => candidate.training_status === "COMPLETED") ? "completed" : "failed", copy: "Bounded seeds under one frozen protocol." },
    { title: "Candidate selected", status: selected === null ? "failed" : "verified", copy: selected === null ? "No eligible candidate." : `Candidate ${selected}, validation only.` },
    { title: "Final evaluation sealed", status: bundle.decision.final_evaluation_exactly_once ? "verified" : "warning", copy: "Confirmatory and adversarial surfaces locked." },
    { title: "Readiness issued", status: bundle.readiness.status, copy: humanize(bundle.readiness.status) },
    { title: "Replay verified", status: bundle.decision.replay_verified ? "verified" : "failed", copy: "Frozen evidence reproduced the decision." },
  ];
}

function readinessTone(status: string) {
  if (status === "PASS") {
    return "bg-gradient-to-br from-emerald-300/[0.08] via-slate-900/80 to-slate-900/70";
  }
  if (status === "CONDITIONAL_PASS") {
    return "bg-gradient-to-br from-amber-300/[0.08] via-slate-900/80 to-slate-900/70";
  }
  return "bg-gradient-to-br from-rose-300/[0.08] via-slate-900/80 to-slate-900/70";
}

function comparisonMetrics(metrics: Record<string, unknown>): Array<[string, string]> {
  return [
    ["Clean operational correctness", surfaceRatio(metrics, "confirmatory", "operational")],
    ["Clean exact-contract fidelity", surfaceRatio(metrics, "confirmatory", "exact")],
    ["Clean strict validity", surfaceRatio(metrics, "confirmatory", "strict")],
    ["Adversarial exact-contract fidelity", surfaceRatio(metrics, "adversarial", "exact")],
    ["Adversarial strict validity", surfaceRatio(metrics, "adversarial", "strict")],
    ["Adversarial blocker findings", String(numberValue(asRecord(metrics.adversarial).blocker_safety_findings))],
  ];
}

function operational(metrics: Record<string, unknown>, surface: string) {
  return numberValue(asRecord(metrics[surface]).operational_semantic_correct);
}
function exact(metrics: Record<string, unknown>, surface: string) {
  return numberValue(asRecord(metrics[surface]).exact_full_contract);
}
function surfaceRatio(
  metrics: Record<string, unknown>,
  surface: string,
  metric: "operational" | "exact" | "strict",
) {
  const values = asRecord(metrics[surface]);
  const numerator =
    metric === "operational"
      ? numberValue(values.operational_semantic_correct)
      : metric === "exact"
        ? numberValue(values.exact_full_contract)
        : numberValue(values.historical_strict_valid);
  return ratio(numerator, numberValue(values.records));
}
function findCandidate(values: unknown[], index: number) {
  return asRecord(values.find((value) => asRecord(value).candidate_index === index));
}
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}
function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}
function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value ? value : fallback;
}
function shortModel(value: string): string {
  return value.split("/").at(-1)?.replace("-Instruct", "") ?? value;
}
function ratio(value: number | null | undefined, denominator: number): string {
  return value === null || value === undefined || denominator <= 0
    ? "Not recorded"
    : `${value}/${denominator}`;
}
function formatRate(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not recorded" : `${(value * 100).toFixed(1)}%`;
}
function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not recorded" : value.toPrecision(5);
}
function humanize(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}
