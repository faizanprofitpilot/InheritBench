"use client";

import { ExternalLink, Sparkles } from "lucide-react";
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
import { labelSystem, labelToken } from "@/lib/utils";

type MemoClaim = Memo["executive_summary"][number];

export function MemoSections({ memo, evidence }: { memo: Memo; evidence: Evidence }) {
  const references = useMemo(
    () => new Map(evidence.references.map((reference) => [reference.evidence_id, reference])),
    [evidence.references],
  );
  return (
    <div className="space-y-10">
      <MemoClaimSection title="Executive readout" claims={memo.executive_summary} references={references} />
      <MemoClaimSection title="Transfer assessment" claims={memo.transfer_assessment} references={references} />
      <MemoClaimSection title="Adversarial weaknesses" claims={memo.adversarial_weaknesses} references={references} />
      <section>
        <p className="eyebrow">Constraint-aware decisions</p>
        <h2 className="mt-3 text-3xl font-semibold text-white">Migration recommendations</h2>
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {memo.recommendations.map((recommendation) => (
            <Card key={recommendation.profile_id} className="p-5">
              <Badge>{labelToken(recommendation.profile_id)}</Badge>
              <p className="mt-4 text-lg font-semibold text-white">
                {recommendation.recommended_system === "NO_VIABLE_TRAINED_MIGRATION"
                  ? "No viable trained migration"
                  : labelSystem(recommendation.recommended_system)}
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-400">{recommendation.rationale}</p>
              <EvidenceLinks evidenceIds={recommendation.evidence_ids} references={references} />
            </Card>
          ))}
        </div>
      </section>
      <MemoClaimSection title="Tradeoffs" claims={memo.tradeoffs} references={references} />
      <section className="grid gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-xl font-semibold text-white">Scientific limitations</h2>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-400">
            {memo.limitations.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                {item}
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-6">
          <h2 className="text-xl font-semibold text-white">Evidence-backed next steps</h2>
          <ol className="mt-4 space-y-3 text-sm leading-6 text-slate-400">
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
  );
}
function MemoClaimSection({
  title,
  claims,
  references,
}: {
  title: string;
  claims: MemoClaim[];
  references: Map<string, Evidence["references"][number]>;
}) {
  return (
    <section>
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
            <p className="mt-4 text-base leading-7 text-slate-200">{claim.statement}</p>
            <EvidenceLinks evidenceIds={claim.evidence_ids} references={references} />
          </Card>
        ))}
      </div>
    </section>
  );
}

function EvidenceLinks({
  evidenceIds,
  references,
}: {
  evidenceIds: string[];
  references: Map<string, Evidence["references"][number]>;
}) {
  const [active, setActive] = useState<string | null>(null);
  const reference = active ? references.get(active) : undefined;
  return (
    <Dialog open={active !== null} onOpenChange={(open) => !open && setActive(null)}>
      <div className="mt-5 flex flex-wrap gap-2">
        {evidenceIds.map((evidenceId) => (
          <DialogTrigger asChild key={evidenceId}>
            <Button variant="ghost" size="sm" onClick={() => setActive(evidenceId)}>
              <ExternalLink className="h-3.5 w-3.5" />
              {evidenceId}
            </Button>
          </DialogTrigger>
        ))}
      </div>
      {reference && (
        <DialogContent>
          <DialogTitle className="pr-10 text-2xl font-semibold text-white">
            Evidence reference
          </DialogTitle>
          <DialogDescription className="mt-2 text-sm leading-6 text-slate-400">
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
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-2 break-all font-mono text-xs leading-6 text-slate-200">{value}</dd>
    </div>
  );
}
