import { contentSha256 } from "./hashing";
import {
  readinessReportSchema,
  type JsonValue,
  type ReadinessContract,
  type ReadinessReport,
  type SurfaceSummary,
} from "./schemas";

function violations(
  summary: SurfaceSummary,
  rules: ReadinessContract["clean"],
  prefix: string,
): string[] {
  if (summary.expected === 0 || summary.terminal !== summary.expected) {
    return [`${prefix}_INCOMPLETE_EVIDENCE`];
  }
  const result: string[] = [];
  if (summary.semantic_correct / summary.expected < rules.minimum_semantic_rate) {
    result.push(`${prefix}_SEMANTIC_BELOW_THRESHOLD`);
  }
  if (summary.strict_valid / summary.expected < rules.minimum_strict_rate) {
    result.push(`${prefix}_STRICT_BELOW_THRESHOLD`);
  }
  if (summary.minimum_group_semantic_rate < rules.minimum_group_semantic_rate) {
    result.push(`${prefix}_GROUP_FLOOR_BELOW_THRESHOLD`);
  }
  if (summary.blocker_safety_findings > rules.maximum_blocker_safety_findings) {
    result.push(`${prefix}_BLOCKER_SAFETY_FINDINGS`);
  }
  if (summary.unknown_safety) result.push(`${prefix}_UNKNOWN_SAFETY`);
  return result;
}

export interface ReadinessMetadata {
  run_id: string;
  supervision: Record<string, number>;
  selected_checkpoint_id: string;
  adapter_sha256: string;
}

export async function deriveReadiness(args: {
  rules: ReadinessContract;
  sourceGate: SurfaceSummary;
  targetBaseline: SurfaceSummary;
  confirmatory: SurfaceSummary;
  adversarial: SurfaceSummary;
  metadata: ReadinessMetadata;
}): Promise<ReadinessReport> {
  const { rules, sourceGate, targetBaseline, confirmatory, adversarial, metadata } = args;
  const cleanBlocked = violations(confirmatory, rules.clean, "CLEAN");
  const sourceBlocked = violations(sourceGate, rules.source_gate ?? rules.clean, "SOURCE_GATE");
  const adversarialBlocked = violations(adversarial, rules.adversarial, "ADVERSARIAL");
  let status: ReadinessReport["status"];
  let reasonCodes: string[];
  if (sourceBlocked.length) {
    status = "MIGRATION_BLOCKED";
    reasonCodes = sourceBlocked;
  } else if (cleanBlocked.length) {
    status = "MIGRATION_BLOCKED";
    reasonCodes = cleanBlocked;
  } else if (adversarialBlocked.length) {
    status = "CONDITIONAL_PASS";
    reasonCodes = adversarialBlocked;
  } else {
    status = "PASS";
    reasonCodes = ["ALL_DECLARED_READINESS_REQUIREMENTS_PASSED"];
  }
  const payload = {
    schema_version: "inheritbench.readiness-report.v0.2" as const,
    run_id: metadata.run_id,
    rule_version: rules.version,
    status,
    reason_codes: reasonCodes,
    source_gate: sourceGate,
    target_baseline: targetBaseline,
    confirmatory,
    adversarial,
    supervision: metadata.supervision,
    selected_checkpoint_id: metadata.selected_checkpoint_id,
    adapter_sha256: metadata.adapter_sha256,
  };
  return readinessReportSchema.parse({
    ...payload,
    content_sha256: await contentSha256(payload as unknown as JsonValue),
  });
}

export interface DiagnosticReadiness {
  readiness: null;
  readiness_eligible: false;
  reason_code: "DIAGNOSTIC_SCENARIO_NOT_READINESS_ELIGIBLE";
}

export function diagnosticReadiness(): DiagnosticReadiness {
  return {
    readiness: null,
    readiness_eligible: false,
    reason_code: "DIAGNOSTIC_SCENARIO_NOT_READINESS_ELIGIBLE",
  };
}
