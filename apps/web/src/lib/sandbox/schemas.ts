import { z } from "zod";

export const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);
export const jsonValueSchema: z.ZodType<JsonValue> = z.lazy(() =>
  z.union([
    z.null(),
    z.boolean(),
    z.number().finite(),
    z.string(),
    z.array(jsonValueSchema),
    z.record(z.string(), jsonValueSchema),
  ]),
);
export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

const jsonObject = z.record(z.string(), jsonValueSchema);
const nonnegativeInteger = z.number().int().nonnegative();

export const manifestAssetSchema = z.object({
  byte_sha256: sha256Schema,
  bytes: nonnegativeInteger,
  relative_path: z.string().min(1),
});
export const sandboxManifestSchema = z
  .object({
    schema_version: z.literal("inheritbench.sandbox-manifest.v0.1"),
    sandbox_id: z.string().min(1),
    assets: z.array(manifestAssetSchema),
    scenarios: z.array(z.string().min(1)),
    content_sha256: sha256Schema,
    expected_result_content_hashes: z.record(z.string(), sha256Schema),
  })
  .passthrough();

export const comparisonSchema = z.object({
  name: z.string().min(1),
  pointer: z.string().startsWith("/"),
  mode: z.enum(["exact", "list", "set", "numeric"]),
  semantic: z.boolean(),
  tolerance: z.number().nonnegative().nullable().optional(),
});
export const evaluatorConfigSchema = z.object({
  schema_version: z.string().min(1),
  strict_json: z.literal(true),
  whole_output_json_fence: z.boolean(),
  strict_requires_cross_field: z.boolean().default(false),
  required_pointers: z.array(z.string().startsWith("/")),
  ignored_pointers: z.array(z.string().startsWith("/")),
  comparisons: z.array(comparisonSchema).min(1),
  controlled_vocabularies: z.record(z.string(), z.string()),
  operational_fields: z.array(z.string().min(1)).min(1).optional(),
});
export const safetyRuleSchema = z.object({
  code: z.string().min(1),
  severity: z.enum(["info", "warning", "blocker"]),
  message: z.string().min(1),
  when: jsonObject,
});
export const evaluationContractSchema = z.object({
  schema_version: z.string().min(1),
  evaluator: evaluatorConfigSchema,
  schemas: z.object({ output: jsonObject, cross_field: jsonObject }),
  vocabularies: z.record(z.string(), z.array(jsonValueSchema)),
  safety: z.object({ version: z.string(), rules: z.array(safetyRuleSchema) }),
});

export const thresholdSchema = z.object({
  maximum_blocker_safety_findings: nonnegativeInteger.default(0),
  minimum_group_semantic_rate: z.number().default(0),
  minimum_semantic_rate: z.number().default(0),
  minimum_strict_rate: z.number().default(0),
});
export const readinessContractSchema = z
  .object({
    schema_version: z.string().min(1),
    version: z.string().min(1),
    clean: thresholdSchema,
    adversarial: thresholdSchema,
    source_gate: thresholdSchema.optional(),
    accounting: z.record(z.string(), nonnegativeInteger).optional(),
  })
  .passthrough();

export const predictionSchema = z.object({
  record_id: z.string().min(1),
  raw_output: z.string(),
  status: z.enum(["COMPLETED", "FAILED"]),
});
export const scenarioSchema = z.object({
  schema_version: z.string().min(1),
  scenario_id: z.string().min(1),
  display_name: z.string().min(1),
  record_definitions: z.string().min(1),
  predictions: z.record(z.string(), predictionSchema),
  surfaces: z.array(z.string().min(1)).min(1),
  source_run: z.string().min(1),
  system_role: z.string().optional(),
});
export const recordDefinitionSchema = z.object({
  record_id: z.string().min(1),
  surface: z.string().min(1),
  input: jsonObject,
  expected: jsonObject,
  safety_context: jsonObject,
  coverage: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])),
});
export const recordSetSchema = z
  .object({
    schema_version: z.string().min(1),
    record_set_id: z.string().min(1),
    records: z.array(recordDefinitionSchema),
  })
  .passthrough();

export const parserFindingSchema = z.object({
  code: z.enum(["INVALID_JSON", "ROOT_NOT_OBJECT", "SCHEMA_INVALID", "PROSE_OR_MULTIPLE_OBJECTS"]),
  message: z.string(),
});
export const safetyFindingSchema = z.object({
  code: z.string(),
  severity: z.enum(["info", "warning", "blocker"]),
  message: z.string(),
});
export const evaluationResultSchema = z.object({
  schema_version: z.literal("inheritbench.generic-evaluation.v0.2"),
  record_id: z.string(),
  raw_output: z.string(),
  strict_candidate: z.string(),
  normalized_candidate: z.string().nullable(),
  parser_classification: z.enum(["STRICT_VALID", "NORMALIZED_VALID", "UNPARSEABLE"]),
  parse_valid: z.boolean(),
  valid_json: z.boolean(),
  schema_valid: z.boolean(),
  vocabulary_conformant: z.boolean(),
  cross_field_conformant: z.boolean(),
  historical_strict_valid: z.boolean(),
  strict_valid: z.boolean(),
  structural_exact: z.boolean(),
  semantic_match: z.boolean(),
  field_correctness: z.record(z.string(), z.boolean()),
  mean_field_correctness: z.number(),
  parsed_output: jsonObject.nullable(),
  expected: jsonObject,
  parser_findings: z.array(parserFindingSchema),
  safety_findings: z.array(safetyFindingSchema),
  coverage: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])),
  content_sha256: sha256Schema,
});
export const generationEvaluationSchema = z.object({
  surface: z.string(),
  generation: predictionSchema,
  evaluation: evaluationResultSchema,
});

