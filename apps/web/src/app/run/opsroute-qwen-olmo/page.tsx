import type { Metadata } from "next";

import { RunInspector } from "@/components/run-inspector";
import { loadReferenceSuccession } from "@/lib/data";

export const metadata: Metadata = {
  title: "Qwen to OLMo succession",
  description:
    "Inspect the browser projection of a completed local InheritBench CLI succession from adapted Qwen to OLMo.",
};

export default function SuccessionReplayPage() {
  const { bundle, audit } = loadReferenceSuccession();
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-slate-950">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <RunInspector bundle={bundle} audit={audit} showBackLink />
      </div>
    </div>
  );
}
