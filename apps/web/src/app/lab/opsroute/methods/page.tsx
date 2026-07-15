import { ArrowDown, CheckCircle2, CircleAlert } from "lucide-react";

import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { loadStory } from "@/lib/data";

export default function MethodsPage() {
  const story = loadStory();
  const facts = new Map(story.facts.map((fact) => [fact.fact_id, fact]));
  const value = (id: string) => facts.get(id)?.display_value ?? "—";
  return (
    <div className="space-y-16">
      <PageHeading
        eyebrow="Recovery methods"
        title="From pure distillation failure to anchored transfer."
        description="The method changed only when immutable evidence justified the next bounded condition. The product keeps direct labels, upstream teacher labels, and distribution-design labels separate."
      />

      <section className="grid gap-5 lg:grid-cols-3">
        <MethodCard
          step="01"
          title="Independent distillation"
          metric={`${value("independent-candidates")} → ${value("independent-accepted")}`}
          body={`Strict teacher filtering left ${value("independent-archetypes")} archetypes represented. No target training occurred.`}
          status="Terminal negative"
        />
        <MethodCard
          step="02"
          title="Distribution matching"
          metric={`768 → ${value("matched-accepted")}`}
          body={`${value("blindspot-accepted")} duplicate auto-refund outputs passed; ${value("blindspot-mismatches")} were exact policy mismatches.`}
          status="Blind spot isolated"
        />
        <MethodCard
          step="03"
          title="Anchored transfer"
          metric={`${value("hybrid-teacher-labels")} + ${value("hybrid-anchor-labels")}`}
          body={`${value("hybrid-total")} unique records trained fresh OLMo for ${value("hybrid-tokens")} processed tokens.`}
          status="Completed condition"
        />
      </section>

      <section className="grid gap-8 lg:grid-cols-[.9fr_1.1fr] lg:items-start">
        <div className="lg:sticky lg:top-28">
          <p className="eyebrow">Label lineage</p>
          <h2 className="mt-4 text-3xl font-semibold text-white">Ten direct anchors are not the whole cost.</h2>
          <p className="mt-5 text-lg leading-8 text-slate-400">
            Anchored transfer consumes ten original labels directly at the target, but its teacher and distribution design rely on earlier labeled data.
          </p>
          <div className="mt-6 rounded-xl border border-amber-300/20 bg-amber-300/5 p-4 text-sm leading-6 text-amber-100/80">
            Accurate description: ten original anchors plus 214 teacher outputs, with 224 upstream teacher labels and 224 labeled records used for distribution design.
          </div>
        </div>
        <div className="space-y-3">
          <AccountingRow label="Original labels directly used by target" value="10" tone="direct" />
          <ArrowDown className="mx-auto h-5 w-5 text-slate-700" />
          <AccountingRow label="Exact strict teacher outputs used by target" value="214" tone="teacher" />
          <ArrowDown className="mx-auto h-5 w-5 text-slate-700" />
          <AccountingRow label="Unique target training records" value="224" tone="total" />
          <div className="grid gap-3 pt-3 sm:grid-cols-2">
            <AccountingRow label="Original labels used upstream to train teacher" value="224" tone="upstream" compact />
            <AccountingRow label="Labeled records used to design distribution" value="224" tone="upstream" compact />
          </div>
        </div>
      </section>

      <section>
        <p className="eyebrow">What stayed fixed</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Model target", "Fresh pinned OLMo"],
            ["Training budget", "≤272,643 whole-sequence tokens"],
            ["Evaluator", "Parser 0.1.0 · metrics v0"],
            ["Selection", "Safety-first frozen checkpoint rule"],
          ].map(([label, detail]) => (
            <Card key={label} className="p-5">
              <CheckCircle2 className="h-5 w-5 text-emerald-300" />
              <p className="mt-4 text-sm font-semibold text-white">{label}</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">{detail}</p>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
function MethodCard({
  step,
  title,
  metric,
  body,
  status,
}: {
  step: string;
  title: string;
  metric: string;
  body: string;
  status: string;
}) {
  return (
    <Card className="relative overflow-hidden p-6">
      <span className="font-mono text-xs text-cyan-300">{step}</span>
      <h2 className="mt-6 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-5 font-mono text-4xl font-semibold tracking-tight text-cyan-100">{metric}</p>
      <p className="mt-4 text-sm leading-6 text-slate-400">{body}</p>
      <Badge className="mt-7">{status}</Badge>
    </Card>
  );
}

function AccountingRow({
  label,
  value,
  tone,
  compact = false,
}: {
  label: string;
  value: string;
  tone: "direct" | "teacher" | "total" | "upstream";
  compact?: boolean;
}) {
  const colors = {
    direct: "border-amber-300/20 bg-amber-300/5 text-amber-100",
    teacher: "border-cyan-300/20 bg-cyan-300/5 text-cyan-100",
    total: "border-violet-300/20 bg-violet-300/5 text-violet-100",
    upstream: "border-white/10 bg-white/[0.025] text-slate-200",
  };
  return (
    <div className={`flex items-center justify-between gap-5 rounded-2xl border ${colors[tone]} ${compact ? "p-4" : "p-6"}`}>
      <div className="flex items-center gap-3">
        {tone === "upstream" && <CircleAlert className="h-4 w-4 shrink-0 text-slate-500" />}
        <p className="text-sm leading-6">{label}</p>
      </div>
      <p className="font-mono text-2xl font-semibold">{value}</p>
    </div>
  );
}
