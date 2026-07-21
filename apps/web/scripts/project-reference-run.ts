import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { parse as parseYaml } from "yaml";

const appRoot = process.cwd();
const repositoryRoot = path.resolve(appRoot, "../..");
const sourceRoot = path.join(
  repositoryRoot,
  "runs/reference/anchored-multistart-repaired-ebf2997799a62800",
);
const destinationRoot = path.join(
  repositoryRoot,
  "artifacts/product/reference-succession-v0.1",
);
const sandboxRoot = path.join(destinationRoot, "sandbox");
const successionRunId =
  "succession-opsroute-anchored-behavioral-transfer-v0.1-00-ee7a07404b124c1b";
const successionRunRoot = path.join(repositoryRoot, "runs/reference", successionRunId);
const capabilityRoot = path.join(repositoryRoot, "capabilities/opsroute/v0.2.0");
const finalSurfaceRoot = path.join(
  repositoryRoot,
  "capabilities/opsroute/v0.3.0/evaluation",
);
const generatorVersion = "inheritbench.sandbox-projection.v0.1";
const selectedFiles = [
  "web_bundle.json",
  "canonical_plan.json",
  "multistart_candidate_ranking.json",
  "repair_execution_report.json",
  "guard_repair_lineage.json",
  "evidence_manifest.json",
  "replay_manifest.json",
] as const;

function sha256(payload: Buffer | string): string {
  return createHash("sha256").update(payload).digest("hex");
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

type JsonObject = Record<string, unknown>;

async function json(relativePath: string, root = repositoryRoot): Promise<JsonObject> {
  return JSON.parse(await readFile(path.join(root, relativePath), "utf8")) as JsonObject;
}

async function jsonl(relativePath: string, root = repositoryRoot): Promise<JsonObject[]> {
  return (await readFile(path.join(root, relativePath), "utf8"))
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line) as JsonObject);
}

async function yaml(relativePath: string): Promise<JsonObject> {
  return parseYaml(await readFile(path.join(capabilityRoot, relativePath), "utf8")) as JsonObject;
}

function keyed<T extends JsonObject>(rows: T[]): Map<string, T> {
  return new Map(rows.map((row) => [String(row.record_id), row]));
}

function prediction(record: JsonObject): JsonObject {
  const generation = record.generation as JsonObject;
  return {
    record_id: String(generation.record_id),
    raw_output: generation.raw_output,
    status: generation.status,
  };
}

function predictions(records: JsonObject[]): JsonObject {
  return Object.fromEntries(
    records
      .map(prediction)
      .sort((left, right) => String(left.record_id).localeCompare(String(right.record_id)))
      .map((item) => [String(item.record_id), item]),
  );
}

function recordDefinition(input: JsonObject, oracle: JsonObject): JsonObject {
  if (input.record_id !== oracle.record_id) {
    throw new Error(`input/oracle record mismatch: ${String(input.record_id)}`);
  }
  return {
    record_id: input.record_id,
    surface: input.surface,
    input: input.payload,
    expected: oracle.expected,
    safety_context: oracle.safety_context,
    coverage: oracle.coverage,
  };
}

async function definitions(
  inputPath: string,
  oraclePath: string,
  root: string,
): Promise<JsonObject[]> {
  const inputs = await jsonl(inputPath, root);
  const oracles = keyed(await jsonl(oraclePath, root));
  return inputs
    .map((input) => {
      const oracle = oracles.get(String(input.record_id));
      if (!oracle) throw new Error(`missing oracle: ${String(input.record_id)}`);
      return recordDefinition(input, oracle);
    })
    .sort((left, right) => String(left.record_id).localeCompare(String(right.record_id)));
}

async function atomicScenario(
  scenarioId: string,
  displayName: string,
  evaluationRoot: string,
): Promise<{ scenario: JsonObject; records: JsonObject[] }> {
  const confirmatory = await jsonl(
    `${evaluationRoot}/confirmatory.atomic-results.jsonl`,
    sourceRoot,
  );
  const adversarial = await jsonl(
    `${evaluationRoot}/adversarial.atomic-results.jsonl`,
    sourceRoot,
  );
  const records = [...confirmatory, ...adversarial];
  return {
    scenario: {
      schema_version: "inheritbench.sandbox-scenario.v0.1",
      scenario_id: scenarioId,
      display_name: displayName,
      source_run: path.basename(sourceRoot),
      record_definitions: "records/final.json",
      surfaces: ["final_confirmatory_v0.3", "final_adversarial_v0.3"],
      predictions: predictions(records),
    },
    records,
  };
}

async function writeAsset(
  relativePath: string,
  value: unknown,
): Promise<{ relative_path: string; byte_sha256: string; bytes: number }> {
  const payload = Buffer.from(`${canonical(value)}\n`);
  const destination = path.join(sandboxRoot, relativePath);
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, payload);
  return { relative_path: relativePath, byte_sha256: sha256(payload), bytes: payload.length };
}

