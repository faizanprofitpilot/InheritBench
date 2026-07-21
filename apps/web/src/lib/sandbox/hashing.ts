import type { JsonValue } from "./schemas";

function normalize(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(normalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, normalize(value[key])]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("canonical JSON cannot encode non-finite numbers");
  }
  return value;
}

export function canonicalJson(value: JsonValue): string {
  return JSON.stringify(normalize(value));
}

export function canonicalJsonBytes(value: JsonValue): Uint8Array {
  return new TextEncoder().encode(canonicalJson(value));
}

export async function sha256Bytes(bytes: Uint8Array): Promise<string> {
  const copy = Uint8Array.from(bytes);
  const digest = await crypto.subtle.digest("SHA-256", copy);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function stripContentFields(
  value: JsonValue,
  excluded = new Set<string>(["content_sha256"]),
): JsonValue {
  if (Array.isArray(value)) return value.map((item) => stripContentFields(item, excluded));
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !excluded.has(key))
        .map(([key, item]) => [key, stripContentFields(item, excluded)]),
    );
  }
  return value;
}

export async function contentSha256(
  value: JsonValue,
  excluded = new Set<string>(["content_sha256"]),
): Promise<string> {
  return sha256Bytes(canonicalJsonBytes(stripContentFields(value, excluded)));
}

export async function inputSha256(value: JsonValue): Promise<string> {
  return sha256Bytes(canonicalJsonBytes(value));
}
