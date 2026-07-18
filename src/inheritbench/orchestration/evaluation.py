"""Generic generation evaluation, aggregation and checkpoint ranking."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.capability.evaluator import evaluate_output
from inheritbench.capability.loader import LoadedCapabilityPack
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    CapabilityOracleRecord,
    CheckpointPolicy,
)
from inheritbench.config import ModelConfig
from inheritbench.model_adapters.base import ModelAdapter
from inheritbench.model_adapters.schemas import (
    CheckpointArtifact,
    GenerationOutput,
    ModelRuntimeIdentity,
)
from inheritbench.orchestration.schemas import (
    CheckpointDecision,
    CheckpointScore,
    EvaluationRecord,
    SurfaceSummary,
)


def evaluate_generations(
    *,
    pack: LoadedCapabilityPack,
    surface: str,
    system_role: str,
    checkpoint_id: str | None,
    model: ModelRuntimeIdentity,
    inputs: list[CapabilityInputRecord],
    oracles: list[CapabilityOracleRecord],
    generations: list[GenerationOutput],
) -> list[EvaluationRecord]:
    oracle_map = {record.record_id: record for record in oracles}
    generation_map = {record.record_id: record for record in generations}
    records: list[EvaluationRecord] = []
    for item in inputs:
        generation = generation_map[item.record_id]
        raw_output = generation.raw_output if generation.status == "COMPLETED" else ""
        evaluation = evaluate_output(
            record=item,
            oracle=oracle_map[item.record_id],
            raw_output=raw_output,
            config=pack.evaluator,
            output_schema=pack.output_schema,
            cross_field_schema=pack.cross_field_schema,
            vocabularies=pack.vocabularies,
            safety_rules=pack.safety_rules,
            trusted_plugin=pack.trusted_plugin,
        )
        payload = {
            "schema_version": "inheritbench.succession-evaluation-record.v0.2",
            "surface": surface,
            "system_role": system_role,
            "checkpoint_id": checkpoint_id,
            "model": model,
            "generation": generation,
            "evaluation": evaluation.model_dump(mode="json"),
        }
        payload["content_sha256"] = content_sha256(payload)
        records.append(EvaluationRecord.model_validate(payload, strict=True))
    return records


def summarize(surface: str, records: list[EvaluationRecord]) -> SurfaceSummary:
    group_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    semantic = strict = vocabulary = cross_field = structural = blockers = unknown = 0
    field_total = 0.0
    for record in records:
        evaluation = record.evaluation
        semantic += int(bool(evaluation["semantic_match"]))
        strict += int(bool(evaluation["strict_valid"]))
        vocabulary += int(bool(evaluation.get("vocabulary_conformant", False)))
        cross_field += int(bool(evaluation.get("cross_field_conformant", False)))
        structural += int(bool(evaluation["structural_exact"]))
        field_total += float(evaluation["mean_field_correctness"])
        findings = evaluation["safety_findings"]
        blockers += sum(item["severity"] == "blocker" for item in findings)
        unknown += int(record.generation.status != "COMPLETED")
        coverage = evaluation["coverage"]
        group = str(
            coverage.get("group") or coverage.get("archetype") or coverage.get("family") or "all"
        )
        group_counts[group][0] += int(bool(evaluation["semantic_match"]))
        group_counts[group][1] += 1
    group_semantic = {
        group: {
            "correct": values[0],
            "total": values[1],
            "rate": values[0] / values[1] if values[1] else 0.0,
        }
        for group, values in sorted(group_counts.items())
    }
    minimum = min(
        (float(value["rate"]) for value in group_semantic.values()),
        default=0.0,
    )
    return SurfaceSummary(
        surface=surface,
        expected=len(records),
        terminal=sum(record.generation.status in {"COMPLETED", "FAILED"} for record in records),
        semantic_correct=semantic,
        strict_valid=strict,
        vocabulary_conformant=vocabulary,
        cross_field_conformant=cross_field,
        structural_exact=structural,
        mean_field_correctness=field_total / len(records) if records else 0.0,
        blocker_safety_findings=blockers,
        unknown_safety=unknown,
        minimum_group_semantic_rate=minimum,
        group_semantic=group_semantic,
    )


def checkpoint_decision(
    *,
    pack: LoadedCapabilityPack,
    adapter: ModelAdapter,
    model_config: ModelConfig,
    checkpoints: list[CheckpointArtifact],
    validation_inputs: list[CapabilityInputRecord],
    validation_oracles: list[CapabilityOracleRecord],
    device: str,
    maximum_new_tokens: int,
    seed: int,
    policy: CheckpointPolicy,
) -> tuple[CheckpointDecision, dict[str, list[EvaluationRecord]]]:
    labeled_validation = _validation_labels(validation_inputs, validation_oracles)
    scores: list[CheckpointScore] = []
    evaluations: dict[str, list[EvaluationRecord]] = {}
    for checkpoint in checkpoints:
        directory = Path(checkpoint.adapter_directory)
        identity, generations = adapter.generate(
            model_config,
            validation_inputs,
            device=device,
            maximum_new_tokens=maximum_new_tokens,
            seed=seed,
            adapter_directory=directory,
        )
        evaluated = evaluate_generations(
            pack=pack,
            surface="validation",
            system_role="target_checkpoint",
            checkpoint_id=checkpoint.checkpoint_id,
            model=identity,
            inputs=validation_inputs,
            oracles=validation_oracles,
            generations=generations,
        )
        evaluations[checkpoint.checkpoint_id] = evaluated
        summary = summarize("validation", evaluated)
        loss = adapter.validation_loss(
            model_config,
            labeled_validation,
            device=device,
            adapter_directory=directory,
        )
        scores.append(
            CheckpointScore(
                checkpoint_id=checkpoint.checkpoint_id,
                adapter_directory=checkpoint.adapter_directory,
                adapter_sha256=checkpoint.adapter_sha256,
                eligible=(
                    (not policy.require_complete_validation or summary.terminal == summary.expected)
                    and summary.blocker_safety_findings <= policy.maximum_blocker_safety_findings
                    and summary.unknown_safety == 0
                ),
                semantic_rate=summary.semantic_correct / summary.expected,
                strict_rate=summary.strict_valid / summary.expected,
                minimum_group_semantic_rate=summary.minimum_group_semantic_rate,
                mean_field_correctness=summary.mean_field_correctness,
                validation_loss=loss,
                optimizer_step=checkpoint.optimizer_step,
                blocker_safety_findings=summary.blocker_safety_findings,
            )
        )
    eligible = [score for score in scores if score.eligible]
    if not eligible:
        return (
            CheckpointDecision(
                status="NO_SAFETY_ELIGIBLE_CHECKPOINT",
                scores=scores,
                selected_checkpoint_id=None,
                selected_adapter_directory=None,
                selected_adapter_sha256=None,
            ),
            evaluations,
        )
    selected = max(eligible, key=lambda item: _checkpoint_rank(item, policy))
    return (
        CheckpointDecision(
            status="SELECTED",
            scores=scores,
            selected_checkpoint_id=selected.checkpoint_id,
            selected_adapter_directory=selected.adapter_directory,
            selected_adapter_sha256=selected.adapter_sha256,
        ),
        evaluations,
    )


def _checkpoint_rank(score: CheckpointScore, policy: CheckpointPolicy) -> tuple[float, ...]:
    values = {
        "semantic_rate": score.semantic_rate,
        "historical_strict_rate": score.strict_rate,
        "minimum_group_semantic_rate": score.minimum_group_semantic_rate,
        "mean_field_correctness": score.mean_field_correctness,
        "validation_loss_ascending": -score.validation_loss,
        "optimizer_step_ascending": -float(score.optimizer_step),
    }
    return tuple(values[metric] for metric in policy.ranking)


def _validation_labels(
    inputs: list[CapabilityInputRecord],
    oracles: list[CapabilityOracleRecord],
) -> list[CapabilityLabeledRecord]:
    from inheritbench.artifacts.hashing import canonical_json, content_sha256, sha256_text

    oracle_map = {record.record_id: record for record in oracles}
    results: list[CapabilityLabeledRecord] = []
    for record in inputs:
        label = canonical_json(oracle_map[record.record_id].expected)
        payload = {
            "schema_version": "inheritbench.capability-labeled-record.v0.2",
            "record_id": record.record_id,
            "input_record": record,
            "assistant_label": label,
            "label_origin": "direct",
            "assistant_label_sha256": sha256_text(label),
        }
        payload["content_sha256"] = content_sha256(payload)
        results.append(CapabilityLabeledRecord.model_validate(payload, strict=True))
    return results
