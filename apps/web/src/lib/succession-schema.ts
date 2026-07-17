import { z } from "zod";

export const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

const artifactReferenceSchema = z
  .object({
    relative_path: z.string().min(1),
    byte_sha256: sha256Schema,
    content_sha256: sha256Schema.nullable(),
    bytes: z.number().int().nonnegative(),
  })
  .strict();

const adapterIdentitySchema = z
  .object({
    adapter_id: z.literal("target_hybrid_anchored_distillation_10-7461072c83b4dcde"),
    base_model_id: z.literal("allenai/OLMo-2-0425-1B-Instruct"),
    base_model_revision: z.string().regex(/^[0-9a-f]{40}$/),
    release_tag: z.literal("phase3b-anchored-v0.1.0"),
    release_commit: z.string().regex(/^[0-9a-f]{40}$/),
    archive_name: z.literal(
      "target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip",
    ),
    archive_sha256: sha256Schema,
    archive_bytes: z.number().int().positive(),
    adapter_file_sha256s: z.record(z.string(), sha256Schema),
    release_url: z.url().startsWith(
      "https://github.com/faizanprofitpilot/InheritBench/releases/download/",
    ),
    publication_status: z.literal("PUBLISHED_VERIFIED"),
    anonymous_download_verified: z.literal(true),
    publication_content_sha256: sha256Schema,
  })
  .strict();

export const operationOrder = [
  "configuration_validated",
  "frozen_evidence_located",
  "manifest_identity_verified",
  "replay_records_loaded",
  "metrics_aggregated",
  "residual_failures_classified",
  "readiness_rules_applied",
  "adapter_identity_confirmed",
  "readiness_report_generated",
] as const;

export const successionManifestSchema = z
  .object({
    schema_version: z.literal("succession-run-manifest-v0.1"),
    run_id: z.string().min(1),
    case_id: z.literal("opsroute-qwen-olmo"),
    status: z.literal("FROZEN"),
    capability_pack_path: z.literal("capabilities/opsroute/v0.1.0/capability.yaml"),
    capability_pack_sha256: sha256Schema,
    configuration: z.record(z.string(), z.union([z.string(), z.number().int()])),
    schema_versions: z.record(z.string(), z.string()),
    source_artifacts: z.array(artifactReferenceSchema).min(6),
    replay_records: artifactReferenceSchema,
    replay_context: artifactReferenceSchema,
    operation_order: z.tuple([
      z.literal("configuration_validated"),
      z.literal("frozen_evidence_located"),
      z.literal("manifest_identity_verified"),
      z.literal("replay_records_loaded"),
      z.literal("metrics_aggregated"),
      z.literal("residual_failures_classified"),
      z.literal("readiness_rules_applied"),
      z.literal("adapter_identity_confirmed"),
      z.literal("readiness_report_generated"),
    ]),
    readiness_rule_version: z.literal("succession-readiness-v0.1"),
    adapter: adapterIdentitySchema,
    content_sha256: sha256Schema,
  })
  .strict();

const actionContractSchema = z
  .object({
    decision: z.enum([
      "execute",
      "request_approval",
      "ask_clarification",
      "refuse",
      "no_action",
    ]),
    tool: z
      .enum([
        "refund_payment",
        "escalate_fraud_review",
        "cancel_subscription",
        "pause_subscription",
        "offer_retention",
      ])
      .nullable(),
    arguments: z.record(
      z.string(),
      z.union([z.string(), z.number(), z.boolean(), z.null()]),
    ),
    approval_required: z.boolean(),
    policy_code: z.string().min(1),
    reason_code: z.string().min(1),
  })
  .strict();

const nullableSafety = z.boolean().nullable();
const atomicMetricsSchema = z
  .object({
    valid_json: z.boolean(),
    schema_valid: z.boolean(),
    strict_contract_score_v0: z.union([z.literal(0), z.literal(1)]),
    semantic_decision_score_v0: z.union([z.literal(0), z.literal(1)]),
    decision_correct: z.boolean(),
    tool_correct: z.boolean(),
    arguments_exact: z.boolean(),
    argument_precision: z.number().min(0).max(1),
    argument_recall: z.number().min(0).max(1),
    argument_f1: z.number().min(0).max(1),
    required_argument_completeness: z.number().min(0).max(1),
    approval_correct: z.boolean(),
    policy_code_correct: z.boolean(),
    reason_code_correct: z.boolean(),
    false_action: nullableSafety,
    approval_bypass: nullableSafety,
    unauthorized_action: nullableSafety,
    hallucinated_arguments: nullableSafety,
    safety_unknown_due_to_parse_failure: z.boolean(),
  })
  .strict();

export const replayRecordSchema = z
  .object({
    schema_version: z.literal("succession-replay-record-v0.1"),
    surface: z.enum(["confirmatory", "adversarial"]),
    system_id: z.enum([
      "target_untouched",
      "target_hybrid_anchored_distillation_10",
    ]),
    example_id: z.string().min(1),
    scenario_family: z.string().min(1),
    archetype: z.string().min(1),
    status: z.literal("COMPLETED"),
    parser_classification: z.enum([
      "STRICT_VALID",
      "NORMALIZED_VALID",
      "UNPARSEABLE",
    ]),
    expected_contract: actionContractSchema,
    validated_contract: actionContractSchema.nullable(),
    metrics: atomicMetricsSchema,
    adversarial_profiles: z.array(z.string()),
    latency_ms: z.number().int().nonnegative(),
    source_prediction_id: z.string().min(1),
    source_prediction_content_sha256: sha256Schema,
  })
  .strict();

export const replayContextSchema = z
  .object({
    schema_version: z.literal("succession-replay-context-v0.1"),
    label_accounting: z.record(z.string(), z.number().int().nonnegative()),
    compute_accounting: z.record(z.string(), z.number().nonnegative()),
    profile_id: z.literal("maximum_confirmed_capability"),
    profile_recommendation: z.literal("target_hybrid_anchored_distillation_10"),
    profile_source_sha256: sha256Schema,
    memo_kind: z.literal("GPT_5_6_SOL"),
    memo_validation_status: z.literal("PASSED"),
    memo_sha256: sha256Schema,
    memo_validation_sha256: sha256Schema,
    content_sha256: sha256Schema,
  })
  .strict();

export type SuccessionManifest = z.infer<typeof successionManifestSchema>;
export type ReplayRecord = z.infer<typeof replayRecordSchema>;
export type ReplayContext = z.infer<typeof replayContextSchema>;
export type AdapterIdentity = z.infer<typeof adapterIdentitySchema>;
