import { CaseExplorer } from "@/components/case-explorer";
import { FailureMatrixExplorer } from "@/components/failure-matrix-explorer";
import { PageHeading } from "@/components/page-heading";
import { loadArchetypeMatrix, loadCases } from "@/lib/data";

export default function FailuresPage() {
  const cases = loadCases();
  const matrix = loadArchetypeMatrix();
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
          <p className="mt-3 text-[0.9375rem] leading-7 text-slate-400">
            Six selected adversarial examples and two unchanged no-eligible-case slots emerge from the frozen selection lineage.
          </p>
        </div>
        <CaseExplorer details={cases} />
      </section>

      <section>
        <p className="eyebrow">Failure summary and archetype matrix</p>
        <h2 className="mt-4 text-3xl font-semibold text-white">Insight first. Complete evidence on demand.</h2>
        <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-400">
          The frozen matrix keeps every archetype denominator and primary-failure count visible.
        </p>
        <div className="mt-7"><FailureMatrixExplorer rows={matrix} /></div>
      </section>
    </div>
  );
}
