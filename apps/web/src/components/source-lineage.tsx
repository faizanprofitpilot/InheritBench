import { ChevronDown, Files } from "lucide-react";

import { Card } from "@/components/ui/card";
import { labelSurface, labelToken } from "@/lib/utils";

type Source = {
  source_id: string;
  relative_path: string;
  byte_sha256: string;
  content_sha256: string | null;
  json_path: string;
  evaluation_surface: string;
};

const groupOrder = [
  "Benchmark data",
  "Independent distillation",
  "Distribution-matched recovery",
  "Phase 3B anchored transfer",
  "Adversarial evaluations",
  "GPT memo and validation",
  "Showcase projection",
];

export function SourceLineage({ sources }: { sources: Source[] }) {
  const groups = new Map<string, Source[]>();
  for (const source of sources) {
    const group = sourceGroup(source);
    groups.set(group, [...(groups.get(group) ?? []), source]);
  }
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-2xl border border-white/10 bg-slate-950/65 px-5 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 sm:px-6">
        <div className="flex items-start gap-4"><Files className="mt-0.5 h-5 w-5 text-cyan-300" /><div><h2 className="font-semibold text-white">Inspect source lineage</h2><p className="mt-1 text-sm text-slate-400">{sources.length} immutable references grouped by scientific role.</p></div></div>
        <ChevronDown className="h-5 w-5 shrink-0 text-cyan-300 transition group-open:rotate-180" />
      </summary>
      <div className="mt-4 grid gap-3">
        {groupOrder.filter((group) => groups.has(group)).map((group) => (
          <details key={group} className="group/source rounded-2xl border border-white/8 bg-white/[0.018]">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
              <div><p className="font-medium text-white">{group}</p><p className="mt-1 text-sm text-slate-400">{groups.get(group)!.length} sources</p></div>
              <ChevronDown className="h-4 w-4 text-slate-400 transition group-open/source:rotate-180" />
            </summary>
            <div className="border-t border-white/8">
              {groups.get(group)!.map((source) => (
                <Card key={source.source_id} className="m-3 rounded-xl border-white/7 bg-slate-950/40 p-4 shadow-none">
                  <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-white">{labelToken(source.source_id.replaceAll("-", "_"))}</p><span className="rounded-full bg-cyan-300/8 px-2.5 py-1 text-xs font-medium text-cyan-200">{labelSurface(source.evaluation_surface)}</span></div>
                  <details className="mt-3"><summary className="cursor-pointer text-sm font-medium text-slate-300 hover:text-white">Show raw path and hashes</summary><dl className="mt-3 grid gap-3 text-sm"><SourceValue label="Artifact" value={source.relative_path} /><SourceValue label="Byte hash" value={source.byte_sha256} />{source.content_sha256 && <SourceValue label="Content hash" value={source.content_sha256} />}<SourceValue label="JSON path" value={source.json_path} /></dl></details>
                </Card>
              ))}
            </div>
          </details>
        ))}
      </div>
    </details>
  );
}

function sourceGroup(source: Source): string {
  if (source.source_id.startsWith("opsroute-")) return "Benchmark data";
  if (source.source_id.startsWith("day3-independent")) return "Independent distillation";
  if (source.source_id.startsWith("day3-matched")) return "Distribution-matched recovery";
  if (source.source_id.startsWith("phase3b")) return "Phase 3B anchored transfer";
  if (source.source_id.startsWith("phase4")) return "Adversarial evaluations";
  if (["showcase-memo", "showcase-memo-validation", "showcase-evidence", "showcase-migration-profiles"].includes(source.source_id)) return "GPT memo and validation";
  return "Showcase projection";
}

function SourceValue({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</dt><dd className="mt-1 break-all font-mono text-sm leading-6 text-slate-300">{value}</dd></div>;
}
