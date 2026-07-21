import { canonicalJson, contentSha256 } from "./hashing";
import { receiptSchema, type JsonValue, type Receipt } from "./schemas";
import type { ScenarioExecution } from "./execute";

export async function createVerificationReceipt(
  execution: ScenarioExecution,
  options: { metadata?: Record<string, JsonValue>; now?: () => Date } = {},
): Promise<Receipt> {
  const now = options.now ?? (() => new Date());
  const resultSha256 = await contentSha256({
    scenario_id: execution.scenario_id,
    input_sha256: execution.input_sha256,
    summaries: execution.summaries,
    readiness: execution.readiness,
    parity: execution.parity,
  } as unknown as JsonValue);
  const payload = {
    schema_version: "inheritbench.local-verification-receipt.v0.1" as const,
    created_at: now().toISOString(),
    scenario_id: execution.scenario_id,
    input_sha256: execution.input_sha256,
    integrity: execution.integrity,
    readiness_status: execution.readiness?.status ?? null,
    parity_verified: execution.parity.verified,
    result_sha256: resultSha256,
    metadata: options.metadata,
  };
  return receiptSchema.parse({
    ...payload,
    receipt_sha256: await contentSha256(payload as unknown as JsonValue),
  });
}

export async function verifyReceiptHash(receipt: Receipt): Promise<boolean> {
  const { receipt_sha256: expected, ...payload } = receipt;
  return (await contentSha256(payload as unknown as JsonValue)) === expected;
}

export function downloadJson(
  value: JsonValue,
  fileName: string,
  environment: {
    document?: Document;
    url?: Pick<typeof URL, "createObjectURL" | "revokeObjectURL">;
  } = {},
): Blob {
  const blob = new Blob([`${canonicalJson(value)}\n`], { type: "application/json" });
  const documentRef = environment.document ?? globalThis.document;
  const urlRef = environment.url ?? globalThis.URL;
  if (!documentRef || !urlRef?.createObjectURL) return blob;
  const href = urlRef.createObjectURL(blob);
  const anchor = documentRef.createElement("a");
  anchor.href = href;
  anchor.download = fileName;
  anchor.hidden = true;
  documentRef.body.append(anchor);
  anchor.click();
  anchor.remove();
  urlRef.revokeObjectURL(href);
  return blob;
}
