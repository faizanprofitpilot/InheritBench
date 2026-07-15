"use client";

import { CheckCircle2, Fingerprint, LoaderCircle, ShieldX } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type State = "idle" | "checking" | "passed" | "failed";

export function IntegrityVerifier() {
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("Ready to verify every served committed file.");

  async function verify(): Promise<void> {
    setState("checking");
    setMessage("Hashing committed showcase and projection files in this browser…");
    try {
      const manifestResponse = await fetch("/data/web-data-manifest.json", { cache: "no-store" });
      if (!manifestResponse.ok) throw new Error("web data manifest is unavailable");
      const manifest = (await manifestResponse.json()) as {
        files: Array<{ served_path: string; byte_sha256: string }>;
      };
      for (const file of manifest.files) {
        const response = await fetch(file.served_path, { cache: "no-store" });
        if (!response.ok) throw new Error(`missing ${file.served_path}`);
        const digest = await crypto.subtle.digest("SHA-256", await response.arrayBuffer());
        const actual = Array.from(new Uint8Array(digest))
          .map((byte) => byte.toString(16).padStart(2, "0"))
          .join("");
        if (actual !== file.byte_sha256) throw new Error(`hash mismatch: ${file.served_path}`);
      }
      setState("passed");
      setMessage(`${manifest.files.length} committed files match their SHA-256 hashes.`);
    } catch (error) {
      setState("failed");
      setMessage(error instanceof Error ? error.message : "Integrity verification failed.");
    }
  }

  const Icon = state === "passed" ? CheckCircle2 : state === "failed" ? ShieldX : Fingerprint;
  return (
    <Card className="p-6 sm:p-8">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-cyan-300/10 text-cyan-200">
            <Icon className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-xl font-semibold text-white">Showcase integrity verification</h2>
            <p className="mt-2 text-sm text-slate-400" aria-live="polite">
              {message}
            </p>
          </div>
        </div>
        <Button onClick={verify} disabled={state === "checking"}>
          {state === "checking" && <LoaderCircle className="h-4 w-4 animate-spin" />}
          Verify served bytes
        </Button>
      </div>
    </Card>
  );
}
