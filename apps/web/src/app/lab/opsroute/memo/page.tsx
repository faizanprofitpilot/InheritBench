import { CheckCircle2, Cpu, FileJson2, Wrench } from "lucide-react";

import { MemoSections } from "@/components/memo-sections";
import { PageHeading } from "@/components/page-heading";
import { RecommendationSummary } from "@/components/recommendation-summary";
import { Card } from "@/components/ui/card";
import { loadEvidence, loadMemo, loadMemoValidation, loadMigrationProfiles, loadStory, loadSystems } from "@/lib/data";

export default function MemoPage() {
  const memo = loadMemo();
  const validation = loadMemoValidation();
  const evidence = loadEvidence();
  const migration = loadMigrationProfiles();
  const systems = loadSystems();
  const story = loadStory();
  return (
    <div className="space-y-16">
      <PageHeading
        eyebrow="Validated analyst memo"
        badge="Authoritative structured output"
        title="Validated migration recommendation."
        description="A constraint-aware product recommendation generated from the frozen evidence graph. The authoritative GPT-5.6 Sol memo remains unchanged beneath this executive layer."
      />

      <RecommendationSummary memo={memo} profiles={migration.recommendations} systems={systems} story={story} />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MemoMeta icon={<Cpu className="h-5 w-5" />} label="Model" value="GPT-5.6 Sol" />
        <MemoMeta icon={<FileJson2 className="h-5 w-5" />} label="Mode" value="Structured output" />
        <MemoMeta icon={<Wrench className="h-5 w-5" />} label="Attempt policy" value="One repair" />
        <MemoMeta icon={<CheckCircle2 className="h-5 w-5" />} label="Validation" value="Offline passed" />
      </section>

      <MemoSections memo={memo} evidence={evidence} />

      <Card id="evidence-replay" className="p-6 text-[0.9375rem] leading-7 text-slate-400">
        Memo hash <code className="break-all text-cyan-200">{validation.memo_sha256}</code>. Validation hash{" "}
        <code className="break-all text-cyan-200">{validation.content_sha256}</code>.
      </Card>
    </div>
  );
}
function MemoMeta({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Card className="p-5">
      <span className="text-cyan-300">{icon}</span>
      <p className="mt-4 text-xs uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-2 font-medium text-white">{value}</p>
    </Card>
  );
}
