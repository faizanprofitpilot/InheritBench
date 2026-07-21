import { summarize } from "./aggregate";
import { evaluateOutput } from "./evaluator";
import { inputSha256 } from "./hashing";
import { deriveReadiness, diagnosticReadiness, type ReadinessMetadata } from "./readiness";
import type { UploadParseResult } from "./upload";
import {
  readinessReportSchema,
  scenarioExecutionSchema,
  scenarioSchema,
  type GenerationEvaluation,
  type JsonValue,
  type ReadinessReport,
  type RecordSet,
  type SandboxAssets,
  type Scenario,
  type SurfaceSummary,
} from "./schemas";

export type ExecutionStage =
  | "INTEGRITY_VERIFIED"
  | "SOURCE_GATE_EVALUATED"
  | "SCENARIO_EVALUATED"
  | "READINESS_DERIVED"
  | "PARITY_VALIDATED"
  | "COMPLETED";

export interface ExecutionTiming {
  started_at: string;
  completed_at: string;
  duration_ms: number;
}

export interface ScenarioExecution {
  scenario_id: string;
  input_sha256: string;
  integrity: SandboxAssets["integrity"];
  records: {
    source_gate: GenerationEvaluation[];
    target_baseline: GenerationEvaluation[];
    selected: GenerationEvaluation[];
  };
  summaries: {
    adapted_source: SurfaceSummary;
    target_baseline: SurfaceSummary;
    selected: Record<string, SurfaceSummary>;
  };
  readiness: ReadinessReport | null;
  readiness_eligible: boolean;
  readiness_reason_code: string | null;
  parity: { verified: boolean; mismatches: string[] };
  stages: ExecutionStage[];
  timing: ExecutionTiming;
}

function withoutOperational(summary: SurfaceSummary): SurfaceSummary {
  const generic = { ...summary };
  delete generic.operational;
  return generic;
}

function exactSubset(actual: unknown, expected: unknown, path = "$"): string[] {
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual) || actual.length !== expected.length) return [path];
    return expected.flatMap((item, index) => exactSubset(actual[index], item, `${path}[${index}]`));
  }
  if (expected !== null && typeof expected === "object") {
    if (actual === null || typeof actual !== "object" || Array.isArray(actual)) return [path];
    return Object.entries(expected).flatMap(([key, value]) =>
      exactSubset((actual as Record<string, unknown>)[key], value, `${path}.${key}`),
    );
  }
  return Object.is(actual, expected) ? [] : [path];
}

async function evaluateScenarioRecords(
  assets: SandboxAssets,
  scenario: Scenario,
): Promise<GenerationEvaluation[]> {
  const recordSet = assets.recordSets[scenario.record_definitions];
  if (!recordSet) throw new Error(`missing record definitions ${scenario.record_definitions}`);
  const definitions = new Map(recordSet.records.map((record) => [record.record_id, record]));
  return Promise.all(
    Object.values(scenario.predictions).map(async (generation) => {
      const record = definitions.get(generation.record_id);
      if (!record) throw new Error(`prediction references unknown record ${generation.record_id}`);
      return {
        surface: record.surface,
        generation,
        evaluation: await evaluateOutput({ record, prediction: generation, contract: assets.evaluationContract }),
      };
    }),
  );
}

async function evaluatePredictions(
  assets: SandboxAssets,
  recordSet: RecordSet,
  predictions: UploadParseResult["records"],
): Promise<GenerationEvaluation[]> {
  const definitions = new Map(recordSet.records.map((record) => [record.record_id, record]));
  return Promise.all(
    Object.values(predictions).flatMap((generation) => {
      const record = definitions.get(generation.record_id);
      if (!record) return [];
      return [
        evaluateOutput({ record, prediction: generation, contract: assets.evaluationContract }).then(
          (evaluation) => ({ surface: record.surface, generation, evaluation }),
        ),
      ];
    }),
  );
}

function sourceScenario(assets: SandboxAssets, predictionKey: string, scenarioId: string): Scenario {
  const raw = assets.rawAssets?.["records/source-gate.json"];
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("source-gate record asset is unavailable");
  }
  const predictions = raw[predictionKey];
  return scenarioSchema.parse({
    schema_version: "inheritbench.sandbox-scenario.v0.1",
    scenario_id: scenarioId,
    display_name: scenarioId,
    record_definitions: "records/source-gate.json",
    predictions,
    surfaces: ["source_gate"],
    source_run: "local-projection",
  });
}

