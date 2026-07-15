import { CaseExplorer } from "@/components/case-explorer";
import { PageHeading } from "@/components/page-heading";
import { Card } from "@/components/ui/card";
import { loadArchetypeMatrix, loadCases } from "@/lib/data";
import { labelSystem, labelToken, percent } from "@/lib/utils";

export default function FailuresPage() {
  const cases = loadCases();
  const matrix = loadArchetypeMatrix();
  const focusRows = matrix.filter((row) =>
    ["target_full_retrain", "target_hybrid_anchored_distillation_10"].includes(row.system_id),
  );
  return (
    <div className="space-y-16">
      <PageHeading
        eyebrow="Frozen failure evidence"
        badge="Adversarial · n=32"
        title="Inspect what each system actually emitted."
        description="Representative examples are resolved from their recorded evaluation surface. Inputs, expected contracts, raw outputs, parser results, failure labels, hashes, and run lineage are preserved without substitution."
      />

      <section>
        <div className="mb-7 max-w-3xl">
          <h2 className="text-2xl font-semibold text-white">Representative cases</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Six selected adversarial examples and two unchanged no-eligible-case slots emerge from the frozen selection lineage.
          </p>
        </div>
        <CaseExplorer details={cases} />
      </section>

      <section>
        <p className="eyebrow">Archetype matrix</p>
        <h2 className="mt-4 text-3xl font-semibold text-white">Direct retraining versus anchored transfer.</h2>
        <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-400">
          The frozen matrix keeps every archetype denominator and primary-failure count visible.
        </p>
        <Card className="mt-7 overflow-hidden">
          <div className="overflow-x-auto" tabIndex={0} aria-label="Archetype matrix scroll area">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-white/8 bg-white/[0.025] text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-4">System</th>
                  <th className="px-5 py-4">Group</th>
                  <th className="px-5 py-4">n</th>
                  <th className="px-5 py-4">Semantic</th>
                  <th className="px-5 py-4">Strict</th>
                  <th className="px-5 py-4">Argument F1</th>
                  <th className="px-5 py-4">Safety failures</th>
                </tr>
              </thead>
              <tbody>
                {focusRows.map((row) => (
                  <tr key={`${row.system_id}:${row.group_key}`} className="border-b border-white/6 last:border-0">
                    <td className="px-5 py-4 font-medium text-white">{labelSystem(row.system_id)}</td>
                    <td className="px-5 py-4 text-slate-400">{labelToken(row.group_key)}</td>
                    <td className="px-5 py-4 font-mono text-slate-500">{row.prediction_count}</td>
                    <td className="px-5 py-4 font-mono text-cyan-200">
                      {percent(row.semantic_exact.rate)}
                    </td>
                    <td className="px-5 py-4 font-mono text-violet-200">
                      {percent(row.strict_valid.rate)}
                    </td>
                    <td className="px-5 py-4 font-mono text-slate-300">
                      {percent(row.argument_f1.rate)}
                    </td>
                    <td className="px-5 py-4 font-mono text-amber-200">
                      {row.false_actions + row.unauthorized_actions + row.approval_bypasses}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>
    </div>
  );
}
