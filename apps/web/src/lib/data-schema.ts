import { z } from "zod";

const sha = z.string().regex(/^[0-9a-f]{64}$/);

export const systemSummarySchema = z
  .object({
    system_id: z.string(),
    comparison_role: z.enum(["SOURCE_REFERENCE", "TARGET_MIGRATION_CANDIDATE"]),
    confirmatory_semantic: z.number(),
    confirmatory_strict: z.number(),
    confirmatory_unauthorized_actions: z.number().int(),
    confirmatory_approval_bypasses: z.number().int(),
    adversarial_semantic: z.number(),
    adversarial_strict: z.number(),
    adversarial_argument_f1: z.number(),
    adversarial_safety_failures: z.number().int(),
    direct_original_labels: z.number().int(),
    upstream_original_labels: z.number().int(),
    complexity: z.string(),
    source_teacher_required: z.boolean(),
    viable: z.boolean(),
    viability_reasons: z.array(z.string()),
    pareto_dominated: z.boolean(),
    dominated_by: z.array(z.string()),
  })
  .strict();

export const storySchema = z
  .object({
    schema_version: z.literal("phase5-story-v0.1"),
    projection_id: z.literal("inheritbench-web-v0.1"),
    thesis: z.string(),
    product_labels: z.array(z.string()).length(3),
    confirmatory_denominator: z.literal(64),
    adversarial_denominator: z.literal(32),
    stages: z.array(
      z
        .object({
          stage_id: z.string(),
          eyebrow: z.string(),
          title: z.string(),
          summary: z.string(),
          fact_ids: z.array(z.string()).min(1),
        })
        .strict(),
    ),
    facts: z.array(
      z
        .object({
          fact_id: z.string(),
          label: z.string(),
          value: z.unknown(),
          display_value: z.string(),
          source_ids: z.array(z.string()).min(1),
        })
        .strict(),
    ),
    prohibited_blended_score: z.literal(true),
    content_sha256: sha,
  })
  .strict();

const casePredictionSchema = z
  .object({
    system_id: z.string(),
    split: z.string(),
    run_id: z.string(),
    prediction_id: z.string(),
    raw_output: z.string(),
    parser_result: z.record(z.string(), z.unknown()),
    expected_contract: z.record(z.string(), z.unknown()),
    metrics: z.record(z.string(), z.unknown()),
    primary_failure: z.string(),
    failure_tags: z.array(z.string()),
    prediction_content_sha256: sha,
    run_content_sha256: sha,
    split_sha256: sha,
    oracle_sha256: sha,
    prediction_artifact_byte_sha256: sha,
  })
  .strict();

export const caseDetailsSchema = z
  .object({
    schema_version: z.literal("phase5-case-details-v0.1"),
    projection_id: z.literal("inheritbench-web-v0.1"),
    case_selection_sha256: sha,
    selection_parent_sha256: sha,
    cases: z.array(
      z
        .object({
          schema_version: z.literal("phase5-representative-case-v0.1"),
          slot: z.string(),
          status: z.enum(["SELECTED", "NO_ELIGIBLE_CASE"]),
          eligibility_reason: z.string(),
          selection_rank: sha.nullable(),
          evaluation_surface: z
            .enum(["confirmatory", "adversarial", "exploratory"])
            .nullable(),
          example_id: z.string().nullable(),
          scenario_family: z.string().nullable(),
          archetype: z.string().nullable(),
          input: z.record(z.string(), z.unknown()).nullable(),
          expected_contract: z.record(z.string(), z.unknown()).nullable(),
          system_predictions: z.array(casePredictionSchema),
          selection_parent_sha256: sha,
          content_sha256: sha,
        })
        .strict(),
    ),
    selected_count: z.literal(6),
    no_eligible_count: z.literal(2),
    content_sha256: sha,
  })
  .strict();

export const sourceIndexSchema = z
  .object({
    schema_version: z.literal("phase5-source-index-v0.1"),
    projection_id: z.literal("inheritbench-web-v0.1"),
    sources: z.array(
      z
        .object({
          schema_version: z.literal("phase5-source-reference-v0.1"),
          source_id: z.string(),
          relative_path: z.string(),
          byte_sha256: sha,
          content_sha256: sha.nullable(),
          json_path: z.string(),
          evaluation_surface: z.enum([
            "confirmatory",
            "adversarial",
            "exploratory",
            "cross_surface",
            "not_applicable",
          ]),
        })
        .strict(),
    ),
    content_sha256: sha,
  })
  .strict();

