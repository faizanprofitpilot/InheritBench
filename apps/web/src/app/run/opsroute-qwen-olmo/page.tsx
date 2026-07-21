import type { Metadata } from "next";

import { RunInspector } from "@/components/run-inspector";
import { loadReferenceSuccession } from "@/lib/data";

export const metadata: Metadata = {
  title: "Qwen to OLMo succession",
  description:
    "Inspect the completed Qwen to OLMo capability succession, readiness decision, and replay evidence.",
};

export default function SuccessionReplayPage() {
  const { bundle, audit } = loadReferenceSuccession();
  return (
    <div className="grid-surface min-h-[calc(100vh-4rem)] border-b border-white/8">
      <div className="mx-auto max-w-[90rem] px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <RunInspector bundle={bundle} audit={audit} showBackLink />
      </div>
    </div>
  );
}
