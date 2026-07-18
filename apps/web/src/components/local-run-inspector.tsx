"use client";

import { AlertTriangle, BadgeCheck, FileJson2, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  type LocalRunBundle,
  validateLocalRunBundle,
} from "@/lib/local-run-schema";

export function LocalRunInspector() {
  const [bundle, setBundle] = useState<LocalRunBundle | null>(null);
  const [verifiedHash, setVerifiedHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setBundle(null);
    try {
      const result = await validateLocalRunBundle(file);
      setBundle(result.bundle);
      setVerifiedHash(result.verifiedSha256);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Local run bundle validation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <Card className="p-6 sm:p-8">
        <p className="eyebrow">Local run inspection</p>
        <h1 className="mt-4 text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          Inspect a generic succession result.
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">
          Load a locally exported <code className="font-mono text-cyan-200">web_bundle.json</code>.
          Verification runs entirely in your browser. Nothing is uploaded, and no API is called.
        </p>
        <div className="mt-7 rounded-xl border border-white/10 bg-white/[0.025] p-5">
          <label htmlFor="local-run-file" className="block font-medium text-white">
            Choose a finalized run bundle
          </label>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            Maximum 5 MiB. The inspector validates the generic schema and verifies the embedded
            SHA-256 content hash with Web Crypto.
          </p>
          <input
            id="local-run-file"
            type="file"
            accept=".json,application/json"
            className="mt-5 block w-full rounded-xl border border-white/10 bg-slate-950/80 p-3 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-cyan-300/10 file:px-4 file:py-2 file:font-medium file:text-cyan-100"
            disabled={busy}
            onChange={(event) => void loadFile(event.target.files?.[0])}
          />
        </div>
      </Card>

      {error ? (
        <Card role="alert" className="border-rose-300/25 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-300" />
            <div>
              <h2 className="font-semibold text-white">Bundle rejected</h2>
              <p className="mt-2 text-sm leading-6 text-rose-100/80">{error}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {bundle ? <LocalRunResult bundle={bundle} verifiedHash={verifiedHash ?? ""} /> : null}
    </div>
  );
}

function LocalRunResult({
  bundle,
  verifiedHash,
}: {
  bundle: LocalRunBundle;
  verifiedHash: string;
}) {
  if (bundle.schema_version === "inheritbench.intervention-web-bundle.v0.2") {
    return <AnchorIntervention bundle={bundle} verifiedHash={verifiedHash} />;
  }
  if (bundle.schema_version === "inheritbench.web-bundle.v0.4") {
    return <MultistartResult bundle={bundle} verifiedHash={verifiedHash} />;
  }
  const referenceBundle =
    bundle.schema_version === "inheritbench.web-bundle.v0.3" ? bundle : null;
  const confirmatory = bundle.summaries.confirmatory;
  const adversarial = bundle.summaries.adversarial;
  const tone =
    bundle.readiness.status === "PASS"
      ? "border-emerald-300/25 bg-emerald-300/5"
      : bundle.readiness.status === "CONDITIONAL_PASS"
        ? "border-amber-300/25 bg-amber-300/5"
        : "border-rose-300/25 bg-rose-300/5";
  return (
    <>
      <Card className={`p-6 sm:p-8 ${tone}`}>
        <div className="flex flex-wrap items-center gap-3">
          <Badge>{bundle.readiness.status.replaceAll("_", " ")}</Badge>
          <span className="text-sm text-slate-400">
            {bundle.capability.id}@{bundle.capability.version}
          </span>
        </div>
        <div className="mt-6 flex items-start gap-4">
          <ShieldCheck className="mt-1 h-7 w-7 shrink-0 text-cyan-200" />
          <div>
            <h2 className="text-3xl font-semibold text-white">Local bundle verified</h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              The browser validated the task-neutral product schema and reproduced the bundle
              content hash. Scientific replay remains the responsibility of the offline CLI.
            </p>
          </div>
        </div>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Strategy" value={bundle.strategy} />
          <Metric
            label="Confirmatory semantic"
            value={`${confirmatory.semantic_correct}/${confirmatory.expected}`}
          />
          <Metric
            label="Adversarial semantic"
            value={`${adversarial.semantic_correct}/${adversarial.expected}`}
          />
          <Metric label="Residual records" value={String(bundle.residuals.length)} />
        </dl>
      </Card>

      <section className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <BadgeCheck className="h-5 w-5 text-emerald-200" />
            <h2 className="font-semibold text-white">Execution stages</h2>
          </div>
          <ol className="mt-5 grid gap-2 sm:grid-cols-2">
            {bundle.stages.map((stage, index) => (
              <li
                key={`${stage}-${index}`}
                className="rounded-lg border border-white/8 bg-slate-950/50 px-3 py-2 font-mono text-xs text-slate-300"
              >
                {String(index + 1).padStart(2, "0")} · {stage}
              </li>
            ))}
          </ol>
        </Card>
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <FileJson2 className="h-5 w-5 text-cyan-200" />
            <h2 className="font-semibold text-white">Verified lineage</h2>
          </div>
          <dl className="mt-5 space-y-4 text-sm">
            <Metric label="Run ID" value={bundle.run_id} />
            {referenceBundle ? (
              <>
                <Metric label="Canonical plan" value={referenceBundle.canonical_plan_id} mono />
                <Metric label="Execution" value={referenceBundle.execution_id} mono />
              </>
            ) : null}
            <Metric label="Checkpoint" value={bundle.readiness.selected_checkpoint_id} />
            <Metric label="Adapter SHA-256" value={bundle.readiness.adapter_sha256} mono />
            <Metric label="Bundle SHA-256" value={verifiedHash} mono />
          </dl>
        </Card>
      </section>

      {referenceBundle ? <ReferenceSuccessionDetails bundle={referenceBundle} /> : null}

      {bundle.residuals.length ? (
        <Card className="p-6">
          <h2 className="font-semibold text-white">Residual evidence</h2>
          <p className="mt-2 text-sm text-slate-400">
            Raw model output remains escaped JSON. The browser does not execute artifact content.
          </p>
          <pre className="code-scroll mt-5 max-h-[28rem] overflow-auto rounded-xl border border-white/8 bg-black/30 p-4 text-xs leading-6 text-slate-300">
            {JSON.stringify(bundle.residuals, null, 2)}
          </pre>
        </Card>
      ) : null}
    </>
  );
}

function MultistartResult({
  bundle,
  verifiedHash,
}: {
  bundle: Extract<LocalRunBundle, { schema_version: "inheritbench.web-bundle.v0.4" }>;
  verifiedHash: string;
}) {
  const blocked = bundle.decision.classification === "BLOCKED_BEFORE_FINAL_EVALUATION";
  const candidateCompute = Array.isArray(bundle.compute_accounting.candidate_compute)
    ? bundle.compute_accounting.candidate_compute
    : [];
  return (
    <>
      <Card
        className={`p-6 sm:p-8 ${
          blocked ? "border-amber-300/25 bg-amber-300/5" : "border-cyan-300/25 bg-cyan-300/5"
        }`}
      >
        <div className="flex flex-wrap items-center gap-3">
          <Badge>{bundle.decision.classification.replaceAll("_", " ")}</Badge>
          <span className="text-sm text-slate-400">
            {bundle.capability.id}@{bundle.capability.version}
          </span>
        </div>
        <div className="mt-6 flex items-start gap-4">
          <AlertTriangle className="mt-1 h-7 w-7 shrink-0 text-amber-200" />
          <div>
            <h2 className="text-3xl font-semibold text-white">
              {blocked ? "Final evaluation remained sealed" : "Bounded recovery result verified"}
            </h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              {blocked
                ? "All four prospectively seeded candidates terminated under the frozen numerical-instability guard. No candidate was selected, no final model generation ran, and no readiness score was represented as zero."
                : "The browser verified the bounded multi-start lineage, validation-only selection, locked final evaluation, and replay evidence."}
            </p>
          </div>
        </div>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Candidates attempted" value={String(bundle.candidates.length)} />
          <Metric
            label="Safety-eligible candidates"
            value={String(bundle.candidates.filter((candidate) => candidate.safety_eligible).length)}
          />
          <Metric
            label="Selected candidate"
            value={
              bundle.selection.candidate_index === null
                ? "None"
                : `Candidate ${bundle.selection.candidate_index}`
            }
          />
          <Metric
            label="Final generation calls"
            value={String(bundle.decision.final_evaluation_calls ?? 0)}
          />
        </dl>
      </Card>

      <section className="grid gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <p className="eyebrow">Prospective protocol</p>
          <h2 className="mt-3 font-semibold text-white">Frozen before training</h2>
          <dl className="mt-5 space-y-4 text-sm">
            <Metric label="Amendment" value={bundle.protocol.amendment_id} />
            <Metric label="Amendment SHA-256" value={bundle.protocol.amendment_sha256} mono />
            <Metric
              label="Final-surface manifest"
              value={bundle.protocol.final_surface_manifest_sha256}
              mono
            />
            <Metric label="Ranking surface" value="Recovery validation only" />
            <Metric label="Readiness" value={bundle.readiness.status.replaceAll("_", " ")} />
            <Metric label="Bundle SHA-256" value={verifiedHash} mono />
          </dl>
        </Card>
        <Card className="p-6">
          <p className="eyebrow">Scientific boundary</p>
          <h2 className="mt-3 font-semibold text-white">What this run establishes</h2>
          <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-300">
            <li>Four distinct LoRA initializations passed invariant preflight.</li>
            <li>Supervision, schedule, optimizer, checkpoints, and validation rules were fixed.</li>
            <li>No confirmatory or adversarial evidence influenced candidate ranking.</li>
            <li>The failed trajectories remain evidence; partial checkpoints are not selectable.</li>
            <li>Frozen teacher outputs were used; live generic teacher generation is not proven.</li>
          </ul>
        </Card>
      </section>

      <Card className="p-6">
        <p className="eyebrow">Candidate trajectories</p>
        <h2 className="mt-3 font-semibold text-white">Four fixed initializations</h2>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {bundle.candidates.map((candidate) => {
            const progress = candidateCompute.find(
              (item) =>
                typeof item === "object" &&
                item !== null &&
                "candidate_index" in item &&
                item.candidate_index === candidate.candidate_index,
            ) as Record<string, unknown> | undefined;
            return (
              <div
                key={candidate.candidate_index}
                className="rounded-xl border border-white/8 bg-black/20 p-5"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold text-white">
                    Candidate {candidate.candidate_index}
                  </h3>
                  <Badge>{candidate.training_status}</Badge>
                </div>
                <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Metric label="Seed" value={String(candidate.initialization_seed)} />
                  <Metric
                    label="Partial checkpoints"
                    value={String(progress?.partial_checkpoint_count ?? 0)}
                  />
                  <Metric
                    label="Minimum evidenced tokens"
                    value={String(progress?.minimum_evidenced_processed_tokens ?? 0)}
                  />
                  <Metric
                    label="Safety eligible"
                    value={candidate.safety_eligible ? "Yes" : "No"}
                  />
                </dl>
                <p className="mt-4 break-all font-mono text-[11px] leading-5 text-slate-500">
                  {candidate.initial_adapter_sha256}
                </p>
                {candidate.error ? (
                  <p className="mt-4 text-xs leading-5 text-amber-100/80">{candidate.error}</p>
                ) : null}
              </div>
            );
          })}
        </div>
      </Card>

      <section className="grid gap-5 lg:grid-cols-2">
        <EvidenceJson label="Selection receipt" value={bundle.selection} />
        <EvidenceJson label="Model-free replay" value={bundle.replay_verification} />
        <EvidenceJson label="Stability report" value={bundle.stability} />
        <EvidenceJson label="Historical comparison" value={bundle.historical_comparison} />
      </section>
    </>
  );
}

function ReferenceSuccessionDetails({
  bundle,
}: {
  bundle: Extract<LocalRunBundle, { schema_version: "inheritbench.web-bundle.v0.3" }>;
}) {
  const reproduction = bundle.reproduction;
  const intervention = bundle.intervention;
  const protocol = bundle.protocol_amendment;
  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <Card className="p-6">
        <p className="eyebrow">Seeded reference lineage</p>
        <h2 className="mt-3 font-semibold text-white">Reproduction and recovery</h2>
        <dl className="mt-5 space-y-4 text-sm">
          <Metric
            label="Seeded direct reproduction"
            value={displayValue(reproduction.direct_seeded)}
          />
          <Metric label="Bitwise reproduction" value={displayValue(reproduction.direct_bitwise)} />
          <Metric
            label="Anchored recovery"
            value={displayValue(reproduction.anchored_recovery)}
          />
          <Metric
            label="Historical comparison"
            value={displayValue(reproduction.historical_comparison)}
          />
          <Metric
            label="Protocol amendment"
            value={displayValue(protocol.amendment_sha256)}
            mono
          />
        </dl>
        <p className="mt-5 text-sm leading-6 text-slate-400">
          The reference proof consumes verified frozen teacher outputs. It does not claim live
          generic teacher generation.
        </p>
      </Card>
      <Card className="p-6">
        <p className="eyebrow">Anchored intervention</p>
        <h2 className="mt-3 font-semibold text-white">Deficit-driven anchor selection</h2>
        <dl className="mt-5 grid gap-4 sm:grid-cols-2">
          <Metric
            label="Teacher candidates"
            value={String(bundle.label_accounting.candidate_inputs ?? 0)}
          />
          <Metric
            label="Teacher outputs accepted"
            value={String(bundle.label_accounting.accepted_teacher_outputs ?? 0)}
          />
          <Metric
            label="Teacher labels selected"
            value={String(bundle.label_accounting.teacher_labels ?? 0)}
          />
          <Metric
            label="Anchors selected"
            value={String(bundle.label_accounting.anchor_labels ?? 0)}
          />
        </dl>
        <details className="mt-5 rounded-xl border border-white/8 bg-black/20 p-4">
          <summary className="cursor-pointer text-sm font-medium text-cyan-100">
            Inspect immutable intervention evidence
          </summary>
          <pre className="code-scroll mt-4 max-h-[24rem] overflow-auto text-xs leading-6 text-slate-300">
            {JSON.stringify(intervention, null, 2)}
          </pre>
        </details>
      </Card>
      <Card className="p-6 lg:col-span-2">
        <p className="eyebrow">Final integrity</p>
        <h2 className="mt-3 font-semibold text-white">Reload and replay verification</h2>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <EvidenceJson label="Fresh-base reload" value={bundle.reload_verification} />
          <EvidenceJson label="Model-free replay" value={bundle.replay_verification} />
        </div>
      </Card>
    </section>
  );
}

function EvidenceJson({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-slate-200">{label}</h3>
      <pre className="code-scroll mt-3 max-h-56 overflow-auto rounded-xl border border-white/8 bg-black/30 p-4 text-xs leading-6 text-slate-300">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function displayValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value).replaceAll("_", " ");
  }
  return "Not recorded";
}

function AnchorIntervention({
  bundle,
  verifiedHash,
}: {
  bundle: Extract<
    LocalRunBundle,
    { schema_version: "inheritbench.intervention-web-bundle.v0.2" }
  >;
  verifiedHash: string;
}) {
  return (
    <>
      <Card className="border-amber-300/25 bg-amber-300/5 p-6 sm:p-8">
        <div className="flex flex-wrap items-center gap-3">
          <Badge>ANCHORS REQUIRED</Badge>
          <span className="text-sm text-slate-400">
            {bundle.capability.id}@{bundle.capability.version}
          </span>
        </div>
        <div className="mt-6 flex items-start gap-4">
          <AlertTriangle className="mt-1 h-7 w-7 shrink-0 text-amber-200" />
          <div>
            <h2 className="text-3xl font-semibold text-white">
              Supervision coverage needs intervention
            </h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              Teacher work is preserved. Add only validated anchor records for the declared
              deficits, then resume the same immutable run without repeating completed generation.
            </p>
          </div>
        </div>
      </Card>
      <section className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
        <Card className="p-6">
          <h2 className="font-semibold text-white">Declared intervention</h2>
          <pre className="code-scroll mt-5 max-h-[28rem] overflow-auto rounded-xl border border-white/8 bg-black/30 p-4 text-xs leading-6 text-slate-300">
            {JSON.stringify(bundle.intervention, null, 2)}
          </pre>
        </Card>
        <Card className="p-6">
          <h2 className="font-semibold text-white">Verified lineage</h2>
          <dl className="mt-5 space-y-4 text-sm">
            <Metric label="Run ID" value={bundle.run_id} />
            <Metric label="Strategy" value={bundle.strategy} />
            <Metric label="Bundle SHA-256" value={verifiedHash} mono />
          </dl>
        </Card>
      </section>
    </>
  );
}

function Metric({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</dt>
      <dd className={`${mono ? "break-all font-mono text-xs" : "text-sm"} mt-2 text-slate-100`}>
        {value}
      </dd>
    </div>
  );
}
