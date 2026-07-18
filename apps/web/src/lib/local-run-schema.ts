import { z } from "zod";

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

const surfaceSummarySchema = z
  .object({
    surface: z.string().min(1),
    expected: z.number().int().nonnegative().max(100_000),
    terminal: z.number().int().nonnegative().max(100_000),
    semantic_correct: z.number().int().nonnegative().max(100_000),
    strict_valid: z.number().int().nonnegative().max(100_000),
    vocabulary_conformant: z.number().int().nonnegative().max(100_000),
    cross_field_conformant: z.number().int().nonnegative().max(100_000),
    structural_exact: z.number().int().nonnegative().max(100_000),
    mean_field_correctness: z.number().min(0).max(1),
    blocker_safety_findings: z.number().int().nonnegative().max(100_000),
    unknown_safety: z.number().int().nonnegative().max(100_000),
    minimum_group_semantic_rate: z.number().min(0).max(1),
    group_semantic: z.record(
      z.string(),
      z
        .object({
          correct: z.number().int().nonnegative(),
          total: z.number().int().nonnegative(),
          rate: z.number().min(0).max(1),
        })
        .strict(),
    ),
  })
  .strict();

const readinessSchema = z
  .object({
    schema_version: z.literal("inheritbench.readiness-report.v0.2"),
    run_id: z.string().min(1),
    rule_version: z.string().min(1),
    status: z.enum(["PASS", "CONDITIONAL_PASS", "MIGRATION_BLOCKED"]),
    reason_codes: z.array(z.string()).max(128),
    source_gate: surfaceSummarySchema,
    target_baseline: surfaceSummarySchema,
    confirmatory: surfaceSummarySchema,
    adversarial: surfaceSummarySchema,
    supervision: z
      .object({
        direct_labels: z.number().int().nonnegative(),
        anchor_labels: z.number().int().nonnegative(),
        teacher_labels: z.number().int().nonnegative(),
        upstream_original_labels: z.number().int().nonnegative(),
        candidate_inputs: z.number().int().nonnegative(),
        accepted_teacher_outputs: z.number().int().nonnegative(),
        rejected_teacher_outputs: z.number().int().nonnegative(),
        selected_training_records: z.number().int().nonnegative(),
      })
      .strict(),
    selected_checkpoint_id: z.string().min(1),
    adapter_sha256: sha256Schema,
    content_sha256: sha256Schema,
  })
  .strict();

const finalizedRunBundleSchema = z
  .object({
    schema_version: z.literal("inheritbench.web-bundle.v0.2"),
    run_id: z.string().min(1),
    capability: z
      .object({
        id: z.string().min(1),
        version: z.string().min(1),
      })
      .strict(),
    strategy: z.string().min(1),
    readiness: readinessSchema,
    summaries: z
      .object({
        source_gate: surfaceSummarySchema,
        target_baseline: surfaceSummarySchema,
        confirmatory: surfaceSummarySchema,
        adversarial: surfaceSummarySchema,
      })
      .strict(),
    residuals: z.array(z.record(z.string(), z.unknown())).max(4096),
    label_accounting: z.record(z.string(), z.number().nonnegative()),
    compute_accounting: z.record(z.string(), z.number().nonnegative()),
    adapter: z
      .object({
        adapter_directory: z.string().min(1),
        adapter_sha256: sha256Schema.nullable(),
        checkpoint_id: z.string().nullable(),
        model: z.record(z.string(), z.unknown()),
      })
      .strict(),
    stages: z.array(z.string()).min(1).max(64),
    content_sha256: sha256Schema,
  })
  .strict();

