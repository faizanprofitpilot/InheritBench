import Ajv2020 from "ajv/dist/2020.js";

import { canonicalJson, contentSha256 } from "./hashing";
import {
  evaluationResultSchema,
  type EvaluationContract,
  type EvaluationResult,
  type JsonValue,
  type Prediction,
  type RecordDefinition,
} from "./schemas";

const fence = /^\s*```(?:json)?\s*\n([\s\S]*)\n```\s*$/i;
const missing = Symbol("missing");
type Missing = typeof missing;

function tokens(pointer: string): string[] {
  if (pointer === "") return [];
  if (!pointer.startsWith("/")) throw new Error(`invalid JSON Pointer: ${pointer}`);
  return pointer
    .slice(1)
    .split("/")
    .map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"));
}

export function resolvePointer(document: unknown, pointer: string, fallback: unknown = missing): unknown {
  let current: unknown = document;
  for (const token of tokens(pointer)) {
    if (current === null || typeof current !== "object" || !(token in current)) return fallback;
    current = (current as Record<string, unknown>)[token];
  }
  return current;
}

export function pointerExists(document: unknown, pointer: string): boolean {
  return resolvePointer(document, pointer, missing) !== missing;
}

function parseCandidate(candidate: string): {
  parsed: Record<string, JsonValue> | null;
  findings: EvaluationResult["parser_findings"];
} {
  if (!candidate) {
    return { parsed: null, findings: [{ code: "INVALID_JSON", message: "output is empty" }] };
  }
  let value: unknown;
  try {
    value = JSON.parse(candidate);
  } catch (error) {
    return {
      parsed: null,
      findings: [{ code: "INVALID_JSON", message: error instanceof Error ? error.message : String(error) }],
    };
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return {
      parsed: null,
      findings: [{ code: "ROOT_NOT_OBJECT", message: "JSON root must be an object" }],
    };
  }
  return { parsed: value as Record<string, JsonValue>, findings: [] };
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) && Array.isArray(right)) {
    return left.length === right.length && left.every((value, index) => deepEqual(value, right[index]));
  }
  if (
    left !== null &&
    right !== null &&
    typeof left === "object" &&
    typeof right === "object" &&
    !Array.isArray(left) &&
    !Array.isArray(right)
  ) {
    const leftKeys = Object.keys(left).sort();
    const rightKeys = Object.keys(right).sort();
    return (
      deepEqual(leftKeys, rightKeys) &&
      leftKeys.every((key) =>
        deepEqual((left as Record<string, unknown>)[key], (right as Record<string, unknown>)[key]),
      )
    );
  }
  return false;
}

function hashable(value: unknown): string | number | boolean | null | undefined {
  return value !== null && typeof value === "object"
    ? canonicalJson(value as JsonValue)
    : (value as string | number | boolean | null | undefined);
}

function compare(
  predicted: unknown | Missing,
  expected: unknown | Missing,
  mode: "exact" | "list" | "set" | "numeric",
  tolerance?: number | null,
): boolean {
  if (predicted === missing || expected === missing) return false;
  if (mode === "exact" || mode === "list") return deepEqual(predicted, expected);
  if (mode === "set") {
    if (!Array.isArray(predicted) || !Array.isArray(expected)) return false;
    const left = new Set(predicted.map(hashable));
    const right = new Set(expected.map(hashable));
    return left.size === right.size && [...left].every((value) => right.has(value));
  }
  return (
    typeof predicted === "number" &&
    typeof expected === "number" &&
    Math.abs(predicted - expected) <= (tolerance ?? 0)
  );
}

