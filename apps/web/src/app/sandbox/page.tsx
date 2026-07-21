import type { Metadata } from "next";

import { SandboxExperience } from "@/components/sandbox/sandbox-experience";
import { loadSandboxPresentation } from "@/lib/data";

export const metadata: Metadata = {
  title: "Interactive Assurance Lab",
  description:
    "Test InheritBench evaluation, safety, readiness, integrity, and replay against frozen or local predictions.",
};

export default function SandboxPage() {
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-slate-950">
      <div className="mx-auto max-w-[90rem] px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <SandboxExperience presentation={loadSandboxPresentation()} />
      </div>
    </div>
  );
}
