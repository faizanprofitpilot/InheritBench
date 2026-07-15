import { GitCommitHorizontal, LockKeyhole, Network } from "lucide-react";

import { IntegrityVerifier } from "@/components/integrity-verifier";
import { PageHeading } from "@/components/page-heading";
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

      <section className="grid gap-8 lg:grid-cols-[.85fr_1.15fr]">
        <div>
          <p className="eyebrow">Offline verification</p>
          <h2 className="mt-4 text-3xl font-semibold text-white">Rebuild the display projection byte for byte.</h2>
          <p className="mt-4 text-lg leading-8 text-slate-400">
            Python reads the frozen historical artifacts locally. The web deployment never needs Python, models, credentials, or network data services.
          </p>
          <pre className="mt-6 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-5 font-mono text-sm text-cyan-200">
            uv run inheritbench phase5 verify-web-projection
          </pre>
        </div>
        <Card className="overflow-hidden">
          <div className="border-b border-white/8 px-5 py-4">
            <h2 className="font-semibold text-white">Projection source index</h2>
            <p className="mt-1 text-xs text-slate-500">{sources.sources.length} immutable source references</p>
          </div>
          <div
            className="max-h-[520px] overflow-auto"
            tabIndex={0}
            aria-label="Projection source index scroll area"
          >
            {sources.sources.map((source) => (
              <div key={source.source_id} className="border-b border-white/6 px-5 py-4 last:border-0">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-white">{source.source_id}</p>
                  <span className="text-[10px] uppercase tracking-wider text-cyan-300">
                    {source.evaluation_surface}
                  </span>
                </div>
                <p className="mt-2 break-all font-mono text-xs leading-5 text-slate-500">{source.relative_path}</p>
                <p className="mt-1 truncate font-mono text-[10px] text-slate-700">{source.byte_sha256}</p>
              </div>
            ))}
          </div>
        </Card>
      </section>

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
      <p className="mt-2 break-all font-mono text-xs leading-5 text-slate-500">{value}</p>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 font-mono text-lg text-cyan-100">{value}</p>
    </Card>
  );
}
