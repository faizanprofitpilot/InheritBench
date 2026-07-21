import { ArrowRight, GitCommitHorizontal, LockKeyhole, Network } from "lucide-react";
import Link from "next/link";

import { IntegrityVerifier } from "@/components/integrity-verifier";
import { PageHeading } from "@/components/page-heading";
import { SourceLineage } from "@/components/source-lineage";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  loadPhase4Decision,
  loadProtocol,
  loadProvenance,
  loadSources,
} from "@/lib/data";

export default function EvidencePage() {
  const sources = loadSources();
  const provenance = loadProvenance();
  const protocol = loadProtocol();
  const decision = loadPhase4Decision();
  return (
    <div className="space-y-16">
      <PageHeading
        eyebrow="Evidence and integrity"
        title="Historical evidence and current assurance stay separate."
        description="The Phase 4 showcase below remains frozen historical evidence. The completed succession inspector and Assurance Lab expose the current readiness evidence without rewriting that history."
      />

      <IntegrityVerifier />

      <Card className="flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="eyebrow">Current readiness evidence</p>
          <h2 className="mt-3 text-2xl font-semibold text-white">Test the assurance layer or inspect how the successor was produced.</h2>
          <p className="mt-3 max-w-3xl text-[0.9375rem] leading-7 text-slate-400">The Assurance Lab re-evaluates precomputed predictions in the browser. The succession inspector preserves training, selection, sealed evaluation, and replay evidence.</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button asChild>
            <Link href="/sandbox/">Open the Assurance Lab <ArrowRight className="h-4 w-4" /></Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href="/run/opsroute-qwen-olmo/">Inspect the completed succession</Link>
          </Button>
        </div>
      </Card>

      <section className="grid gap-5 lg:grid-cols-3">
        <LineageCard
          icon={<GitCommitHorizontal className="h-5 w-5" />}
          title="Protocol commit"
          value={String(provenance.phase4_protocol_commit)}
        />
        <LineageCard
          icon={<LockKeyhole className="h-5 w-5" />}
          title="Phase 4 decision"
          value={String(decision.content_sha256)}
        />
        <LineageCard
          icon={<Network className="h-5 w-5" />}
          title="Web projection"
          value={sources.content_sha256}
        />
      </section>

      <section id="offline-verification" className="scroll-mt-28">
        <div className="max-w-4xl">
          <p className="eyebrow">Historical projection verification</p>
          <h2 className="mt-4 text-3xl font-semibold text-white">Rebuild the Phase 4 display projection byte for byte.</h2>
          <p className="mt-4 text-lg leading-8 text-slate-400">
            Python reads the frozen historical artifacts locally. The web deployment never needs Python, models, credentials, or network data services.
          </p>
          <pre
            className="mt-6 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-5 font-mono text-sm text-cyan-200"
            tabIndex={0}
            aria-label="Offline verification command"
          >
            uv run inheritbench phase5 verify-web-projection
          </pre>
        </div>
      </section>

      <section><SourceLineage sources={sources.sources} /></section>

      <section>
        <p className="eyebrow">Frozen protocol</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Prompt" value={String(protocol.prompt_version ?? "0.1.0")} />
          <Fact label="Parser" value="0.1.0" />
          <Fact label="Evaluator" value="v0" />
          <Fact label="Repeated seeds" value={String(protocol.repeated_seeds)} />
        </div>
      </section>
    </div>
  );
}

function LineageCard({ icon, title, value }: { icon: React.ReactNode; title: string; value: string }) {
  return (
    <Card className="p-5">
      <span className="text-cyan-300">{icon}</span>
      <p className="mt-4 text-sm font-medium text-white">{title}</p>
      <p className="mt-2 break-all font-mono text-sm leading-6 text-slate-400">{value}</p>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-2 font-mono text-lg text-cyan-100">{value}</p>
    </Card>
  );
}
