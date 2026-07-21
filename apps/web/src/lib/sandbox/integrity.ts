import { contentSha256, sha256Bytes } from "./hashing";
import {
  evaluationContractSchema,
  parityExpectationsSchema,
  readinessContractSchema,
  recordSetSchema,
  sandboxManifestSchema,
  scenarioSchema,
  type IntegrityResult,
  type JsonValue,
  type SandboxAssets,
} from "./schemas";

export type SandboxFetch = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Pick<Response, "ok" | "status" | "arrayBuffer" | "text">>;

export interface IntegrityLoadResult {
  assets: SandboxAssets | null;
  integrity: IntegrityResult;
}

function failed(
  verifiedAssets: string[],
  failedAsset: string,
  error: string,
  expectedHash: string | null = null,
  actualHash: string | null = null,
): IntegrityLoadResult {
  return {
    assets: null,
    integrity: {
      verified: false,
      manifest_hash: null,
      verified_assets: verifiedAssets,
      failed_asset: failedAsset,
      expected_hash: expectedHash,
      actual_hash: actualHash,
      error,
    },
  };
}

async function responseBytes(response: Pick<Response, "arrayBuffer">): Promise<Uint8Array> {
  return new Uint8Array(await response.arrayBuffer());
}

export async function loadSandboxAssets(
  baseUrl: string,
  options: { fetch?: SandboxFetch; manifestPath?: string } = {},
): Promise<IntegrityLoadResult> {
  const fetcher = options.fetch ?? fetch;
  const manifestPath = options.manifestPath ?? "sandbox-manifest.json";
  const root = baseUrl.replace(/\/$/, "");
  let manifestBytes: Uint8Array;
  try {
    const response = await fetcher(`${root}/${manifestPath}`);
    if (!response.ok) return failed([], manifestPath, `HTTP ${response.status}`);
    manifestBytes = await responseBytes(response);
  } catch (error) {
    return failed([], manifestPath, error instanceof Error ? error.message : String(error));
  }

  let manifest;
  try {
    manifest = sandboxManifestSchema.parse(JSON.parse(new TextDecoder().decode(manifestBytes)));
  } catch (error) {
    return failed([], manifestPath, `invalid manifest: ${error instanceof Error ? error.message : String(error)}`);
  }
  const manifestHash = await contentSha256(manifest as unknown as JsonValue);
  if (manifestHash !== manifest.content_sha256) {
    return failed([], manifestPath, "manifest content hash mismatch", manifest.content_sha256, manifestHash);
  }

  const rawAssets: Record<string, JsonValue> = {};
  const verifiedAssets: string[] = [];
  for (const asset of manifest.assets) {
    let bytes: Uint8Array;
    try {
      const response = await fetcher(`${root}/${asset.relative_path}`);
      if (!response.ok) return failed(verifiedAssets, asset.relative_path, `HTTP ${response.status}`);
      bytes = await responseBytes(response);
    } catch (error) {
      return failed(
        verifiedAssets,
        asset.relative_path,
        error instanceof Error ? error.message : String(error),
      );
    }
    const actualHash = await sha256Bytes(bytes);
    if (actualHash !== asset.byte_sha256 || bytes.byteLength !== asset.bytes) {
      return failed(
        verifiedAssets,
        asset.relative_path,
        bytes.byteLength !== asset.bytes ? "asset byte length mismatch" : "asset byte hash mismatch",
        asset.byte_sha256,
        actualHash,
      );
    }
    try {
      rawAssets[asset.relative_path] = JSON.parse(new TextDecoder().decode(bytes)) as JsonValue;
    } catch (error) {
      return failed(
        verifiedAssets,
        asset.relative_path,
        `invalid JSON: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    verifiedAssets.push(asset.relative_path);
  }

  try {
    const recordSets = Object.fromEntries(
      Object.entries(rawAssets)
        .filter(([path]) => path.startsWith("records/"))
        .map(([path, value]) => [path, recordSetSchema.parse(value)]),
    );
    const scenarios = Object.fromEntries(
      Object.entries(rawAssets)
        .filter(([path]) => path.startsWith("scenarios/"))
        .map(([, value]) => {
          const scenario = scenarioSchema.parse(value);
          return [scenario.scenario_id, scenario];
        }),
    );
    const integrity: IntegrityResult = {
      verified: true,
      manifest_hash: manifestHash,
      verified_assets: verifiedAssets,
      failed_asset: null,
      expected_hash: null,
      actual_hash: null,
      error: null,
    };
    return {
      assets: {
        manifest,
        evaluationContract: evaluationContractSchema.parse(rawAssets["evaluation-contract.json"]),
        readinessContract: readinessContractSchema.parse(rawAssets["readiness-contract.json"]),
        parityExpectations: parityExpectationsSchema.parse(rawAssets["parity-expectations.json"]),
        recordSets,
        scenarios,
        rawAssets,
        integrity,
      },
      integrity,
    };
  } catch (error) {
    return failed(
      verifiedAssets,
      "asset-schema",
      `asset schema validation failed: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}