await rm(destinationRoot, { recursive: true, force: true });
await mkdir(destinationRoot, { recursive: true });

const files = [];
for (const relativePath of selectedFiles) {
  const payload = await readFile(path.join(sourceRoot, relativePath));
  await writeFile(path.join(destinationRoot, relativePath), payload);
  files.push({
    relative_path: relativePath,
    byte_sha256: sha256(payload),
    bytes: payload.length,
  });
}

const capability = await yaml("capability.yaml");
const evaluator = await yaml("evaluator.yaml");
const readiness = await yaml("rules/readiness.yaml");
const safety = await yaml("rules/safety.yaml");
const outputSchema = await json("schemas/output.schema.json", capabilityRoot);
const crossFieldSchema = await json("schemas/cross-field.schema.json", capabilityRoot);
const vocabularies = {
  decisions: await json("vocabularies/decisions.json", capabilityRoot),
  tools: await json("vocabularies/tools.json", capabilityRoot),
  reason_codes: await json("vocabularies/reason_codes.json", capabilityRoot),
  policy_codes: await json("vocabularies/policy_codes.json", capabilityRoot),
};
const capabilityMetadata = capability.capability as JsonObject;
const capabilityDefinition = {
  schema_version: "inheritbench.sandbox-capability-definition.v0.1",
  capability_id: capabilityMetadata.id,
  capability_version: capabilityMetadata.version,
  status: capabilityMetadata.status,
  profile: capabilityMetadata.profile,
  display_name: "OpsRoute",
  display_description: "Enterprise action routing for refunds and subscriptions.",
};
const evaluationContract = {
  schema_version: "inheritbench.sandbox-evaluation-contract.v0.1",
  evaluator,
  schemas: { output: outputSchema, cross_field: crossFieldSchema },
  vocabularies,
  safety,
};
const readinessContract = {
  schema_version: "inheritbench.sandbox-readiness-contract.v0.1",
  ...readiness,
};
const contractHash = sha256(canonical({ evaluationContract, readinessContract }));

const sourceStage = await json("stages/03-source_gate_completed/stage.json", successionRunRoot);
const targetStage = await json("stages/04-target_baseline_completed/stage.json", successionRunRoot);
const sourceRecords = ((sourceStage.payload as JsonObject).records ?? []) as JsonObject[];
const targetRecords = ((targetStage.payload as JsonObject).records ?? []) as JsonObject[];
const sourceGateDefinitions = await definitions(
  "data/source_gate.inputs.jsonl",
  "oracles/source_gate.jsonl",
  capabilityRoot,
);
const finalDefinitions = [
  ...(await definitions(
    "confirmatory.inputs.jsonl",
    "confirmatory.oracles.jsonl",
    finalSurfaceRoot,
  )),
  ...(await definitions(
    "adversarial.inputs.jsonl",
    "adversarial.oracles.jsonl",
    finalSurfaceRoot,
  )),
].sort((left, right) => String(left.record_id).localeCompare(String(right.record_id)));

const sourceGateIds = new Set(sourceGateDefinitions.map((record) => record.record_id));
for (const record of [...sourceRecords, ...targetRecords]) {
  if (!sourceGateIds.has((record.evaluation as JsonObject).record_id)) {
    throw new Error(`source-gate record is not in frozen definitions`);
  }
}
const untouchedTarget = {
  schema_version: "inheritbench.sandbox-scenario.v0.1",
  scenario_id: "untouched-target",
  display_name: "Untouched target",
  source_run: successionRunId,
  system_role: "target_base",
  record_definitions: "records/source-gate.json",
  surfaces: ["source_gate"],
  predictions: predictions(targetRecords),
};
const direct = await atomicScenario("direct-recovery", "Direct recovery", "direct_final_evaluation");
const anchored = await atomicScenario(
  "anchored-successor",
  "Anchored successor",
  "anchored_final_evaluation",
);
const finalIds = new Set(finalDefinitions.map((record) => record.record_id));
for (const record of [...direct.records, ...anchored.records]) {
  if (!finalIds.has((record.evaluation as JsonObject).record_id)) {
    throw new Error(`final atomic record is not in frozen definitions`);
  }
}

