"use client";

import {
  ArrowRight,
  BadgeCheck,
  Download,
  ExternalLink,
  FileCheck2,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  downloadJson,
  type SuccessionReplayResult,
} from "@/lib/succession-replay";

export function SuccessionResult({ result }: { result: SuccessionReplayResult }) {
  const clean = result.summary.successor_confirmatory;
  const target = result.summary.target_before_confirmatory;
  const adverse = result.summary.successor_adversarial;
  return (
    <div className="space-y-8" data-testid="succession-result">
      <Card className="relative overflow-hidden border-amber-300/25 p-6 sm:p-8">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-300 to-transparent" />
        <div className="flex flex-wrap items-center gap-3">
          <Badge className="border-amber-300/20 bg-amber-300/8 text-amber-100">
            Conditional pass
          </Badge>
          <span className="text-sm text-slate-500">succession-readiness-v0.1</span>
        </div>
        <h1 tabIndex={-1} className="mt-6 text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          Verified succession replay completed
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">
          The published Qwen → OLMo succession was reproduced from frozen evidence. A fresh readiness report and replay receipt were generated in this browser.
        </p>
        <div className="mt-7 rounded-xl border border-amber-300/15 bg-amber-300/5 p-4 text-[0.9375rem] leading-7 text-amber-50/90">
          Every measured clean operational decision and action was correct. Unresolved adversarial failures require safeguards and additional validation before migration.
        </div>
      </Card>

      <section aria-labelledby="outcome-metrics">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Published successor outcome reproduced</p>
            <h2 id="outcome-metrics" className="mt-3 text-3xl font-semibold text-white">
              Capability recovered; adversarial risk remains.
            </h2>
          </div>
          <span className="text-sm text-slate-500">Clean n=64 · Adversarial n=32</span>
        </div>
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <MetricPanel
            title="Target before succession"
            tone="rose"
            metrics={[
              ["Full-contract exactness", `${target.semantic_exact} / ${target.record_count}`],
              ["Strict validity", `${target.strict_valid} / ${target.record_count}`],
              ["Unauthorized actions", String(target.unauthorized_actions)],
            ]}
          />
          <MetricPanel
            title="Recovered successor"
            tone="green"
            metrics={[
              ["Decision correctness", `${clean.decision_correct} / ${clean.record_count}`],
              ["Tool correctness", `${clean.tool_correct} / ${clean.record_count}`],
              ["Argument correctness", `${clean.arguments_exact} / ${clean.record_count}`],
              ["Approval correctness", `${clean.approval_correct} / ${clean.record_count}`],
              ["Reason-code correctness", `${clean.reason_code_correct} / ${clean.record_count}`],
              ["Full-contract fidelity", `${clean.semantic_exact} / ${clean.record_count} — ${ratio(clean.semantic_exact, clean.record_count)}`],
              ["Strict validity", `${clean.strict_valid} / ${clean.record_count} — ${ratio(clean.strict_valid, clean.record_count)}`],
            ]}
          />
          <MetricPanel
            title="Adversarial limitation"
            tone="amber"
            metrics={[
              ["Semantic exactness", `${adverse.semantic_exact} / ${adverse.record_count} — ${ratio(adverse.semantic_exact, adverse.record_count)}`],
              ["Strict validity", `${adverse.strict_valid} / ${adverse.record_count}`],
              ["Prompt-injection failures", String(result.residuals.adversarial_profile_failures.prompt_injection ?? 0)],
              ["Conflicting-identifier failures", String(result.residuals.adversarial_profile_failures.conflicting_id ?? 0)],
              ["Unauthorized actions", String(adverse.unauthorized_actions)],
              ["Approval bypasses", String(adverse.approval_bypasses)],
            ]}
          />
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[1.05fr_.95fr]">
        <Card className="p-6">
          <div className="flex items-center gap-3 text-emerald-200">
            <BadgeCheck className="h-5 w-5" />
            <h2 className="font-semibold text-white">Recovered successor adapter verified</h2>
          </div>
          <p className="mt-4 text-[0.9375rem] leading-7 text-slate-400">
            The browser confirmed the adapter identity and publication lineage in the immutable replay manifest. Adapter bytes remain on the byte-verified GitHub release.
          </p>
          <dl className="mt-5 space-y-3 text-sm">
            <Definition label="Adapter" value={result.adapter_reference.adapter_id} />
            <Definition label="Archive SHA-256" value={result.adapter_reference.archive_sha256} mono />
          </dl>
          <Button asChild className="mt-6">
            <a
              href={result.adapter_reference.release_url}
              target="_blank"
              rel="noreferrer noopener"
            >
              Open recovered successor adapter <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3 text-amber-200">
            <ShieldAlert className="h-5 w-5" />
            <h2 className="font-semibold text-white">Clean residual</h2>
          </div>
          <p className="mt-4 text-[0.9375rem] leading-7 text-slate-400">
            Nine outputs used incorrect exact policy-code literals. No clean operational decision, tool, argument, approval, reason-code, parser-validity, or safety error occurred.
          </p>
          <Button asChild variant="secondary" className="mt-6">
            <Link href="/lab/opsroute/failures">
              Inspect residual failures <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </Card>
      </section>

      <section aria-labelledby="generated-files">
        <p className="eyebrow">Fresh browser outputs</p>
        <h2 id="generated-files" className="mt-3 text-2xl font-semibold text-white">
          Download the generated decision and receipt.
        </h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <DownloadCard
            icon={<FileCheck2 className="h-5 w-5" />}
            title="Readiness report"
            description="Derived metrics, decision, constraints, and verified adapter identity."
            onClick={() => downloadJson("readiness_report.json", result.readiness)}
          />
          <DownloadCard
            icon={<Download className="h-5 w-5" />}
            title="Replay receipt"
            description="Operation results and hashes for this deterministic browser replay."
            onClick={() => downloadJson("replay_receipt.json", result.receipt)}
          />
        </div>
      </section>

      <section className="flex flex-wrap gap-3 border-t border-white/8 pt-8">
        <Button asChild variant="secondary">
          <Link href="/lab/opsroute/memo">Read GPT-5.6 rationale</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href="/lab/opsroute/evidence">Verify evidence</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href="/lab/opsroute">Explore the full case</Link>
        </Button>
      </section>
    </div>
  );
}