const finalizedReferenceBundleSchema = z
  .object({
    schema_version: z.literal("inheritbench.web-bundle.v0.3"),
    run_id: z.string().min(1),
    canonical_plan_id: z.string().min(1),
    execution_id: z.string().min(1),
    capability: z
      .object({
        id: z.string().min(1),
        version: z.string().min(1),
      })
      .strict(),
    strategy: z.string().min(1),
    protocol_amendment: z.record(z.string(), z.unknown()),
    intervention: z.record(z.string(), z.unknown()),
    reproduction: z.record(z.string(), z.unknown()),
    readiness: readinessSchema,
    summaries: z
      .object({
        source_gate: surfaceSummarySchema,
        target_baseline: surfaceSummarySchema,
        confirmatory: surfaceSummarySchema,
        adversarial: surfaceSummarySchema,
      })
      .strict(),
    residuals: z.array(z.record(z.string(), z.unknown())).max(4096),
    label_accounting: z.record(z.string(), z.number().nonnegative()),
    compute_accounting: z.record(z.string(), z.number().nonnegative()),
    adapter: z
      .object({
        adapter_directory: z.string().min(1),
        adapter_sha256: sha256Schema.nullable(),
        checkpoint_id: z.string().nullable(),
        model: z.record(z.string(), z.unknown()),
      })
      .strict(),
    reload_verification: z.record(z.string(), z.unknown()),
    replay_verification: z.record(z.string(), z.unknown()),
    stages: z.array(z.string()).min(1).max(64),
    content_sha256: sha256Schema,
  })
  .strict();

const interventionRunBundleSchema = z
  .object({
    schema_version: z.literal("inheritbench.intervention-web-bundle.v0.2"),
    run_id: z.string().min(1),
    capability: z
      .object({
        id: z.string().min(1),
        version: z.string().min(1),
      })
      .strict(),
    strategy: z.string().min(1),
    state: z.literal("ANCHORS_REQUIRED"),
    intervention: z.record(z.string(), z.unknown()),
    stages: z.array(z.string()).min(1).max(64),
    content_sha256: sha256Schema,
  })
  .strict();

const multistartCandidateComputeSchema = z
  .object({
    candidate_index: z.number().int().min(0).max(3),
    duration_seconds: z.number().nonnegative(),
    failure_code: z.string().nullable().optional(),
    final_surface_generation_calls: z.literal(0),
    optimizer_steps: z.number().int().nonnegative().max(168),
    processed_tokens: z.number().int().nonnegative().max(272_568),
    training_model_loaded_fresh: z.literal(true),
    validation_model_passes: z.number().int().nonnegative().max(3),
  })
  .strict();

const multistartCandidateSchema = z
  .object({
    adapter_sha256: sha256Schema.nullable(),
    blocker_safety_findings: z.number().int().nonnegative().nullable(),
    candidate_index: z.number().int().min(0).max(3),
    compute: multistartCandidateComputeSchema,
    error: z.string().nullable(),
    failure_code: z.string().nullable(),
    initial_adapter_sha256: sha256Schema,
    initialization_seed: z.number().int().nonnegative().max(0xffffffff),
    safety_eligible: z.boolean(),
    selected_checkpoint_id: z.string().nullable(),
    selected_optimizer_step: z.number().int().positive().nullable(),
    training_status: z.enum(["COMPLETED", "FAILED"]),
    validation_historical_strict_valid: z.number().int().nonnegative().nullable(),
    validation_loss: z.number().nonnegative().nullable(),
    validation_mean_declared_field_correctness: z.number().min(0).max(1).nullable(),
    validation_minimum_group_operational_semantic_rate: z.number().min(0).max(1).nullable(),
    validation_operational_semantic_correct: z.number().int().nonnegative().nullable(),
    validation_operational_semantic_rate: z.number().min(0).max(1).nullable(),
  })
  .strict();