export function validateSafetyAst(node: unknown): void {
  if (node === null || typeof node !== "object" || Array.isArray(node) || Object.keys(node).length !== 1) {
    throw new Error("safety expression must be a one-key object");
  }
  const [operator, value] = Object.entries(node)[0];
  if (operator === "and" || operator === "or") {
    if (!Array.isArray(value) || value.length === 0) throw new Error(`${operator} requires a non-empty list`);
    value.forEach(validateSafetyAst);
    return;
  }
  if (operator === "not") {
    validateSafetyAst(value);
    return;
  }
  if (operator === "exists" || operator === "missing") {
    if (typeof value !== "string" || !value.startsWith("/")) throw new Error(`${operator} requires a JSON Pointer`);
    return;
  }
  if (["eq", "ne", "in", "not_in", "contains"].includes(operator)) {
    if (
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      Object.keys(value).sort().join(",") !== "pointer,value"
    ) {
      throw new Error(`${operator} requires pointer and value`);
    }
    const operand = value as Record<string, unknown>;
    if (typeof operand.pointer !== "string" || !operand.pointer.startsWith("/")) {
      throw new Error(`${operator} pointer is invalid`);
    }
    if (operand.value !== null && typeof operand.value === "object" && !Array.isArray(operand.value)) {
      const reference = operand.value as Record<string, unknown>;
      if (
        Object.keys(reference).join(",") !== "pointer" ||
        typeof reference.pointer !== "string" ||
        !reference.pointer.startsWith("/")
      ) {
        throw new Error(`${operator} value reference is invalid`);
      }
    }
    return;
  }
  throw new Error(`unsupported safety operator ${operator}`);
}

function evalAst(node: Record<string, JsonValue>, document: Record<string, JsonValue>): boolean {
  const [operator, value] = Object.entries(node)[0];
  if (operator === "and") return (value as JsonValue[]).every((child) => evalAst(child as Record<string, JsonValue>, document));
  if (operator === "or") return (value as JsonValue[]).some((child) => evalAst(child as Record<string, JsonValue>, document));
  if (operator === "not") return !evalAst(value as Record<string, JsonValue>, document);
  if (operator === "exists") return pointerExists(document, value as string);
  if (operator === "missing") return !pointerExists(document, value as string);
  const operand = value as Record<string, JsonValue>;
  const actual = resolvePointer(document, operand.pointer as string, missing);
  const expectedSpec = operand.value;
  const expected =
    expectedSpec !== null &&
    typeof expectedSpec === "object" &&
    !Array.isArray(expectedSpec) &&
    Object.keys(expectedSpec).length === 1 &&
    "pointer" in expectedSpec
      ? resolvePointer(document, expectedSpec.pointer as string, missing)
      : expectedSpec;
  if (operator === "eq") return deepEqual(actual, expected);
  if (operator === "ne") return !deepEqual(actual, expected);
  if (operator === "in") return Array.isArray(expected) && expected.some((item) => deepEqual(actual, item));
  if (operator === "not_in") return Array.isArray(expected) && !expected.some((item) => deepEqual(actual, item));
  if (operator === "contains") {
    if (Array.isArray(actual)) return actual.some((item) => deepEqual(item, expected));
    if (typeof actual === "string") return typeof expected === "string" && actual.includes(expected);
    return actual !== null && typeof actual === "object" && typeof expected === "string" && expected in actual;
  }
  throw new Error(operator);
}