const groupMetricSchema = z.object({
  correct: nonnegativeInteger,
  total: nonnegativeInteger,
  rate: z.number(),
});
export const surfaceSummarySchema = z.object({
  surface: z.string(),
  expected: nonnegativeInteger,
  terminal: nonnegativeInteger,
  semantic_correct: nonnegativeInteger,
  strict_valid: nonnegativeInteger,
  vocabulary_conformant: nonnegativeInteger,
  cross_field_conformant: nonnegativeInteger,
  structural_exact: nonnegativeInteger,
  mean_field_correctness: z.number(),
  blocker_safety_findings: nonnegativeInteger,
  unknown_safety: nonnegativeInteger,
  minimum_group_semantic_rate: z.number(),
  group_semantic: z.record(z.string(), groupMetricSchema),
  operational: z
    .object({
      fields: z.array(z.string()),
      correct: nonnegativeInteger,
      rate: z.number(),
      minimum_group_rate: z.number(),
      groups: z.record(z.string(), groupMetricSchema),
    })
    .optional(),
});
export const readinessReportSchema = z.object({
  schema_version: z.literal("inheritbench.readiness-report.v0.2"),
  run_id: z.string(),
  rule_version: z.string(),
  status: z.enum(["MIGRATION_BLOCKED", "CONDITIONAL_PASS", "PASS"]),
  reason_codes: z.array(z.string()),
  source_gate: surfaceSummarySchema,
  target_baseline: surfaceSummarySchema,
  confirmatory: surfaceSummarySchema,
  adversarial: surfaceSummarySchema,
  supervision: z.record(z.string(), nonnegativeInteger),
  selected_checkpoint_id: z.string(),
  adapter_sha256: sha256Schema,
  content_sha256: sha256Schema,
});

export const parityExpectationsSchema = z
  .object({
    schema_version: z.string(),
    scenarios: z.record(z.string(), jsonObject),
  })
  .passthrough();
export const integrityResultSchema = z.object({
  verified: z.boolean(),
  manifest_hash: sha256Schema.nullable(),
  verified_assets: z.array(z.string()),
  failed_asset: z.string().nullable(),
  expected_hash: sha256Schema.nullable(),
  actual_hash: sha256Schema.nullable(),
  error: z.string().nullable(),
});
export const receiptSchema = z.object({
  schema_version: z.literal("inheritbench.local-verification-receipt.v0.1"),
  created_at: z.string(),
  scenario_id: z.string(),
  input_sha256: sha256Schema,
  integrity: integrityResultSchema,
  readiness_status: z.string().nullable(),
  parity_verified: z.boolean(),
  result_sha256: sha256Schema,
  metadata: jsonObject.optional(),
  receipt_sha256: sha256Schema,
});
export const executionStageSchema = z.enum([
  "INTEGRITY_VERIFIED",
  "SOURCE_GATE_EVALUATED",
  "SCENARIO_EVALUATED",
  "READINESS_DERIVED",
  "PARITY_VALIDATED",
  "COMPLETED",
]);
export const scenarioExecutionSchema = z.object({
  scenario_id: z.string(),
  input_sha256: sha256Schema,
  integrity: integrityResultSchema,
  records: z.object({
    source_gate: z.array(generationEvaluationSchema),
    target_baseline: z.array(generationEvaluationSchema),
    selected: z.array(generationEvaluationSchema),
  }),
  summaries: z.object({
    adapted_source: surfaceSummarySchema,
    target_baseline: surfaceSummarySchema,
    selected: z.record(z.string(), surfaceSummarySchema),
  }),
  readiness: readinessReportSchema.nullable(),
  readiness_eligible: z.boolean(),
  readiness_reason_code: z.string().nullable(),
  parity: z.object({ verified: z.boolean(), mismatches: z.array(z.string()) }),
  stages: z.array(executionStageSchema),
  timing: z.object({
    started_at: z.string(),
    completed_at: z.string(),
    duration_ms: z.number().nonnegative(),
  }),
});

export type SandboxManifest = z.infer<typeof sandboxManifestSchema>;
export type EvaluationContract = z.infer<typeof evaluationContractSchema>;
export type ReadinessContract = z.infer<typeof readinessContractSchema>;
export type Prediction = z.infer<typeof predictionSchema>;
export type Scenario = z.infer<typeof scenarioSchema>;
export type RecordDefinition = z.infer<typeof recordDefinitionSchema>;
export type RecordSet = z.infer<typeof recordSetSchema>;
export type EvaluationResult = z.infer<typeof evaluationResultSchema>;
export type GenerationEvaluation = z.infer<typeof generationEvaluationSchema>;
export type SurfaceSummary = z.infer<typeof surfaceSummarySchema>;
export type ReadinessReport = z.infer<typeof readinessReportSchema>;
export type IntegrityResult = z.infer<typeof integrityResultSchema>;
export type Receipt = z.infer<typeof receiptSchema>;
export type ScenarioExecutionResult = z.infer<typeof scenarioExecutionSchema>;

export interface SandboxAssets {
  manifest: SandboxManifest;
  evaluationContract: EvaluationContract;
  readinessContract: ReadinessContract;
  parityExpectations: z.infer<typeof parityExpectationsSchema>;
  recordSets: Record<string, RecordSet>;
  scenarios: Record<string, Scenario>;
  rawAssets?: Record<string, JsonValue>;
  integrity: IntegrityResult;
}
