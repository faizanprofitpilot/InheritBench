import { CheckCircle2, Cpu, FileJson2, Wrench } from "lucide-react";

import { MemoSections } from "@/components/memo-sections";
import { PageHeading } from "@/components/page-heading";
import { Card } from "@/components/ui/card";
import { loadEvidence, loadMemo, loadMemoValidation } from "@/lib/data";

export default function MemoPage() {
  const memo = loadMemo();
  const validation = loadMemoValidation();
  const evidence = loadEvidence();
  return (
    <div className="space-y-16">
      <PageHeading
        eyebrow="Validated analyst memo"
        badge="Authoritative structured output"
        title={memo.title}
        description="GPT-5.6 Sol synthesized only the validated evidence graph. The JSON below is authoritative; the interface does not regenerate, summarize, or rewrite it."
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MemoMeta icon={<Cpu className="h-5 w-5" />} label="Model" value="GPT-5.6 Sol" />
        <MemoMeta icon={<FileJson2 className="h-5 w-5" />} label="Mode" value="Structured output" />
        <MemoMeta icon={<Wrench className="h-5 w-5" />} label="Attempt policy" value="One repair" />
        <MemoMeta icon={<CheckCircle2 className="h-5 w-5" />} label="Validation" value="Offline passed" />
      </section>

      <MemoSections memo={memo} evidence={evidence} />

      <Card className="p-6 text-sm leading-6 text-slate-400">
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
      <p className="mt-4 text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 font-medium text-white">{value}</p>
    </Card>
  );
}
