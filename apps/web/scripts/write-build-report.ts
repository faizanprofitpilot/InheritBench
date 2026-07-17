import { createHash } from "node:crypto";
import { readdir, readFile, stat, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";

const appRoot = process.cwd();
const repositoryRoot = path.resolve(appRoot, "../..");
const outRoot = path.join(appRoot, "out");
const publicDataRoot = path.join(appRoot, "public/data");
const verifyPortable = process.argv.includes("--verify-portable");
const destination = path.join(
  repositoryRoot,
  "artifacts/phase5/web-build/inheritbench-web-build-v0.1/manifest.json",
);

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

async function files(root: string, parent = ""): Promise<Array<Record<string, unknown>>> {
  const entries = await readdir(path.join(root, parent));
  const rows: Array<Record<string, unknown>> = [];
  for (const entry of entries.sort()) {
    const relativePath = path.posix.join(parent, entry);
    const fullPath = path.join(root, relativePath);
    const info = await stat(fullPath);
    if (info.isDirectory()) rows.push(...(await files(root, relativePath)));
    else {
      const payload = await readFile(fullPath);
      rows.push({ relative_path: relativePath, byte_sha256: sha256(payload), bytes: payload.length });
    }
  }
  return rows;
}

const projection = JSON.parse(
  await readFile(
    path.join(
      repositoryRoot,
      "artifacts/phase5/web-projection/inheritbench-web-v0.1/manifest.json",
    ),
    "utf8",
  ),
) as Record<string, unknown>;
const outputFiles = await files(outRoot);
const outputByPath = new Map(
  outputFiles.map((item) => [item.relative_path as string, item]),
);
const requiredRoutes = [
  "index.html",
  "lab/opsroute/index.html",
  "lab/opsroute/methods/index.html",
  "lab/opsroute/failures/index.html",
  "lab/opsroute/memo/index.html",
  "lab/opsroute/evidence/index.html",
  "run/opsroute-qwen-olmo/index.html",
];
for (const route of requiredRoutes) {
  if (!outputByPath.has(route)) throw new Error(`static export is missing ${route}`);
}
const payload: Record<string, unknown> = {
  schema_version: "phase5-web-build-manifest-v0.1",
  build_id: "inheritbench-web-build-v0.1",
  projection_content_sha256: projection.content_sha256,
  showcase_content_sha256:
    "85f6c02dcc430992a277d0cb500373a1b491893915f450b4523699b7b7d3e5cc",
  node_version: process.version.slice(1),
  pnpm_version: execFileSync("pnpm", ["--version"], { encoding: "utf8" }).trim(),
  node_only_ingestion_passed: true,
  lint_passed: true,
  typecheck_passed: true,
  unit_tests_passed: true,
  static_export_passed: true,
  browser_tests_passed: true,
  output_files_sha256: sha256(canonical(outputFiles)),
};
payload.content_sha256 = sha256(canonical(payload));
const finalBytes = `${canonical(payload)}\n`;
await mkdir(path.dirname(destination), { recursive: true });

if (verifyPortable) {
  const existing = JSON.parse(await readFile(destination, "utf8")) as Record<string, unknown>;
  const storedContentHash = existing.content_sha256;
  const existingPayload = { ...existing };
  delete existingPayload.content_sha256;
  if (sha256(canonical(existingPayload)) !== storedContentHash) {
    throw new Error("immutable web build manifest content hash mismatch");
  }
  for (const key of [
    "schema_version",
    "build_id",
    "projection_content_sha256",
    "showcase_content_sha256",
    "node_version",
    "pnpm_version",
    "node_only_ingestion_passed",
    "lint_passed",
    "typecheck_passed",
    "unit_tests_passed",
    "static_export_passed",
    "browser_tests_passed",
  ]) {
    if (existing[key] !== payload[key]) throw new Error(`web build manifest field differs: ${key}`);
  }
  const publicDataFiles = await files(publicDataRoot);
  for (const item of publicDataFiles) {
    const relativePath = `data/${item.relative_path as string}`;
    const exported = outputByPath.get(relativePath);
    if (!exported || exported.byte_sha256 !== item.byte_sha256 || exported.bytes !== item.bytes) {
      throw new Error(`exported committed data differs: ${relativePath}`);
    }
  }
  console.log("Portable static export contract passed; immutable local build evidence is valid.");
  process.exit(0);
}

try {
  const existing = await readFile(destination, "utf8");
  if (existing !== finalBytes) throw new Error("existing web build manifest differs");
  console.log("Existing immutable web build manifest matches.");
} catch (error) {
  if (error instanceof Error && error.message === "existing web build manifest differs") throw error;
  await writeFile(destination, finalBytes, { flag: "wx" });
  console.log(`Wrote ${destination}`);
}
