import type { Metadata } from "next";

import { LocalRunInspector } from "@/components/local-run-inspector";

export const metadata: Metadata = {
  title: "Inspect local succession run",
  description:
    "Validate and inspect a generic InheritBench succession web bundle entirely in the browser.",
};

export default function LocalRunPage() {
  return (
    <div className="grid-surface min-h-[calc(100vh-4rem)] border-b border-white/8">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <LocalRunInspector />
      </div>
    </div>
  );
}
