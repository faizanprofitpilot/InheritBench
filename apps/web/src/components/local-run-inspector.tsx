"use client";

import { AlertTriangle, FileJson2 } from "lucide-react";
import { useState } from "react";

import { RunInspector } from "@/components/run-inspector";
import { Card } from "@/components/ui/card";
import {
  type LocalRunBundle,
  validateLocalRunBundle,
} from "@/lib/local-run-schema";

export function LocalRunInspector() {
  const [bundle, setBundle] = useState<LocalRunBundle | null>(null);
  const [verifiedHash, setVerifiedHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setBundle(null);
    try {
      const result = await validateLocalRunBundle(file);
      setBundle(result.bundle);
      setVerifiedHash(result.verifiedSha256);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Local run bundle validation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <Card className="p-6 sm:p-8">
        <div className="flex items-center gap-3 text-cyan-200">
          <FileJson2 className="h-5 w-5" />
          <p className="eyebrow">Local run inspection</p>
        </div>
        <h1 className="mt-4 text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          Inspect a succession bundle.
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">
          Load a locally exported <code className="font-mono text-cyan-200">web_bundle.json</code>.
          Validation and rendering stay in your browser; nothing is uploaded.
        </p>
        <div className="mt-7 rounded-xl border border-white/10 bg-white/[0.025] p-5">
          <label htmlFor="local-run-file" className="block font-medium text-white">
            Choose a run bundle
          </label>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            Maximum 5 MiB. Supports current v0.4 and legacy v0.2/v0.3 bundles.
          </p>
          <input
            id="local-run-file"
            type="file"
            accept=".json,application/json"
            className="mt-5 block w-full rounded-xl border border-white/10 bg-slate-950/80 p-3 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-cyan-300/10 file:px-4 file:py-2 file:font-medium file:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
            disabled={busy}
            onChange={(event) => void loadFile(event.target.files?.[0])}
          />
        </div>
      </Card>

      {error ? (
        <Card role="alert" className="border-rose-300/25 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-300" />
            <div>
              <h2 className="font-semibold text-white">Bundle rejected</h2>
              <p className="mt-2 text-sm leading-6 text-rose-100/80">{error}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {bundle ? <RunInspector bundle={bundle} verifiedHash={verifiedHash ?? undefined} /> : null}
    </div>
  );
}
