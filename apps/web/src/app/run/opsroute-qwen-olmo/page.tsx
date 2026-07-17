import type { Metadata } from "next";
import { Suspense } from "react";

import { SuccessionWorkflow } from "@/components/succession-workflow";

export const metadata: Metadata = {
  title: "Run verified succession replay",
  description:
    "Verify the published Qwen to OLMo succession and generate a fresh migration-readiness report.",
};

export default function SuccessionReplayPage() {
  return (
    <div className="grid-surface min-h-[calc(100vh-4rem)] border-b border-white/8">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <Suspense fallback={<p className="text-slate-400">Loading verified replay…</p>}>
          <SuccessionWorkflow />
        </Suspense>
      </div>
    </div>
  );
}