function MetricPanel({
  title,
  tone,
  metrics,
}: {
  title: string;
  tone: "rose" | "green" | "amber";
  metrics: Array<[string, string]>;
}) {
  const toneClass = {
    rose: "border-rose-300/20 bg-rose-300/5",
    green: "border-emerald-300/20 bg-emerald-300/5",
    amber: "border-amber-300/20 bg-amber-300/5",
  }[tone];
  return (
    <Card className={`p-5 ${toneClass}`}>
      <h3 className="font-semibold text-white">{title}</h3>
      <dl className="mt-5 space-y-3">
        {metrics.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4 border-t border-white/7 pt-3 first:border-0 first:pt-0">
            <dt className="text-sm leading-6 text-slate-400">{label}</dt>
            <dd className="text-right font-mono text-sm leading-6 text-slate-100">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function Definition({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className={`${mono ? "break-all font-mono" : "break-words"} mt-1 text-slate-200`}>{value}</dd>
    </div>
  );
}

function DownloadCard({
  icon,
  title,
  description,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <Card className="flex items-start gap-4 p-5">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cyan-300/10 text-cyan-200">{icon}</span>
      <div className="min-w-0 flex-1">
        <h3 className="font-semibold text-white">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
        <Button type="button" variant="secondary" size="sm" className="mt-4" onClick={onClick}>
          Download JSON <Download className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  );
}

function ratio(value: number, denominator: number): string {
  return `${((value / denominator) * 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}%`;
}