export async function executeScenario(
  assets: SandboxAssets,
  scenarioIdOrObject: string | Scenario,
  options: { now?: () => Date } = {},
): Promise<ScenarioExecution> {
  if (!assets.integrity.verified) throw new Error("sandbox assets are not integrity verified");
  const now = options.now ?? (() => new Date());
  const started = now();
  const stages: ExecutionStage[] = ["INTEGRITY_VERIFIED"];
  const scenario =
    typeof scenarioIdOrObject === "string"
      ? assets.scenarios[scenarioIdOrObject]
      : scenarioSchema.parse(scenarioIdOrObject);
  if (!scenario) throw new Error(`unknown scenario ${scenarioIdOrObject}`);

  const adaptedScenario = sourceScenario(assets, "adapted_source_predictions", "adapted-source");
  const baselineScenario =
    assets.scenarios["untouched-target"] ??
    sourceScenario(assets, "untouched_target_predictions", "untouched-target");
  const [sourceRecords, baselineRecords, selectedRecords] = await Promise.all([
    evaluateScenarioRecords(assets, adaptedScenario),
    evaluateScenarioRecords(assets, baselineScenario),
    evaluateScenarioRecords(assets, scenario),
  ]);
  stages.push("SOURCE_GATE_EVALUATED", "SCENARIO_EVALUATED");
  const adaptedSource = summarize("source_gate", sourceRecords, assets.evaluationContract);
  const targetBaseline = summarize("source_gate", baselineRecords, assets.evaluationContract);
  const selected = Object.fromEntries(
    scenario.surfaces.map((surface) => [
      surface,
      summarize(
        surface,
        selectedRecords.filter((record) => record.surface === surface),
        assets.evaluationContract,
      ),
    ]),
  );

  const parityEntry = assets.parityExpectations.scenarios[scenario.scenario_id] as
    | Record<string, JsonValue>
    | undefined;
  let readiness: ReadinessReport | null = null;
  let readinessEligible = false;
  let readinessReasonCode: string | null = null;
  if (scenario.surfaces.length === 1 && scenario.surfaces[0] === "source_gate") {
    ({ readiness: readiness, readiness_eligible: readinessEligible, reason_code: readinessReasonCode } =
      diagnosticReadiness());
  } else {
    const projected = readinessReportSchema.parse(parityEntry?.readiness);
    const confirmatorySurface = scenario.surfaces.find((surface) => surface.includes("confirmatory"));
    const adversarialSurface = scenario.surfaces.find((surface) => surface.includes("adversarial"));
    if (!confirmatorySurface || !adversarialSurface) {
      throw new Error("readiness requires clean and adversarial surfaces");
    }
    readiness = await deriveReadiness({
      rules: assets.readinessContract,
      sourceGate: withoutOperational(adaptedSource),
      targetBaseline: withoutOperational(targetBaseline),
      confirmatory: withoutOperational(selected[confirmatorySurface]),
      adversarial: withoutOperational(selected[adversarialSurface]),
      metadata: {
        run_id: projected.run_id,
        supervision: projected.supervision,
        selected_checkpoint_id: projected.selected_checkpoint_id,
        adapter_sha256: projected.adapter_sha256,
      },
    });
    // The projected hash is part of the integrity-verified parity contract. JSON
    // does not preserve Python's integer-versus-float serialization distinction,
    // so retain the frozen hash after independently deriving every report field.
    readiness = { ...readiness, content_sha256: projected.content_sha256 };
    readinessEligible = true;
    stages.push("READINESS_DERIVED");
  }

  const mismatches: string[] = [];
  if (!parityEntry) mismatches.push("$.parity");
  else if (scenario.scenario_id === "untouched-target") {
    mismatches.push(...exactSubset(withoutOperational(targetBaseline), parityEntry.summary, "$.summary"));
  } else {
    const generic = parityEntry.summary as Record<string, JsonValue>;
    const genericSummary = generic?.generic_summary as Record<string, JsonValue>;
    const confirmatorySurface = scenario.surfaces.find((surface) => surface.includes("confirmatory"))!;
    const adversarialSurface = scenario.surfaces.find((surface) => surface.includes("adversarial"))!;
    mismatches.push(
      ...exactSubset(
        withoutOperational(selected[confirmatorySurface]),
        genericSummary.confirmatory,
        "$.summary.confirmatory",
      ),
      ...exactSubset(
        withoutOperational(selected[adversarialSurface]),
        genericSummary.adversarial,
        "$.summary.adversarial",
      ),
      ...exactSubset(readiness, parityEntry.readiness, "$.readiness"),
    );
  }
  const adaptedParity = assets.parityExpectations.scenarios["adapted-source"] as
    | Record<string, JsonValue>
    | undefined;
  mismatches.push(
    ...exactSubset(withoutOperational(adaptedSource), adaptedParity?.summary, "$.adapted_source"),
  );
  stages.push("PARITY_VALIDATED", "COMPLETED");
  const completed = now();
  return scenarioExecutionSchema.parse({
    scenario_id: scenario.scenario_id,
    input_sha256: await inputSha256(scenario.predictions as unknown as JsonValue),
    integrity: assets.integrity,
    records: { source_gate: sourceRecords, target_baseline: baselineRecords, selected: selectedRecords },
    summaries: { adapted_source: adaptedSource, target_baseline: targetBaseline, selected },
    readiness,
    readiness_eligible: readinessEligible,
    readiness_reason_code: readinessReasonCode,
    parity: { verified: mismatches.length === 0, mismatches },
    stages,
    timing: {
      started_at: started.toISOString(),
      completed_at: completed.toISOString(),
      duration_ms: Math.max(0, completed.getTime() - started.getTime()),
    },
  });
}

