import { ArrowRight, Boxes, BrainCircuit, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { StoryRail } from "@/components/story-rail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { loadStory, loadSystems } from "@/lib/data";
import { labelSystem } from "@/lib/utils";

export default function HomePage() {
  const story = loadStory();
  const systems = loadSystems();
  const source = systems.find((system) => system.system_id === "source_adapted_full")!;
  const target = systems.find((system) => system.system_id === "target_untouched")!;
  return (
    <>
      <section className="grid-surface relative overflow-hidden border-b border-white/8">
        <div className="mx-auto grid max-w-7xl gap-14 px-4 py-20 sm:px-6 sm:py-28 lg:grid-cols-[1.1fr_.9fr] lg:items-center lg:px-8 lg:py-32">
          <div>
            <div className="flex flex-wrap gap-2">
              {story.product_labels.map((label) => (
                <Badge key={label}>{label}</Badge>
              ))}
            </div>
            <h1 className="mt-7 max-w-4xl text-balance text-5xl font-semibold tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl">
              Your successor model does not inherit capability by default.
            </h1>
            <p className="mt-7 max-w-2xl text-balance text-lg leading-8 text-slate-400 sm:text-xl">
              {story.thesis}
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link href="/lab/opsroute">
                  Explore the experiment <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary">
                <Link href="/lab/opsroute/memo">Read the validated GPT memo</Link>
              </Button>
            </div>
          </div>
          <Card className="relative overflow-hidden p-6 sm:p-8">
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
            <p className="eyebrow">Confirmatory capability break · n=64</p>
            <div className="mt-7 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
              <MetricBlock
                title={labelSystem(source.system_id)}
                semantic={source.confirmatory_semantic}
                strict={source.confirmatory_strict}
                tone="source"
              />
              <ArrowRight className="h-6 w-6 text-slate-600" />
              <MetricBlock
                title={labelSystem(target.system_id)}
                semantic={target.confirmatory_semantic}
                strict={target.confirmatory_strict}
                tone="target"
              />
            </div>
            <div className="mt-7 rounded-xl border border-amber-300/15 bg-amber-300/5 p-4 text-sm leading-6 text-amber-100/80">
              Same task contract. Different architecture. Zero untouched target capability on the clean surface.
            </div>
          </Card>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <p className="eyebrow">One frozen experiment</p>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Follow the evidence from capability break to migration decision.
          </h2>
          <p className="mt-4 text-lg leading-8 text-slate-400">
            Every number below is projected from immutable artifacts with a source path and hash.
          </p>
        </div>
        <div className="mt-10">
          <StoryRail story={story} />
        </div>
      </section>

      <section className="border-y border-white/8 bg-white/[0.018]">
        <div className="mx-auto grid max-w-7xl gap-5 px-4 py-16 sm:px-6 md:grid-cols-3 lg:px-8">
          <LinkCard
            href="/lab/opsroute/methods"
            icon={<Boxes className="h-5 w-5" />}
            title="Compare recovery methods"
            description="Inspect independent distillation, distribution matching, and anchored transfer accounting."
          />
          <LinkCard
            href="/lab/opsroute/failures"
            icon={<ShieldCheck className="h-5 w-5" />}
            title="Inspect exact failures"
            description="Open frozen prompts, raw outputs, parser classes, metrics, and run lineage."
          />
          <LinkCard
            href="/lab/opsroute/memo"
            icon={<BrainCircuit className="h-5 w-5" />}
            title="Read the GPT-5.6 analysis"
            description="Review the authoritative structured memo and open every evidence reference."
          />
        </div>
      </section>
    </>
  );
}
function MetricBlock({
  title,
  semantic,
  strict,
  tone,
}: {
  title: string;
  semantic: number;
  strict: number;
  tone: "source" | "target";
}) {
  const color = tone === "source" ? "text-cyan-200" : "text-rose-200";
  return (
    <div>
      <p className="text-xs font-medium text-slate-400">{title}</p>
      <p className={`mt-4 font-mono text-4xl font-semibold ${color}`}>
        {(semantic * 100).toFixed(3)}%
      </p>
      <p className="mt-2 text-xs text-slate-500">semantic exactness</p>
      <p className={`mt-5 font-mono text-xl ${color}`}>{(strict * 100).toFixed(3)}%</p>
      <p className="mt-1 text-xs text-slate-500">strict validity</p>
    </div>
  );
}

function LinkCard({
  href,
  icon,
  title,
  description,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Link href={href} className="group rounded-2xl border border-white/10 bg-slate-950/50 p-6 transition hover:-translate-y-1 hover:border-cyan-300/30">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-cyan-300/10 text-cyan-200">
        {icon}
      </span>
      <h3 className="mt-6 text-lg font-semibold text-white">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-slate-400">{description}</p>
      <span className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-cyan-200">
        Open lab <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
      </span>
    </Link>
  );
}
