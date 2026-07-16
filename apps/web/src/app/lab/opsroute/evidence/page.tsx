import { GitCommitHorizontal, LockKeyhole, Network } from "lucide-react";

import { IntegrityVerifier } from "@/components/integrity-verifier";
import { PageHeading } from "@/components/page-heading";
import { SourceLineage } from "@/components/source-lineage";
import { Card } from "@/components/ui/card";
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
        title="Every displayed fact resolves to frozen bytes."
        description="The deployed product contains a committed display projection and the authoritative Phase 4 showcase. Browser verification checks served hashes; scientific replay remains an offline repository command."
      />

      <IntegrityVerifier />

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
          <p className="eyebrow">Offline verification</p>
          <h2 className="mt-4 text-3xl font-semibold text-white">Rebuild the display projection byte for byte.</h2>
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