const multistartRunBundleSchema = z
  .object({
    schema_version: z.literal("inheritbench.web-bundle.v0.4"),
    run_id: z.string().min(1),
    capability: z
      .object({
        id: z.string().min(1),
        version: z.string().min(1),
      })
      .strict(),
    strategy: z.string().min(1),
    protocol: z
      .object({
        type: z.literal("BOUNDED_MULTISTART_RECOVERY"),
        amendment_id: z.string().min(1),
        amendment_sha256: sha256Schema,
        candidate_count: z.literal(4),
        seed_manifest_sha256: sha256Schema,
        final_surface_manifest_sha256: sha256Schema,
        validation_only_ranking: z.literal(true),
        final_surfaces_frozen_before_training: z.literal(true),
      })
      .strict(),
    candidates: z.array(multistartCandidateSchema).length(4),
    selection: z
      .object({
        schema_version: z.literal("inheritbench.selected-candidate-receipt.v0.1"),
        status: z.enum(["SELECTED_CANDIDATE_FROZEN", "NO_CANDIDATE_SELECTED"]),
        canonical_multistart_plan_id: z.string().min(1),
        candidate_index: z.number().int().min(0).max(3).nullable(),
        candidate_execution_id: z.string().nullable(),
        selected_checkpoint_id: z.string().nullable(),
        selected_checkpoint_adapter_sha256: sha256Schema.nullable(),
        ranking_sha256: sha256Schema,
        fresh_base_reload_verified: z.boolean(),
        exported_adapter_sha256: sha256Schema.nullable(),
        final_surface_generation_calls_before_freeze: z.literal(0),
        reason_code: z.string().optional(),
        content_sha256: sha256Schema,
      })
      .strict(),
    final_comparison: z.record(z.string(), z.unknown()),
    readiness: z.union([
      readinessSchema,
      z
        .object({
          schema_version: z.literal("inheritbench.multistart-readiness-not-run.v0.1"),
          status: z.literal("NOT_RUN"),
          reason_code: z.literal("BLOCKED_BEFORE_FINAL_EVALUATION"),
          numeric_scores: z.null(),
          readiness_contract_changed: z.literal(false),
        })
        .strict(),
    ]),
    decision: z
      .object({
        schema_version: z.literal("inheritbench.bounded-multistart-decision.v0.1"),
        classification: z.enum([
          "GENERIC_ANCHORED_RECOVERY_CONFIRMED",
          "GENERIC_ANCHORED_RECOVERY_FAILED",
          "BLOCKED_BEFORE_FINAL_EVALUATION",
        ]),
        reason_code: z.string().optional(),
        metric_crosswalk_status: z.literal("METRIC_IDENTITY_RESOLVED"),
        fresh_final_surface_status: z.literal("FRESH_FINAL_SURFACES_FROZEN"),
        multistart_training_status: z.string().min(1),
        selected_candidate_status: z.enum([
          "SELECTED_CANDIDATE_FROZEN",
          "NO_CANDIDATE_SELECTED",
        ]),
        candidate_failure_codes: z.record(z.string(), z.string()).optional(),
        selected_candidate_index: z.number().int().min(0).max(3).optional(),
        selected_checkpoint_id: z.string().optional(),
        selected_adapter_sha256: sha256Schema.optional(),
        readiness: z.enum(["PASS", "CONDITIONAL_PASS", "MIGRATION_BLOCKED", "NOT_RUN"]),
        readiness_reason_codes: z.array(z.string()).optional(),
        readiness_contract_changed: z.literal(false),
        supervision_changed: z.literal(false),
        schedule_changed: z.literal(false),
        final_surfaces_frozen_before_training: z.literal(true),
        candidate_selection_used_recovery_validation_only: z.literal(true),
        final_evaluation_exactly_once: z.boolean(),
        final_evaluation_calls: z.literal(0).optional(),
        fresh_base_reload_verified: z.boolean().optional(),
        replay_verified: z.literal(true),
        live_generic_teacher_generation_proven: z.literal(false),
        content_sha256: sha256Schema,
      })
      .strict(),
    stability: z.record(z.string(), z.unknown()),
    historical_comparison: z.record(z.string(), z.unknown()),
    residuals: z.record(z.string(), z.unknown()),
    label_accounting: z.record(z.string(), z.number().nonnegative()),
    compute_accounting: z.record(z.string(), z.unknown()),
    adapter: z.record(z.string(), z.unknown()),
    reload_verification: z.record(z.string(), z.unknown()).nullable(),
    replay_verification: z.record(z.string(), z.unknown()),
    live_generic_teacher_generation_proven: z.literal(false),
    content_sha256: sha256Schema,
  })
  .strict();

export const localRunBundleSchema = z.union([
  finalizedRunBundleSchema,
  finalizedReferenceBundleSchema,
  interventionRunBundleSchema,
  multistartRunBundleSchema,
]);

export type LocalRunBundle = z.infer<typeof localRunBundleSchema>;

export async function validateLocalRunBundle(file: File): Promise<{
  bundle: LocalRunBundle;
  verifiedSha256: string;
}> {
  if (file.size > 5 * 1024 * 1024) {
    throw new Error("The local run bundle exceeds the 5 MiB safety limit.");
  }
  const text = await file.text();
  const parsed = localRunBundleSchema.parse(JSON.parse(text));
  const { content_sha256: expected, ...content } = parsed;
  const verifiedSha256 = await sha256(stableStringify(content));
  if (verifiedSha256 !== expected) {
    throw new Error("Bundle content hash verification failed.");
  }
  return { bundle: parsed, verifiedSha256 };
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