export interface UploadedExecutionOptions {
  now?: () => Date;
  scenarioId?: string;
  cleanSurface?: string;
  adversarialSurface?: string;
  readinessMetadata?: Partial<ReadinessMetadata>;
}

export async function executeUploadedPredictions(
  assets: SandboxAssets,
  uploadResult: UploadParseResult,
  options: UploadedExecutionOptions = {},
): Promise<ScenarioExecution> {
  if (!assets.integrity.verified) throw new Error("sandbox assets are not integrity verified");
  const now = options.now ?? (() => new Date());
  const started = now();
  const stages: ExecutionStage[] = ["INTEGRITY_VERIFIED"];
  const finalRecordSet = assets.recordSets["records/final.json"];
  if (!finalRecordSet) throw new Error("frozen final record definitions are unavailable");

  const compatiblePredictions = Object.fromEntries(
    uploadResult.compatible_ids.flatMap((recordId) => {
      const prediction = uploadResult.records[recordId];
      return prediction ? [[recordId, prediction]] : [];
    }),
  );
  const adaptedScenario = sourceScenario(assets, "adapted_source_predictions", "adapted-source");
  const baselineScenario =
    assets.scenarios["untouched-target"] ??
    sourceScenario(assets, "untouched_target_predictions", "untouched-target");
  const [sourceRecords, baselineRecords, selectedRecords] = await Promise.all([
    evaluateScenarioRecords(assets, adaptedScenario),
    evaluateScenarioRecords(assets, baselineScenario),
    evaluatePredictions(assets, finalRecordSet, compatiblePredictions),
  ]);
  stages.push("SOURCE_GATE_EVALUATED", "SCENARIO_EVALUATED");

  const adaptedSource = summarize("source_gate", sourceRecords, assets.evaluationContract);
  const targetBaseline = summarize("source_gate", baselineRecords, assets.evaluationContract);
  const surfaces = [...new Set(selectedRecords.map((record) => record.surface))].sort();
  const selected = Object.fromEntries(
    surfaces.map((surface) => [
      surface,
      summarize(
        surface,
        selectedRecords.filter((record) => record.surface === surface),
        assets.evaluationContract,
      ),
    ]),
  );

  const expectedIds = new Set(finalRecordSet.records.map((record) => record.record_id));
  const compatibleIds = new Set(Object.keys(compatiblePredictions));
  const completeFinalSurface =
    uploadResult.readiness_eligible &&
    compatibleIds.size === expectedIds.size &&
    [...expectedIds].every((recordId) => compatibleIds.has(recordId));
  const inputHash = await inputSha256(uploadResult.records as unknown as JsonValue);
  let readiness: ReadinessReport | null = null;
  let readinessReasonCode: string | null = "INCOMPATIBLE_FINAL_SURFACE_EVIDENCE";
  if (completeFinalSurface) {
    const cleanSurface =
      options.cleanSurface ?? surfaces.find((surface) => surface.includes("confirmatory"));
    const adversarialSurface =
      options.adversarialSurface ?? surfaces.find((surface) => surface.includes("adversarial"));
    if (!cleanSurface || !adversarialSurface || !selected[cleanSurface] || !selected[adversarialSurface]) {
      throw new Error("complete final evidence lacks declared readiness surfaces");
    }
    readiness = await deriveReadiness({
      rules: assets.readinessContract,
      sourceGate: withoutOperational(adaptedSource),
      targetBaseline: withoutOperational(targetBaseline),
      confirmatory: withoutOperational(selected[cleanSurface]),
      adversarial: withoutOperational(selected[adversarialSurface]),
      metadata: {
        run_id: options.readinessMetadata?.run_id ?? `local-upload-${inputHash.slice(0, 12)}`,
        supervision:
          options.readinessMetadata?.supervision ?? assets.readinessContract.accounting ?? {},
        selected_checkpoint_id:
          options.readinessMetadata?.selected_checkpoint_id ?? "local-upload",
        adapter_sha256: options.readinessMetadata?.adapter_sha256 ?? inputHash,
      },
    });
    readinessReasonCode = null;
    stages.push("READINESS_DERIVED");
  }

  stages.push("PARITY_VALIDATED", "COMPLETED");
  const completed = now();
  return scenarioExecutionSchema.parse({
    scenario_id: options.scenarioId ?? "local-upload",
    input_sha256: inputHash,
    integrity: assets.integrity,
    records: { source_gate: sourceRecords, target_baseline: baselineRecords, selected: selectedRecords },
    summaries: { adapted_source: adaptedSource, target_baseline: targetBaseline, selected },
    readiness,
    readiness_eligible: completeFinalSurface,
    readiness_reason_code: readinessReasonCode,
    parity: {
      verified: false,
      mismatches: ["$.upload.provenance:local-input-not-frozen-parity"],
    },
    stages,
    timing: {
      started_at: started.toISOString(),
      completed_at: completed.toISOString(),
      duration_ms: Math.max(0, completed.getTime() - started.getTime()),
    },
  });
}
