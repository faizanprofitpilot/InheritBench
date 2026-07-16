"use client";

import { BookOpen, ExternalLink, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { Evidence, Memo } from "@/lib/data-schema";
import { formatMemoText, labelSurface, labelSystem, labelToken } from "@/lib/utils";

type MemoClaim = Memo["executive_summary"][number];

export function MemoSections({ memo, evidence }: { memo: Memo; evidence: Evidence }) {
  const references = useMemo(
    () => new Map(evidence.references.map((reference) => [reference.evidence_id, reference])),
    [evidence.references],
  );
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <nav aria-label="Memo sections" className="h-fit rounded-2xl border border-white/8 bg-slate-950/55 p-4 lg:sticky lg:top-28">
        <div className="flex items-center gap-2 text-sm font-semibold text-white"><BookOpen className="h-4 w-4 text-cyan-300" /> Memo sections</div>
        <div className="mt-4 grid gap-1 text-sm">
          {[
            ["Executive recommendation", "#executive-recommendation"],
            ["Confirmatory evidence", "#executive-readout"],
            ["Transfer assessment", "#transfer-assessment"],
            ["Adversarial evidence", "#adversarial-evidence"],
            ["Migration profiles", "#migration-recommendations"],
            ["Data and compute", "#tradeoffs"],
            ["Limitations", "#limitations"],
            ["Evidence and replay", "#evidence-replay"],
          ].map(([label, href]) => <a key={href} href={href} className="rounded-lg px-3 py-2 text-slate-400 hover:bg-white/5 hover:text-cyan-100">{label}</a>)}
        </div>
      </nav>
      <div className="min-w-0 space-y-10">
      <MemoClaimSection id="executive-readout" title="Executive readout" claims={memo.executive_summary} references={references} restrictions={evidence.restrictions} />
      <MemoClaimSection id="transfer-assessment" title="Transfer assessment" claims={memo.transfer_assessment} references={references} restrictions={evidence.restrictions} />
      <MemoClaimSection id="adversarial-evidence" title="Adversarial weaknesses" claims={memo.adversarial_weaknesses} references={references} restrictions={evidence.restrictions} />
      <section id="migration-recommendations" className="scroll-mt-28">
        <p className="eyebrow">Constraint-aware decisions</p>
        <h2 className="mt-3 text-3xl font-semibold text-white">Migration recommendations</h2>
        <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2">
          {memo.recommendations.map((recommendation) => (
            <Card key={recommendation.profile_id} className="p-5">
              <Badge>{labelToken(recommendation.profile_id)}</Badge>
              <p className="mt-4 text-lg font-semibold text-white">
                {recommendation.recommended_system === "NO_VIABLE_TRAINED_MIGRATION"
                  ? "No viable trained migration"
                  : labelSystem(recommendation.recommended_system)}
              </p>
              <p className="mt-3 text-[0.9375rem] leading-7 text-slate-400">{formatMemoText(recommendation.rationale)}</p>
              <EvidenceLinks evidenceIds={recommendation.evidence_ids} references={references} restrictions={evidence.restrictions} />
            </Card>
          ))}
        </div>
      </section>
      <MemoClaimSection id="tradeoffs" title="Tradeoffs" claims={memo.tradeoffs} references={references} restrictions={evidence.restrictions} />
      <section className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-2">
        <Card id="limitations" className="scroll-mt-28 p-6">
          <h2 className="text-xl font-semibold text-white">Scientific limitations</h2>
          <ul className="mt-4 space-y-3 text-[0.9375rem] leading-7 text-slate-400">
            {memo.limitations.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                {item}
              </li>
            ))}
          </ul>
        </Card>
        <Card id="next-steps" className="scroll-mt-28 p-6">
          <h2 className="text-xl font-semibold text-white">Evidence-backed next steps</h2>
          <ol className="mt-4 space-y-3 text-[0.9375rem] leading-7 text-slate-400">
            {memo.next_steps.map((item, index) => (
              <li key={item} className="flex gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cyan-300/10 font-mono text-xs text-cyan-200">
                  {index + 1}
                </span>
                {item}
              </li>
            ))}
          </ol>
        </Card>
      </section>
      </div>
    </div>
  );
}
function MemoClaimSection({
  title,
  id,
  claims,
  references,
  restrictions,
}: {
  id: string;
  title: string;
  claims: MemoClaim[];
  references: Map<string, Evidence["references"][number]>;
  restrictions: string[];
}) {
  return (
    <section id={id} className="scroll-mt-28">
      <div className="flex items-center gap-3">
        <Sparkles className="h-5 w-5 text-cyan-300" />
        <h2 className="text-2xl font-semibold text-white">{title}</h2>
      </div>
      <div className="mt-5 grid gap-4">
        {claims.map((claim) => (
          <Card key={claim.claim_id} className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{claim.claim_id}</Badge>
              <span className="text-xs uppercase tracking-wider text-slate-600">{claim.comparison}</span>
            </div>
            <p className="mt-4 text-base leading-7 text-slate-200">{formatMemoText(claim.statement)}</p>
            <EvidenceLinks evidenceIds={claim.evidence_ids} references={references} restrictions={restrictions} />
          </Card>
        ))}
      </div>
    </section>
  );
}

function EvidenceLinks({
  evidenceIds,
  references,
  restrictions,
}: {
  evidenceIds: string[];
  references: Map<string, Evidence["references"][number]>;
  restrictions: string[];
}) {
  const [active, setActive] = useState<string | null>(null);
  const reference = active ? references.get(active) : undefined;
  return (
    <Dialog open={active !== null} onOpenChange={(open) => !open && setActive(null)}>
      <div className="mt-5 flex flex-wrap gap-2">
        {evidenceIds.map((evidenceId, index) => (
          <DialogTrigger asChild key={evidenceId}>
            <Button variant="ghost" size="sm" onClick={() => setActive(evidenceId)} aria-label={`View evidence ${evidenceId}`}>
              <ExternalLink className="h-3.5 w-3.5" />
              E{index + 1}
            </Button>
          </DialogTrigger>
        ))}
      </div>
      {reference && (
        <DialogContent>
          <DialogTitle className="pr-10 text-2xl font-semibold text-white">
            Evidence reference
          </DialogTitle>
          <DialogDescription className="mt-2 text-[0.9375rem] leading-7 text-slate-400">
            Exact artifact lineage for this validated memo claim.
          </DialogDescription>
          <dl className="mt-8 space-y-5 text-sm">
            <DrawerValue label="Evidence ID" value={reference.evidence_id} />
            <DrawerValue label="Artifact" value={reference.artifact_path} />
            <DrawerValue label="JSON path" value={reference.json_path} />
            <DrawerValue label="Value" value={JSON.stringify(reference.value)} />
            <DrawerValue
              label="Numerator / denominator"
              value={`${reference.numerator ?? "—"} / ${reference.denominator ?? "—"}`}
            />
            <DrawerValue label="Surface" value={reference.evaluation_surface} />
            <DrawerValue label="Surface label" value={labelSurface(reference.evaluation_surface)} />
            <DrawerValue label="System" value={reference.system_id ? labelSystem(reference.system_id) : "Not system-specific"} />
            <DrawerValue label="Source restrictions" value={restrictions.join(" · ")} />
            <DrawerValue label="Byte hash" value={reference.artifact_byte_sha256} />
            <DrawerValue label="Content hash" value={reference.artifact_content_sha256} />
          </dl>
        </DialogContent>
      )}
    </Dialog>
  );
}

function DrawerValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</dt>
      <dd className="mt-2 break-all font-mono text-sm leading-6 text-slate-200">{value}</dd>
    </div>
  );
}