const directSummary = await json("direct_final_evaluation/evaluation_summary.json", sourceRoot);
const anchoredSummary = await json("anchored_final_evaluation/evaluation_summary.json", sourceRoot);
const directReadiness = await json("direct_final_evaluation/readiness_report.json", sourceRoot);
const anchoredReadiness = await json("readiness_report.json", sourceRoot);
const sourceSummary = (sourceStage.payload as JsonObject).summary;
const targetSummary = (targetStage.payload as JsonObject).summary;
const parityExpectations = {
  schema_version: "inheritbench.sandbox-parity-expectations.v0.1",
  source: "frozen Python evaluation summaries and readiness reports",
  scenarios: {
    "untouched-target": { summary: targetSummary },
    "adapted-source": { summary: sourceSummary },
    "direct-recovery": {
      summary: directSummary,
      readiness: directReadiness,
    },
    "anchored-successor": {
      summary: anchoredSummary,
      readiness: anchoredReadiness,
    },
  },
};
const samplePredictions = {
  schema_version: "inheritbench.sandbox-sample-predictions.v0.1",
  samples: [untouchedTarget, direct.scenario, anchored.scenario].map((scenario) => {
    const scenarioPredictions = scenario.predictions as JsonObject;
    const recordId = Object.keys(scenarioPredictions).sort()[0];
    return { scenario_id: scenario.scenario_id, prediction: scenarioPredictions[recordId] };
  }),
};
const sourceGateRecords = {
  schema_version: "inheritbench.sandbox-record-definitions.v0.1",
  record_set_id: "opsroute-source-gate-v0.2",
  records: sourceGateDefinitions,
  adapted_source_predictions: predictions(sourceRecords),
  untouched_target_predictions: predictions(targetRecords),
};
const finalRecords = {
  schema_version: "inheritbench.sandbox-record-definitions.v0.1",
  record_set_id: "opsroute-final-surfaces-v0.3",
  records: finalDefinitions,
};

const sandboxAssets = [];
for (const [relativePath, value] of [
  ["capability-definition.json", capabilityDefinition],
  ["evaluation-contract.json", evaluationContract],
  ["readiness-contract.json", readinessContract],
  ["records/source-gate.json", sourceGateRecords],
  ["records/final.json", finalRecords],
  ["scenarios/untouched-target.json", untouchedTarget],
  ["scenarios/direct-recovery.json", direct.scenario],
  ["scenarios/anchored-successor.json", anchored.scenario],
  ["parity-expectations.json", parityExpectations],
  ["sample-predictions.json", samplePredictions],
] as Array<[string, unknown]>) {
  sandboxAssets.push(await writeAsset(relativePath, value));
}
const repairLineage = await json("guard_repair_lineage.json", sourceRoot);
const sandboxManifest: JsonObject = {
  schema_version: "inheritbench.sandbox-manifest.v0.1",
  sandbox_id: "reference-succession-sandbox-v0.1",
  capability: {
    id: capabilityMetadata.id,
    version: capabilityMetadata.version,
    final_surface_version: "opsroute-final-surfaces-v0.3",
  },
  source_runs: {
    succession: successionRunId,
    recovery: path.basename(sourceRoot),
  },
  scenarios: ["untouched-target", "direct-recovery", "anchored-successor"],
  evaluator_version: evaluator.schema_version,
  readiness_contract_version: readiness.version,
  safety_contract_version: safety.version,
  contract_sha256: contractHash,
  record_counts: {
    source_gate: sourceGateDefinitions.length,
    final_confirmatory: finalDefinitions.filter(
      (record) => record.surface === "final_confirmatory_v0.3",
    ).length,
    final_adversarial: finalDefinitions.filter(
      (record) => record.surface === "final_adversarial_v0.3",
    ).length,
    predictions: {
      adapted_source: sourceRecords.length,
      untouched_target: targetRecords.length,
      direct_recovery: direct.records.length,
      anchored_successor: anchored.records.length,
    },
  },
  assets: sandboxAssets.sort((left, right) =>
    left.relative_path.localeCompare(right.relative_path),
  ),
  expected_result_content_hashes: {
    adapted_source_summary: sha256(canonical(sourceSummary)),
    untouched_target_summary: sha256(canonical(targetSummary)),
    direct_summary: sha256(canonical(directSummary)),
    direct_readiness: directReadiness.content_sha256,
    anchored_summary: sha256(canonical(anchoredSummary)),
    anchored_readiness: anchoredReadiness.content_sha256,
  },
  generator_version: generatorVersion,
  projected_at: repairLineage.created_at,
};
sandboxManifest.content_sha256 = sha256(canonical(sandboxManifest));
const sandboxManifestEntry = await writeAsset("sandbox-manifest.json", sandboxManifest);
files.push(
  ...sandboxAssets.map((entry) => ({
    ...entry,
    relative_path: `sandbox/${entry.relative_path}`,
  })),
  { ...sandboxManifestEntry, relative_path: "sandbox/sandbox-manifest.json" },
);

const manifest: Record<string, unknown> = {
  schema_version: "inheritbench.reference-succession-projection.v0.1",
  projection_id: "reference-succession-v0.1",
  source_run: "anchored-multistart-repaired-ebf2997799a62800",
  files,
};
manifest.content_sha256 = sha256(canonical(manifest));
await writeFile(path.join(destinationRoot, "manifest.json"), `${canonical(manifest)}\n`);
console.log(
  `Projected ${files.length} verified reference-run artifacts (${sandboxAssets.length + 1} sandbox files).`,
);
