import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const appRoot = process.cwd();
const repositoryRoot = path.resolve(appRoot, "../..");
const showcaseRoot = path.join(
  repositoryRoot,
  "artifacts/showcase/inheritbench-v0.1-gpt",
);
const projectionRoot = path.join(
  repositoryRoot,
  "artifacts/phase5/web-projection/inheritbench-web-v0.1",
);
const successionRoot = path.join(
  repositoryRoot,
  "artifacts/phase5/succession-replay/inheritbench-succession-v0.1",
);
const referenceSuccessionRoot = path.join(
  repositoryRoot,
  "artifacts/product/reference-succession-v0.1",
);
const destinationRoot = path.join(appRoot, "public/data");
const expectedShowcase =
  "85f6c02dcc430992a277d0cb500373a1b491893915f450b4523699b7b7d3e5cc";
const expectedProjectionId = "inheritbench-web-v0.1";
const expectedReferenceProjection =
  "dee9ee1b5b59ad27823643c8dfde2e2d4cc709e12302b6afcf2981260164eb52";

type ManifestEntry = {
  relative_path: string;
  byte_sha256: string;
  content_sha256?: string | null;
  bytes: number;
};

type SuccessionManifest = Record<string, unknown> & {
  replay_records: ManifestEntry;
  replay_context: ManifestEntry;
};

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

function stripContentFields(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stripContentFields);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(
          ([key]) =>
            !["content_sha256", "created_at", "finished_at"].includes(key),
        )
        .map(([key, item]) => [key, stripContentFields(item)]),
    );
  }
  return value;
}

async function loadManifest(root: string): Promise<Record<string, unknown>> {
  return JSON.parse(await readFile(path.join(root, "manifest.json"), "utf8")) as Record<
    string,
    unknown
  >;
}

async function verifyAndCopy(
  root: string,
  outputName: string,
  manifest: Record<string, unknown>,
): Promise<Array<ManifestEntry & { served_path: string }>> {
  const entries = manifest.files;
  if (!Array.isArray(entries)) throw new Error(`${outputName} manifest has no files`);
  const outputRoot = path.join(destinationRoot, outputName);
  await mkdir(outputRoot, { recursive: true });
  const copied: Array<ManifestEntry & { served_path: string }> = [];
  for (const item of entries as ManifestEntry[]) {
    if (item.relative_path.includes("..") || path.isAbsolute(item.relative_path)) {
      throw new Error(`unsafe artifact path: ${item.relative_path}`);
    }
    const source = path.join(root, item.relative_path);
    const payload = await readFile(source);
    if (payload.length !== item.bytes || sha256(payload) !== item.byte_sha256) {
      throw new Error(`artifact hash mismatch: ${item.relative_path}`);
    }
    const destination = path.join(outputRoot, item.relative_path);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, payload);
    copied.push({
      ...item,
      served_path: `/data/${outputName}/${item.relative_path}`,
    });
  }
  const manifestPayload = await readFile(path.join(root, "manifest.json"));
  await writeFile(path.join(outputRoot, "manifest.json"), manifestPayload);
  copied.push({
    relative_path: "manifest.json",
    byte_sha256: sha256(manifestPayload),
    bytes: manifestPayload.length,
    served_path: `/data/${outputName}/manifest.json`,
  });
  return copied;
}

async function verifyAndCopySuccession(
  manifest: SuccessionManifest,
): Promise<Array<ManifestEntry & { served_path: string }>> {
  const outputRoot = path.join(destinationRoot, "succession");
  await mkdir(outputRoot, { recursive: true });
  const copied: Array<ManifestEntry & { served_path: string }> = [];
  for (const item of [manifest.replay_records, manifest.replay_context]) {
    if (item.relative_path.includes("..") || path.isAbsolute(item.relative_path)) {
      throw new Error(`unsafe succession path: ${item.relative_path}`);
    }
    const payload = await readFile(path.join(successionRoot, item.relative_path));
    if (payload.length !== item.bytes || sha256(payload) !== item.byte_sha256) {
      throw new Error(`succession artifact hash mismatch: ${item.relative_path}`);
    }
    await writeFile(path.join(outputRoot, item.relative_path), payload);
    copied.push({
      ...item,
      served_path: `/data/succession/${item.relative_path}`,
    });
  }
  const manifestPayload = await readFile(
    path.join(successionRoot, "succession_run_manifest.json"),
  );
  await writeFile(path.join(outputRoot, "succession_run_manifest.json"), manifestPayload);
  copied.push({
    relative_path: "succession_run_manifest.json",
    byte_sha256: sha256(manifestPayload),
    content_sha256: String(manifest.content_sha256),
    bytes: manifestPayload.length,
    served_path: "/data/succession/succession_run_manifest.json",
  });
  return copied;
}

async function main(): Promise<void> {
  const showcase = await loadManifest(showcaseRoot);
  const projection = await loadManifest(projectionRoot);
  const succession = JSON.parse(
    await readFile(path.join(successionRoot, "succession_run_manifest.json"), "utf8"),
  ) as SuccessionManifest;
  const referenceSuccession = await loadManifest(referenceSuccessionRoot);
  const showcaseContent = sha256(canonical(stripContentFields(showcase)));
  const projectionContent = sha256(canonical(stripContentFields(projection)));
  if (
    showcase.content_sha256 !== expectedShowcase ||
    showcaseContent !== expectedShowcase
  ) {
    throw new Error("frozen showcase manifest verification failed");
  }
  if (
    projection.projection_id !== expectedProjectionId ||
    projection.content_sha256 !== projectionContent
  ) {
    throw new Error("frozen Phase 5 projection verification failed");
  }
  const referenceContent = sha256(canonical(stripContentFields(referenceSuccession)));
  if (
    referenceSuccession.projection_id !== "reference-succession-v0.1" ||
    referenceSuccession.content_sha256 !== expectedReferenceProjection ||
    referenceContent !== expectedReferenceProjection
  ) {
    throw new Error("frozen reference succession projection verification failed");
  }
  const successionContent = sha256(canonical(stripContentFields(succession)));
  if (
    succession.schema_version !== "succession-run-manifest-v0.1" ||
    succession.content_sha256 !== successionContent
  ) {
    throw new Error("frozen succession replay verification failed");
  }
  await rm(destinationRoot, { recursive: true, force: true });
  const files = [
    ...(await verifyAndCopy(showcaseRoot, "showcase", showcase)),
    ...(await verifyAndCopy(projectionRoot, "projection", projection)),
    ...(await verifyAndCopySuccession(succession)),
    ...(await verifyAndCopy(
      referenceSuccessionRoot,
      "reference-succession",
      referenceSuccession,
    )),
  ].sort((left, right) => left.served_path.localeCompare(right.served_path));
  const webManifest = {
    schema_version: "phase5-web-data-manifest-v0.1",
    showcase_content_sha256: expectedShowcase,
    projection_content_sha256: projection.content_sha256,
    succession_content_sha256: succession.content_sha256,
    reference_succession_content_sha256: expectedReferenceProjection,
    files,
  };
  await writeFile(
    path.join(destinationRoot, "web-data-manifest.json"),
    `${canonical(webManifest)}\n`,
  );
  console.log(`Validated and ingested ${files.length} committed files.`);
}

await main();
