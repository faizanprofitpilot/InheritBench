import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const appRoot = process.cwd();
const repositoryRoot = path.resolve(appRoot, "../..");
const sourceRoot = path.join(
  repositoryRoot,
  "runs/reference/anchored-multistart-repaired-ebf2997799a62800",
);
const destinationRoot = path.join(
  repositoryRoot,
  "artifacts/product/reference-succession-v0.1",
);
const selectedFiles = [
  "web_bundle.json",
  "canonical_plan.json",
  "multistart_candidate_ranking.json",
  "repair_execution_report.json",
  "guard_repair_lineage.json",
  "evidence_manifest.json",
  "replay_manifest.json",
] as const;

function sha256(payload: Buffer | string): string {
  return createHash("sha256").update(payload).digest("hex");
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

await rm(destinationRoot, { recursive: true, force: true });
await mkdir(destinationRoot, { recursive: true });

const files = [];
for (const relativePath of selectedFiles) {
  const payload = await readFile(path.join(sourceRoot, relativePath));
  await writeFile(path.join(destinationRoot, relativePath), payload);
  files.push({
    relative_path: relativePath,
    byte_sha256: sha256(payload),
    bytes: payload.length,
  });
}

const manifest: Record<string, unknown> = {
  schema_version: "inheritbench.reference-succession-projection.v0.1",
  projection_id: "reference-succession-v0.1",
  source_run: "anchored-multistart-repaired-ebf2997799a62800",
  files,
};
manifest.content_sha256 = sha256(canonical(manifest));
await writeFile(path.join(destinationRoot, "manifest.json"), `${canonical(manifest)}\n`);
console.log(`Projected ${files.length} verified reference-run artifacts.`);