export const matrixRowSchema = z
  .object({
    system_id: z.string(),
    group_key: z.string(),
    prediction_count: z.number().int(),
    semantic_exact: z
      .object({ denominator: z.number().int(), numerator: z.number(), rate: z.number() })
      .strict(),
    strict_valid: z
      .object({ denominator: z.number().int(), numerator: z.number(), rate: z.number() })
      .strict(),
    argument_f1: z
      .object({ denominator: z.number().int(), numerator: z.number(), rate: z.number() })
      .strict(),
    safety_known: z.number().int(),
    safety_unknown: z.number().int(),
    false_actions: z.number().int(),
    unauthorized_actions: z.number().int(),
    approval_bypasses: z.number().int(),
    primary_failures: z.record(z.string(), z.number().int()),
  })
  .strict();

const claimSchema = z
  .object({
    claim_id: z.string(),
    compared_systems: z.array(z.string()),
    comparison: z.string(),
    evidence_ids: z.array(z.string()),
    statement: z.string(),
  })
  .strict();

export const memoSchema = z
  .object({
    schema_version: z.string(),
    memo_kind: z.literal("GPT_5_6_SOL"),
    title: z.string(),
    executive_summary: z.array(claimSchema),
    transfer_assessment: z.array(claimSchema),
    adversarial_weaknesses: z.array(claimSchema),
    recommendations: z.array(
      z
        .object({
          profile_id: z.string(),
          recommended_system: z.string(),
          rationale: z.string(),
          evidence_ids: z.array(z.string()),
        })
        .strict(),
    ),
    tradeoffs: z.array(claimSchema),
    limitations: z.array(z.string()),
    next_steps: z.array(z.string()),
    evidence_pack_sha256: sha,
    generated_at: z.string(),
    content_sha256: sha,
  })
  .strict();

export const memoValidationSchema = z
  .object({
    schema_version: z.string(),
    validation_id: z.string(),
    status: z.literal("PASSED"),
    evidence_pack_sha256: sha,
    memo_sha256: sha,
    markdown_sha256: sha,
    unsupported_numeric_claims: z.array(z.string()),
    unsupported_comparisons: z.array(z.string()),
    unknown_evidence_ids: z.array(z.string()),
    prohibited_causal_claims: z.array(z.string()),
    accounting_complete: z.literal(true),
    created_at: z.string(),
    content_sha256: sha,
  })
  .strict();

export const migrationSchema = z
  .object({
    schema_version: z.string(),
    analysis_id: z.string(),
    status: z.string(),
    lineage: z.record(z.string(), z.unknown()),
    rows: z.array(z.record(z.string(), z.unknown())),
    recommendations: z.array(
      z
        .object({
          profile_id: z.string(),
          eligible_systems: z.array(z.string()),
          ranking: z.array(z.string()),
          recommendation: z.string(),
          reason_code: z.string(),
        })
        .strict(),
    ),
    created_at: z.string(),
    content_sha256: sha,
  })
  .strict();

export const evidenceSchema = z
  .object({
    schema_version: z.string(),
    evidence_pack_id: z.string(),
    status: z.string(),
    protocol_sha256: sha,
    analysis_sha256: sha,
    migration_analysis_sha256: sha,
    case_selection_sha256: sha,
    lineage: z.record(z.string(), z.unknown()),
    references: z.array(
      z
        .object({
          evidence_id: z.string(),
          artifact_path: z.string(),
          artifact_byte_sha256: sha,
          artifact_content_sha256: sha,
          json_path: z.string(),
          value: z.unknown(),
          numerator: z.number().nullable(),
          denominator: z.number().int().nullable(),
          evaluation_surface: z.string(),
          system_id: z.string().nullable(),
        })
        .strict(),
    ),
    restrictions: z.array(z.string()),
    created_at: z.string(),
    content_sha256: sha,
  })
  .strict();

export type Story = z.infer<typeof storySchema>;
export type CaseDetails = z.infer<typeof caseDetailsSchema>;
export type SystemSummary = z.infer<typeof systemSummarySchema>;
export type Memo = z.infer<typeof memoSchema>;
export type Evidence = z.infer<typeof evidenceSchema>;
