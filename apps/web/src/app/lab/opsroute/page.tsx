import { ArrowRight, Banknote, RefreshCcw } from "lucide-react";
import Link from "next/link";

import { MigrationProfiles } from "@/components/migration-profiles";
import { PageHeading } from "@/components/page-heading";
import { SurfaceExplorer } from "@/components/surface-explorer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { loadMigrationProfiles, loadSystems } from "@/lib/data";

export default function OpsRoutePage() {
  const systems = loadSystems();
  const migration = loadMigrationProfiles();
  return (
    <div className="space-y-20">
      <PageHeading
        eyebrow="OpsRoute v0.1.0"
        badge="Published experiment"
        title="Operational routing under strict contracts."
        description="Two policy families test whether a successor can choose the correct decision, tool, arguments, approval state, policy code, and reason code—without repairing invalid output."
      >
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/run/opsroute-qwen-olmo/">Run verified succession replay</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href="/lab/opsroute/methods">Study the recovery methods</Link>
          </Button>
        </div>
      </PageHeading>

      <section className="grid gap-5 md:grid-cols-2">
        <DomainCard
          icon={<Banknote className="h-5 w-5" />}
          title="Refund policy routing"
          description="Duplicate payments, approval thresholds, fraud review, authorization, evidence completeness, settlement state, and refund windows."
        />
        <DomainCard
          icon={<RefreshCcw className="h-5 w-5" />}
          title="Subscription cancellation and retention"
          description="Cancellation confirmation, locked contracts, balances, pauses, retention eligibility, requester authorization, and explicit intent."
        />
      </section>

      <section>
        <div className="mb-8 max-w-3xl">
          <p className="eyebrow">Six systems · two surfaces</p>
          <h2 className="mt-4 text-3xl font-semibold text-white">Capability and resilience are not the same result.</h2>
          <p className="mt-4 text-lg leading-8 text-slate-400">
            Confirmatory evidence contains 64 clean records. Adversarial evidence contains 32 untouched stress cases.
          </p>
        </div>
        <Card className="p-5 sm:p-7">
          <SurfaceExplorer systems={systems} />
        </Card>
      </section>

      <section>
        <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow">Migration recommendations</p>
            <h2 className="mt-4 text-3xl font-semibold text-white">The best successor depends on the constraint.</h2>
            <p className="mt-4 text-lg leading-8 text-slate-400">
              Anchored transfer leads the clean confirmatory surface. Full retraining leads adversarial semantic performance.
            </p>
          </div>
          <Button asChild variant="secondary">
            <Link href="/lab/opsroute/memo">
              Read analyst rationale <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
        <MigrationProfiles profiles={migration.recommendations} />
      </section>
    </div>
  );
}
function DomainCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <Card className="p-6">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-cyan-300/10 text-cyan-200">{icon}</span>
      <h2 className="mt-5 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-3 text-[0.9375rem] leading-7 text-slate-400">{description}</p>
    </Card>
  );
}
