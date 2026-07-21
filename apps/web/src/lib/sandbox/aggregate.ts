import {
  surfaceSummarySchema,
  type EvaluationContract,
  type GenerationEvaluation,
  type SurfaceSummary,
} from "./schemas";

export function summarize(
  surface: string,
  records: GenerationEvaluation[],
  contract?: EvaluationContract,
): SurfaceSummary {
  const groups = new Map<string, [number, number]>();
  const operationalGroups = new Map<string, [number, number]>();
  const semanticFields = contract?.evaluator.comparisons
    .filter((comparison) => comparison.semantic)
    .map((comparison) => comparison.name) ?? [];
  const operationalFields = contract?.evaluator.operational_fields ?? semanticFields;
  let semantic = 0;
  let strict = 0;
  let vocabulary = 0;
  let crossField = 0;
  let structural = 0;
  let blockers = 0;
  let unknown = 0;
  let fieldTotal = 0;
  let operationalCorrect = 0;

  for (const record of records) {
    const evaluation = record.evaluation;
    semantic += Number(evaluation.semantic_match);
    strict += Number(evaluation.strict_valid);
    vocabulary += Number(evaluation.vocabulary_conformant);
    crossField += Number(evaluation.cross_field_conformant);
    structural += Number(evaluation.structural_exact);
    fieldTotal += evaluation.mean_field_correctness;
    blockers += evaluation.safety_findings.filter((finding) => finding.severity === "blocker").length;
    unknown += Number(record.generation.status !== "COMPLETED");
    const group = String(
      evaluation.coverage.group ??
        evaluation.coverage.archetype ??
        evaluation.coverage.family ??
        "all",
    );
    const counts = groups.get(group) ?? [0, 0];
    counts[0] += Number(evaluation.semantic_match);
    counts[1] += 1;
    groups.set(group, counts);
    const operationalMatch =
      operationalFields.length > 0 &&
      operationalFields.every((field) => evaluation.field_correctness[field] === true);
    operationalCorrect += Number(operationalMatch);
    const operationalCounts = operationalGroups.get(group) ?? [0, 0];
    operationalCounts[0] += Number(operationalMatch);
    operationalCounts[1] += 1;
    operationalGroups.set(group, operationalCounts);
  }

  const groupSemantic = Object.fromEntries(
    [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([group, [correct, total]]) => [group, { correct, total, rate: total ? correct / total : 0 }]),
  );
  const operationalGroupMetrics = Object.fromEntries(
    [...operationalGroups.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([group, [correct, total]]) => [group, { correct, total, rate: total ? correct / total : 0 }]),
  );
  const minimum = Math.min(
    ...Object.values(groupSemantic).map((value) => value.rate),
    ...(Object.keys(groupSemantic).length ? [] : [0]),
  );
  const operationalMinimum = Math.min(
    ...Object.values(operationalGroupMetrics).map((value) => value.rate),
    ...(Object.keys(operationalGroupMetrics).length ? [] : [0]),
  );
  return surfaceSummarySchema.parse({
    surface,
    expected: records.length,
    terminal: records.filter((record) => ["COMPLETED", "FAILED"].includes(record.generation.status)).length,
    semantic_correct: semantic,
    strict_valid: strict,
    vocabulary_conformant: vocabulary,
    cross_field_conformant: crossField,
    structural_exact: structural,
    mean_field_correctness: records.length ? fieldTotal / records.length : 0,
    blocker_safety_findings: blockers,
    unknown_safety: unknown,
    minimum_group_semantic_rate: minimum,
    group_semantic: groupSemantic,
    operational: {
      fields: operationalFields,
      correct: operationalCorrect,
      rate: records.length ? operationalCorrect / records.length : 0,
      minimum_group_rate: operationalMinimum,
      groups: operationalGroupMetrics,
    },
  });
}
