import { predictionSchema, type JsonValue, type Prediction } from "./schemas";

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

export interface UploadProvenance {
  kind: "local-upload";
  file_name?: string;
  format: "json" | "jsonl";
  bytes: number;
  imported_at: string;
}

export interface UploadParseResult {
  records: Record<string, Prediction>;
  metadata?: Record<string, JsonValue>;
  provenance: UploadProvenance;
  compatible_ids: string[];
  missing_ids: string[];
  unknown_ids: string[];
  evaluation_eligible: boolean;
  readiness_eligible: boolean;
}

export class UploadParseError extends Error {
  constructor(
    message: string,
    readonly code:
      | "FILE_TOO_LARGE"
      | "INVALID_JSON"
      | "INVALID_RECORD"
      | "DUPLICATE_ID"
      | "MISSING_ID",
  ) {
    super(message);
    this.name = "UploadParseError";
  }
}

function decode(input: string | Uint8Array): { text: string; bytes: number } {
  if (typeof input === "string") {
    const bytes = new TextEncoder().encode(input);
    return { text: input, bytes: bytes.byteLength };
  }
  return { text: new TextDecoder().decode(input), bytes: input.byteLength };
}

function normalizeJson(value: unknown): {
  values: unknown[];
  metadata?: Record<string, JsonValue>;
} {
  if (Array.isArray(value)) return { values: value };
  if (value !== null && typeof value === "object") {
    const object = value as Record<string, unknown>;
    const metadata =
      object.metadata !== null && typeof object.metadata === "object" && !Array.isArray(object.metadata)
        ? (object.metadata as Record<string, JsonValue>)
        : undefined;
    if (Array.isArray(object.records)) return { values: object.records, metadata };
    if (
      object.predictions !== null &&
      typeof object.predictions === "object" &&
      !Array.isArray(object.predictions)
    ) {
      return { values: Object.values(object.predictions as object), metadata };
    }
    if ("record_id" in object) return { values: [object], metadata };
  }
  throw new UploadParseError("JSON upload must contain prediction records", "INVALID_RECORD");
}

export function parsePredictionUpload(
  input: string | Uint8Array,
  options: {
    format?: "json" | "jsonl";
    fileName?: string;
    compatibleIds?: Iterable<string>;
    completeFinalIds?: Iterable<string>;
    now?: () => Date;
  } = {},
): UploadParseResult {
  const { text, bytes } = decode(input);
  if (bytes > MAX_UPLOAD_BYTES) {
    throw new UploadParseError(`upload exceeds ${MAX_UPLOAD_BYTES} bytes`, "FILE_TOO_LARGE");
  }
  const format =
    options.format ??
    (options.fileName?.toLowerCase().endsWith(".jsonl") ? "jsonl" : "json");
  let values: unknown[];
  let metadata: Record<string, JsonValue> | undefined;
  try {
    if (format === "jsonl") {
      values = text
        .split(/\r?\n/)
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line));
    } else {
      ({ values, metadata } = normalizeJson(JSON.parse(text)));
    }
  } catch (error) {
    if (error instanceof UploadParseError) throw error;
    throw new UploadParseError(
      `invalid ${format.toUpperCase()}: ${error instanceof Error ? error.message : String(error)}`,
      "INVALID_JSON",
    );
  }

  const records: Record<string, Prediction> = {};
  for (const value of values) {
    let prediction: Prediction;
    try {
      prediction = predictionSchema.parse(value);
    } catch (error) {
      const missing =
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value) &&
        !("record_id" in value);
      throw new UploadParseError(
        missing ? "prediction is missing record_id" : `invalid prediction: ${String(error)}`,
        missing ? "MISSING_ID" : "INVALID_RECORD",
      );
    }
    if (records[prediction.record_id]) {
      throw new UploadParseError(`duplicate record_id ${prediction.record_id}`, "DUPLICATE_ID");
    }
    records[prediction.record_id] = prediction;
  }

  const ids = Object.keys(records);
  const compatible = new Set(options.compatibleIds ?? ids);
  const required = new Set(options.completeFinalIds ?? []);
  const compatibleIds = ids.filter((id) => compatible.has(id));
  const unknownIds = ids.filter((id) => !compatible.has(id));
  const missingIds = [...required].filter((id) => !records[id]);
  const now = options.now ?? (() => new Date());
  return {
    records,
    metadata,
    provenance: {
      kind: "local-upload",
      file_name: options.fileName,
      format,
      bytes,
      imported_at: now().toISOString(),
    },
    compatible_ids: compatibleIds,
    missing_ids: missingIds,
    unknown_ids: unknownIds,
    evaluation_eligible: compatibleIds.length > 0,
    readiness_eligible:
      required.size > 0 &&
      missingIds.length === 0 &&
      unknownIds.length === 0 &&
      ids.length === required.size,
  };
}
