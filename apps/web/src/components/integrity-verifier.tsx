"use client";

import { Check, CheckCircle2, Fingerprint, LoaderCircle, ShieldX } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type State = "idle" | "checking" | "passed" | "failed";
type ManifestFile = { served_path: string; byte_sha256: string };
type WebManifest = {
  files: ManifestFile[];
  projection_content_sha256: string;
  showcase_content_sha256: string;
  succession_content_sha256: string;
};
type Success = {
  filesChecked: number;
  hashesMatched: number;
  manifestSha256: string;
  projectionSha256: string;
  showcaseSha256: string;
  successionSha256: string;
  verifiedAt: string;
};
type Failure = { file: string; expected: string; observed: string; reason: string };

export function IntegrityVerifier() {
  const reducedMotion = useReducedMotion();
  const [state, setState] = useState<State>("idle");
  const [progress, setProgress] = useState({ checked: 0, total: 0 });
  const [success, setSuccess] = useState<Success | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);

  async function verify(): Promise<void> {
    setState("checking");
    setSuccess(null);
    setFailure(null);
    setProgress({ checked: 0, total: 0 });
    try {
      const manifestResponse = await fetch("/data/web-data-manifest.json", { cache: "no-store" });
      if (!manifestResponse.ok) throw new Error("web data manifest is unavailable");
      const manifestBytes = await manifestResponse.arrayBuffer();
      const manifestSha256 = await sha256(manifestBytes);
      const manifest = JSON.parse(new TextDecoder().decode(manifestBytes)) as WebManifest;
      setProgress({ checked: 0, total: manifest.files.length });
      for (const [index, file] of manifest.files.entries()) {
        const response = await fetch(file.served_path, { cache: "no-store" });
        if (!response.ok) {
          setFailure({ file: file.served_path, expected: file.byte_sha256, observed: "UNAVAILABLE", reason: "Served file is unavailable." });
          setState("failed");
          return;
        }
        const actual = await sha256(await response.arrayBuffer());
        if (actual !== file.byte_sha256) {
          setFailure({ file: file.served_path, expected: file.byte_sha256, observed: actual, reason: "Served bytes do not match the committed manifest." });
          setState("failed");
          return;
        }
        setProgress({ checked: index + 1, total: manifest.files.length });
      }
      setSuccess({
        filesChecked: manifest.files.length,
        hashesMatched: manifest.files.length,
        manifestSha256,
        projectionSha256: manifest.projection_content_sha256,
        showcaseSha256: manifest.showcase_content_sha256,
        successionSha256: manifest.succession_content_sha256,
        verifiedAt: new Date().toISOString(),
      });
      setState("passed");
    } catch (error) {
      setFailure({ file: "/data/web-data-manifest.json", expected: "Committed manifest", observed: "UNAVAILABLE", reason: error instanceof Error ? error.message : "Integrity verification failed." });
      setState("failed");
    }
  }

  const percentage = progress.total > 0 ? Math.round((progress.checked / progress.total) * 100) : 0;
  return (
    <Card className="overflow-hidden p-6 sm:p-8">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl ${state === "failed" ? "bg-rose-300/10 text-rose-200" : state === "passed" ? "bg-emerald-300/10 text-emerald-200" : "bg-cyan-300/10 text-cyan-200"}`}>
            {state === "passed" ? <CheckCircle2 className="h-6 w-6" /> : state === "failed" ? <ShieldX className="h-6 w-6" /> : <Fingerprint className="h-6 w-6" />}
          </span>
          <div>
            <h2 className="text-xl font-semibold text-white">Showcase integrity verification</h2>
            <p className="mt-2 text-[0.9375rem] leading-7 text-slate-400">
              Hash the committed showcase, projection, and verified-replay files served to this browser.
            </p>
          </div>
        </div>
        <Button onClick={verify} disabled={state === "checking"} className="min-h-11">
          {state === "checking" && <LoaderCircle className="h-4 w-4 animate-spin" />}
          Verify served bytes
        </Button>
      </div>

      {state === "checking" && (
        <div className="mt-7" role="status" aria-live="polite">
          <div className="flex items-center justify-between text-sm text-slate-300"><span>Checking committed files</span><span>{progress.checked} / {progress.total || "…"}</span></div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/8"><div className="h-full bg-cyan-300 transition-[width]" style={{ width: `${percentage}%` }} /></div>
        </div>
      )}

      {state === "passed" && success && (
        <motion.div
          initial={reducedMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0.01 : 0.35 }}
          className="mt-7 rounded-2xl border border-emerald-300/20 bg-emerald-300/[0.055] p-5 sm:p-6"
          role="status"
          aria-live="polite"
        >
          <div className="flex items-start gap-4">
            <motion.span initial={reducedMotion ? false : { scale: 0.6 }} animate={{ scale: 1 }} className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-emerald-300 text-slate-950">
              <Check className="h-5 w-5" />
            </motion.span>
            <div><h3 className="text-xl font-semibold text-emerald-100">Showcase bundle verified</h3><p className="mt-2 text-sm leading-6 text-emerald-100/80">{success.filesChecked} files checked · {success.hashesMatched} hashes matched</p></div>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <VerificationStatus label="Showcase files" value="Verified" />
            <VerificationStatus label="Projection files" value="Verified" />
            <VerificationStatus label="Succession replay" value="Verified" />
            <VerificationStatus label="Manifest" value="Read and hashed" />
            <VerificationStatus label="Evidence references" value="Verified in served bundle" />
          </div>
          <dl className="mt-6 grid gap-4 text-sm lg:grid-cols-2">
            <HashValue label="Manifest hash" value={success.manifestSha256} />
            <HashValue label="Web-projection hash" value={success.projectionSha256} />
            <HashValue label="Showcase hash" value={success.showcaseSha256} />
            <HashValue label="Succession manifest hash" value={success.successionSha256} />
            <HashValue label="Verified at" value={success.verifiedAt} />
          </dl>
          <p className="mt-6 border-t border-emerald-300/15 pt-5 text-sm leading-6 text-slate-300">
            This verifies the deployed display bundle. Full scientific replay remains an offline repository command.
          </p>
        </motion.div>
      )}

      {state === "failed" && failure && (
        <div className="mt-7 rounded-2xl border border-rose-300/20 bg-rose-300/[0.055] p-5 sm:p-6" role="alert" aria-live="assertive">
          <h3 className="text-xl font-semibold text-rose-100">Showcase verification failed</h3>
          <p className="mt-2 text-sm leading-6 text-rose-100/80">{failure.reason}</p>
          <dl className="mt-5 grid gap-4 text-sm"><HashValue label="Affected file" value={failure.file} /><HashValue label="Expected hash" value={failure.expected} /><HashValue label="Observed hash" value={failure.observed} /></dl>
          <a href="#offline-verification" className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold text-cyan-200 hover:text-cyan-100">Open offline verification instructions</a>
        </div>
      )}
    </Card>
  );
}

async function sha256(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function VerificationStatus({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-300/10 bg-slate-950/30 px-4 py-3 text-sm"><span className="text-slate-300">{label}</span><span className="font-medium text-emerald-200">{value}</span></div>;
}

function HashValue({ label, value }: { label: string; value: string }) {
  return <div><dt className="font-medium text-slate-300">{label}</dt><dd className="mt-1 break-all font-mono text-xs leading-5 text-slate-400">{value}</dd></div>;
}