export async function evaluateOutput(args: {
  record: RecordDefinition;
  prediction: Prediction;
  contract: EvaluationContract;
}): Promise<EvaluationResult> {
  const { record, prediction, contract } = args;
  const config = contract.evaluator;
  const strictCandidate = prediction.raw_output.trim();
  let { parsed, findings } = parseCandidate(strictCandidate);
  let normalizedCandidate: string | null = null;
  let classification: EvaluationResult["parser_classification"] = "UNPARSEABLE";
  if (parsed !== null) classification = "STRICT_VALID";
  else if (config.whole_output_json_fence) {
    const match = fence.exec(prediction.raw_output);
    if (match) {
      normalizedCandidate = match[1].trim();
      ({ parsed, findings } = parseCandidate(normalizedCandidate));
      if (parsed !== null) classification = "NORMALIZED_VALID";
    }
  }

  const ajv = new Ajv2020({ allErrors: true, strict: false });
  let schemaValid = false;
  let vocabularyConformant = false;
  let crossFieldConformant = false;
  if (parsed !== null) {
    const outputValidator = ajv.compile(contract.schemas.output);
    const outputValid = outputValidator(parsed);
    if (!outputValid) {
      findings = (outputValidator.errors ?? [])
        .map((error) => ({ code: "SCHEMA_INVALID" as const, message: error.message ?? "schema invalid" }))
        .sort((a, b) => a.message.localeCompare(b.message));
    } else {
      schemaValid = true;
      vocabularyConformant =
        config.required_pointers.every((pointer) => pointerExists(parsed, pointer)) &&
        Object.entries(config.controlled_vocabularies).every(([pointer, relative]) => {
          const name = relative.split("/").at(-1)?.replace(/\.json$/, "") ?? relative;
          const allowed = contract.vocabularies[name] ?? [];
          const value = resolvePointer(parsed, pointer, missing);
          return value !== missing && allowed.some((item) => deepEqual(value, item));
        });
      const crossFieldValidator = ajv.compile(contract.schemas.cross_field);
      crossFieldConformant = crossFieldValidator(parsed);
    }
  }

  const eligible = schemaValid && parsed !== null && (crossFieldConformant || !config.strict_requires_cross_field);
  const fieldCorrectness = Object.fromEntries(
    config.comparisons.map((rule) => [
      rule.name,
      eligible
        ? compare(
            resolvePointer(parsed, rule.pointer, missing) as unknown | Missing,
            resolvePointer(record.expected, rule.pointer, missing) as unknown | Missing,
            rule.mode,
            rule.tolerance,
          )
        : false,
    ]),
  );
  const semanticNames = config.comparisons.filter((rule) => rule.semantic).map((rule) => rule.name);
  const semanticMatch =
    eligible && semanticNames.length > 0 && semanticNames.every((name) => fieldCorrectness[name]);
  const structuralExact = eligible && deepEqual(parsed, record.expected);
  const historicalStrictValid =
    classification === "STRICT_VALID" &&
    schemaValid &&
    (crossFieldConformant || !config.strict_requires_cross_field);
  const safetyDocument = {
    prediction: parsed,
    expected: record.expected,
    input: record.input,
    oracle: record.safety_context,
    metrics: { semantic_match: semanticMatch, structural_exact: structuralExact, schema_valid: schemaValid },
  } as Record<string, JsonValue>;
  const safetyFindings =
    parsed === null
      ? []
      : contract.safety.rules
          .filter((rule) => {
            validateSafetyAst(rule.when);
            return evalAst(rule.when, safetyDocument);
          })
          .map(({ code, severity, message }) => ({ code, severity, message }));
  const values = Object.values(fieldCorrectness);
  const payload = {
    schema_version: "inheritbench.generic-evaluation.v0.2" as const,
    record_id: record.record_id,
    raw_output: prediction.raw_output,
    strict_candidate: strictCandidate,
    normalized_candidate: normalizedCandidate,
    parser_classification: classification,
    parse_valid: parsed !== null,
    valid_json: parsed !== null,
    schema_valid: schemaValid,
    vocabulary_conformant: vocabularyConformant,
    cross_field_conformant: crossFieldConformant,
    historical_strict_valid: historicalStrictValid,
    strict_valid: historicalStrictValid,
    structural_exact: structuralExact,
    semantic_match: semanticMatch,
    field_correctness: fieldCorrectness,
    mean_field_correctness: values.length ? values.filter(Boolean).length / values.length : 0,
    parsed_output: parsed,
    expected: record.expected,
    parser_findings: findings,
    safety_findings: safetyFindings,
    coverage: record.coverage,
  };
  return evaluationResultSchema.parse({
    ...payload,
    content_sha256: await contentSha256(payload as unknown as JsonValue),
  });
}
