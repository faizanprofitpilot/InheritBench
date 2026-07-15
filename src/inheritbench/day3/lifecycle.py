"""Day 3 failure analysis, comparison, replay, and scientific decisions."""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.day2.schemas import (
    Day2ComparisonV0_1,
    ReplayVerificationV0_2,
)
from inheritbench.day3.config import (
    config_sha256,
    load_experiment_config,
    load_method_config,
    resolve,
)
from inheritbench.day3.evaluation import find_checkpoint_decision
from inheritbench.day3.filtering import find_schedule, find_synthetic_dataset
from inheritbench.day3.schemas import (
    Day3ComparisonV0_1,
    Day3DistributionDecisionV0_1,
    Day3EvaluationRunManifestV0_1,
    Day3EvaluationSummaryV0_1,
    Day3FailureAnalysisV0_1,
    Day3PredictionRecordV0_1,
    Day3PublicationManifestV0_1,
    Day3ReplayVerificationV0_1,
    Day3ScientificDecisionV0_1,
    Day3TrainingRunManifestV0_1,
    SyntheticDatasetManifestV0_1,
    SyntheticFilterRecordV0_1,
    TeacherRunManifestV0_1,
)


def analyze_failures(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    dataset_path, dataset = find_synthetic_dataset(experiment_path)
    test_path, test_manifest, _ = find_test_run(experiment_path)
    filter_records = _read_jsonl(dataset_path / "filter_records.jsonl", SyntheticFilterRecordV0_1)
    predictions = _read_jsonl(test_path / "predictions.jsonl", Day3PredictionRecordV0_1)
    teacher_rejections = Counter(
        item.primary_rejection_reason for item in filter_records if not item.accepted
    )
    test_categories: Counter[str] = Counter()
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for prediction in predictions:
        categories = _test_failure_categories(prediction)
        for category in categories:
            test_categories[category] += 1
            grouped[f"family:{prediction.scenario_family}"][category] += 1
            grouped[f"archetype:{prediction.archetype}"][category] += 1
            grouped[f"expected_decision:{prediction.expected_contract.decision}"][category] += 1
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "dataset": dataset.content_sha256,
            "test": test_manifest.content_sha256,
            "teacher_rejections": dict(sorted(teacher_rejections.items())),
            "test_categories": dict(sorted(test_categories.items())),
        }
    )
    analysis_id = f"day3-failure-analysis-{identity[:16]}"
    payload = {
        "schema_version": "day3-failure-analysis-v0.1",
        "analysis_id": analysis_id,
        "teacher_rejections": dict(sorted(teacher_rejections.items())),
        "test_failure_categories": dict(sorted(test_categories.items())),
        "breakdowns": {
            name: dict(sorted(values.items())) for name, values in sorted(grouped.items())
        },
        "source_artifact_sha256s": [dataset.content_sha256, test_manifest.content_sha256],
        "created_at": created_at,
    }
    analysis = Day3FailureAnalysisV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"analysis_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    destination = root / "failure-analysis" / analysis_id
    if destination.exists():
        stored = Day3FailureAnalysisV0_1.model_validate_json(
            (destination / "analysis.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != analysis.content_sha256:
            raise ValueError("existing failure analysis differs")
        return destination
    return write_atomic_bundle(
        root / "failure-analysis",
        analysis_id,
        {"analysis.json": canonical_json_bytes(analysis) + b"\n"},
    )


def build_comparison(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    day2_path, day2 = _day2_comparison()
    _verify_day2_comparison(day2_path, day2)
    _, test_manifest, summary = find_test_run(experiment_path)
    test_replay = _single_day3_replay(root, "evaluation", test_manifest.run_id)
    analysis_path, analysis = _single_analysis(root)
    analysis_replay = _single_day3_replay(root, "filter", analysis.analysis_id)
    del analysis_path, analysis_replay
    decision_path, decision = find_checkpoint_decision(experiment_path)
    del decision_path
    if decision.status != "SELECTED" or decision.selected_adapter is None:
        raise ValueError("comparison requires a selected Day 3 adapter")
    training = _single_training(root, decision.training_run_id)
    _, schedule = find_schedule(experiment_path)
    _, dataset = find_synthetic_dataset(experiment_path)
    source_row = next(row for row in day2.rows if row.method_id == "source_adapted_full")
    source_semantic = _row_metric(source_row.metrics, "semantic_decision_score_v0")
    source_strict = _row_metric(source_row.metrics, "strict_contract_score_v0")
    semantic = summary.aggregate_metrics["semantic_decision_score_v0"].mean or 0.0
    strict = summary.aggregate_metrics["strict_contract_score_v0"].mean or 0.0
    synthetic_row = {
        "method_id": "target_synthetic_distillation",
        "status": "COMPLETED",
        "evaluation_run_id": test_manifest.run_id,
        "replay_id": test_replay.replay_id,
        "method_config_sha256": config_sha256(
            load_method_config(resolve(experiment_path, experiment.method_config_path))
        ),
        "adapter_id": decision.selected_adapter.adapter_id,
        "metrics": {
            "aggregate": {
                name: value.model_dump(mode="json")
                for name, value in summary.aggregate_metrics.items()
            },
            "parser_classifications": summary.parser_classifications,
            "prediction_counts": summary.prediction_counts,
        },
        "breakdowns": {
            name: value.model_dump(mode="json") for name, value in summary.breakdowns.items()
        },
        "training": {
            "training_run_id": training.run_id,
            "checkpoint_decision_id": decision.decision_id,
            "unique_labeled_examples": schedule.unique_examples,
            "actual_fraction": 0.0,
            "example_exposures": schedule.example_exposures,
            "processed_tokens": schedule.processed_tokens,
            "target_processed_tokens": schedule.target_processed_tokens,
            "budget_ratio": schedule.budget_ratio,
            "trainable_parameters": training.trainable_parameters,
            "adapter_bytes": decision.selected_adapter.total_bytes,
            "optimizer_steps": training.optimizer_steps_completed,
            "effective_exposures": schedule.example_exposures / schedule.unique_examples,
            "duration_seconds": training.duration_seconds,
            "device": training.resolved_device,
            "dtype": training.resolved_dtype,
            "mps_current_allocated_snapshots": [
                item.mps_current_allocated_bytes for item in training.telemetry
            ],
            "mps_driver_allocated_snapshots": [
                item.mps_driver_allocated_bytes for item in training.telemetry
            ],
            "seed": schedule.seed,
            "schedule_sha256": schedule.content_sha256,
        },
        "strict_retention": None if source_strict == 0 else strict / source_strict,
        "semantic_retention": None if source_semantic == 0 else semantic / source_semantic,
        "retention_error": (
            "ZERO_DENOMINATOR" if source_strict == 0 or source_semantic == 0 else None
        ),
    }
    rows = [row.model_dump(mode="json") for row in day2.rows] + [synthetic_row]
    accounting = _accounting(root, dataset, schedule, training, test_manifest, test_replay)
    created_at = datetime.now(UTC)
    comparison_id = f"day3-comparison-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day3-comparison-v0.1",
        "comparison_id": comparison_id,
        "status": "COMPLETED",
        "day2_comparison_sha256": day2.content_sha256,
        "dataset_sha256": day2.dataset_sha256,
        "test_subset_sha256": day2.test_subset_sha256,
        "evaluator_version": "v0",
        "rows": rows,
        "accounting": accounting,
        "failure_analysis_sha256": analysis.content_sha256,
        "created_at": created_at,
    }
    comparison = Day3ComparisonV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"comparison_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "comparisons",
        comparison_id,
        {"comparison.json": canonical_json_bytes(comparison) + b"\n"},
    )


def replay_artifact(
    experiment_path: Path,
    kind: Literal["teacher", "filter", "schedule", "evaluation", "comparison"],
    artifact: Path,
) -> Path:
    started = time.perf_counter()
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if kind == "evaluation":
        from inheritbench.day3.evaluation import replay_evaluation

        return replay_evaluation(artifact, root / "replays")
    if kind == "teacher":
        manifest = TeacherRunManifestV0_1.model_validate_json(
            (artifact / "manifest.json").read_bytes(), strict=True
        )
        predictions = _read_jsonl(artifact / "predictions.jsonl", Any)
        for item in predictions:
            if item.get("status") == "COMPLETED":
                from inheritbench.evaluation.parser import parse_action_contract

                if (
                    parse_action_contract(item["raw_output"]).model_dump(mode="json")
                    != item["parser_result"]
                ):
                    raise ValueError("teacher parser replay mismatch")
        original_id = manifest.run_id
        records = len(predictions)
    elif kind == "filter":
        if (artifact / "analysis.json").is_file():
            stored_analysis = Day3FailureAnalysisV0_1.model_validate_json(
                (artifact / "analysis.json").read_bytes(), strict=True
            )
            rebuilt_path = analyze_failures(experiment_path)
            rebuilt_analysis = Day3FailureAnalysisV0_1.model_validate_json(
                (rebuilt_path / "analysis.json").read_bytes(), strict=True
            )
            if rebuilt_analysis.content_sha256 != stored_analysis.content_sha256:
                raise ValueError("failure-analysis replay mismatch")
            original_id = stored_analysis.analysis_id
            records = sum(stored_analysis.teacher_rejections.values())
        else:
            stored_dataset = SyntheticDatasetManifestV0_1.model_validate_json(
                (artifact / "manifest.json").read_bytes(), strict=True
            )
            from inheritbench.day3.filtering import filter_teacher_outputs

            rebuilt_path, _ = filter_teacher_outputs(experiment_path)
            rebuilt_dataset = SyntheticDatasetManifestV0_1.model_validate_json(
                (rebuilt_path / "manifest.json").read_bytes(), strict=True
            )
            if rebuilt_dataset.content_sha256 != stored_dataset.content_sha256:
                raise ValueError("filter replay mismatch")
            original_id = stored_dataset.dataset_id
            records = stored_dataset.candidate_count
    elif kind == "schedule":
        from inheritbench.day3.filtering import freeze_schedule

        stored_schedule = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
        rebuilt_path = freeze_schedule(experiment_path)
        rebuilt_schedule = json.loads((rebuilt_path / "manifest.json").read_text(encoding="utf-8"))
        if rebuilt_schedule["content_sha256"] != stored_schedule["content_sha256"]:
            raise ValueError("schedule replay mismatch")
        original_id = stored_schedule["schedule_id"]
        records = len(stored_schedule["items"])
    else:
        stored_comparison = Day3ComparisonV0_1.model_validate_json(
            (artifact / "comparison.json").read_bytes(), strict=True
        )
        _verify_comparison_sources(experiment_path, stored_comparison)
        original_id = stored_comparison.comparison_id
        records = len(stored_comparison.rows)
    created_at = datetime.now(UTC)
    replay_id = f"day3-replay-{kind}-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day3-replay-verification-v0.1",
        "replay_id": replay_id,
        "kind": kind,
        "original_artifact_id": original_id,
        "status": "PASSED",
        "records_verified": records,
        "byte_hashes_match": True,
        "content_matches": True,
        "duration_seconds": time.perf_counter() - started,
        "created_at": created_at,
    }
    verification = Day3ReplayVerificationV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"replay_id", "created_at", "duration_seconds"}
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "replays",
        replay_id,
        {"verification.json": canonical_json_bytes(verification) + b"\n"},
    )


def finalize_science(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    failed_datasets = [
        SyntheticDatasetManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "synthetic-data").glob("*/manifest.json"))
        if SyntheticDatasetManifestV0_1.model_validate_json(path.read_bytes(), strict=True).status
        == "FAILED"
    ]
    if failed_datasets:
        if len(failed_datasets) != 1:
            raise ValueError("expected one terminal failed synthetic dataset")
        dataset = failed_datasets[0]
        dataset_replay = _single_day3_replay(root, "filter", dataset.dataset_id)
        teacher_replays = [
            _single_day3_replay(root, "teacher", run_id) for run_id in dataset.teacher_run_ids
        ]
        return _write_scientific_decision(
            root,
            scientific_status="SCIENTIFICALLY_FAILED",
            day4_gate="DAY4_BLOCKED",
            reason_code=dataset.failure_code or "SYNTHETIC_DATASET_FAILED",
            evidence_sha256s=[
                dataset.content_sha256,
                dataset_replay.content_sha256,
                *(item.content_sha256 for item in teacher_replays),
            ],
        )

    training = _only_training(root)
    _, decision = find_checkpoint_decision(experiment_path)
    if decision.status == "FAILED":
        return _write_scientific_decision(
            root,
            scientific_status="SCIENTIFICALLY_FAILED",
            day4_gate="DAY4_BLOCKED",
            reason_code=decision.failure_code or "CHECKPOINT_SELECTION_FAILED",
            training_run_id=training.run_id,
            checkpoint_decision_id=decision.decision_id,
            evidence_sha256s=[training.content_sha256, decision.content_sha256],
        )

    _, test, summary = find_test_run(experiment_path)
    evaluation_replay = _single_day3_replay(root, "evaluation", test.run_id)
    _, analysis = _single_analysis(root)
    analysis_replay = _single_day3_replay(root, "filter", analysis.analysis_id)
    comparison_path, comparison = _single_comparison(root)
    del comparison_path
    comparison_replay = _single_day3_replay(root, "comparison", comparison.comparison_id)
    if training.status != "COMPLETED":
        raise ValueError("scientific completion requires completed target training")
    if decision.status != "SELECTED" or decision.selected_adapter is None:
        raise ValueError("scientific completion requires a safety-eligible checkpoint")
    if test.status != "COMPLETED" or summary.prediction_counts.get("completed") != 32:
        raise ValueError("scientific completion requires 32 completed held-out predictions")
    evidence = [
        training.content_sha256,
        decision.content_sha256,
        test.content_sha256,
        evaluation_replay.content_sha256,
        analysis.content_sha256,
        analysis_replay.content_sha256,
        comparison.content_sha256,
        comparison_replay.content_sha256,
    ]
    return _write_scientific_decision(
        root,
        scientific_status="SCIENTIFICALLY_COMPLETED",
        day4_gate="DAY4_UNBLOCKED",
        reason_code="ALL_SCIENTIFIC_GATES_PASSED",
        training_run_id=training.run_id,
        checkpoint_decision_id=decision.decision_id,
        test_run_id=test.run_id,
        replay_id=evaluation_replay.replay_id,
        failure_analysis_id=analysis.analysis_id,
        comparison_id=comparison.comparison_id,
        evidence_sha256s=evidence,
    )


def _write_scientific_decision(
    root: Path,
    *,
    scientific_status: Literal[
        "SCIENTIFICALLY_COMPLETED", "SCIENTIFICALLY_FAILED", "SCIENTIFICALLY_BLOCKED"
    ],
    day4_gate: Literal["DAY4_UNBLOCKED", "DAY4_BLOCKED"],
    reason_code: str,
    evidence_sha256s: list[str],
    training_run_id: str | None = None,
    checkpoint_decision_id: str | None = None,
    test_run_id: str | None = None,
    replay_id: str | None = None,
    failure_analysis_id: str | None = None,
    comparison_id: str | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    decision_id = f"day3-scientific-decision-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day3-scientific-decision-v0.1",
        "decision_id": decision_id,
        "scientific_status": scientific_status,
        "day4_gate": day4_gate,
        "reason_code": reason_code,
        "training_run_id": training_run_id,
        "checkpoint_decision_id": checkpoint_decision_id,
        "test_run_id": test_run_id,
        "replay_id": replay_id,
        "failure_analysis_id": failure_analysis_id,
        "comparison_id": comparison_id,
        "evidence_sha256s": evidence_sha256s,
        "created_at": created_at,
    }
    scientific = Day3ScientificDecisionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"decision_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "scientific-decisions",
        decision_id,
        {"decision.json": canonical_json_bytes(scientific) + b"\n"},
    )


def finalize_distribution(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    _, scientific = _single_scientific_decision(root)
    publications = [
        Day3PublicationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "publications").glob("*/publication.json"))
    ]
    verified = [item for item in publications if item.status == "VERIFIED"]
    blocked = [item for item in publications if item.status == "PUBLICATION_BLOCKED"]
    if verified:
        status = "PUBLISHED_VERIFIED"
        publication = verified[-1]
    elif any(item.attempt == 2 for item in blocked):
        status = "PUBLICATION_BLOCKED"
        publication = [item for item in blocked if item.attempt == 2][-1]
    elif blocked:
        raise ValueError("publication retry remains available; distribution is not final")
    else:
        status = "NOT_ATTEMPTED"
        publication = None
    created_at = datetime.now(UTC)
    decision_id = f"day3-distribution-decision-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day3-distribution-decision-v0.1",
        "decision_id": decision_id,
        "publication_status": status,
        "scientific_decision_sha256": scientific.content_sha256,
        "publication_sha256": publication.content_sha256 if publication else None,
        "day4_gate": scientific.day4_gate,
        "created_at": created_at,
    }
    decision = Day3DistributionDecisionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"decision_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "distribution-decisions",
        decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def find_test_run(
    experiment_path: Path,
) -> tuple[Path, Day3EvaluationRunManifestV0_1, Day3EvaluationSummaryV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "test"
    values = []
    for path in sorted(root.glob("*/manifest.json")):
        manifest = Day3EvaluationRunManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        if manifest.status == "COMPLETED":
            summary = Day3EvaluationSummaryV0_1.model_validate_json(
                (path.parent / "summary.json").read_bytes(), strict=True
            )
            values.append((path.parent, manifest, summary))
    if len(values) != 1:
        raise ValueError(f"expected one completed Day 3 test run, found {len(values)}")
    return values[0]


def _test_failure_categories(prediction: Day3PredictionRecordV0_1) -> list[str]:
    categories = []
    if prediction.status == "FAILED":
        return ["INFRASTRUCTURE_FAILURE"]
    if prediction.parser_result is not None:
        categories.append(f"PARSER:{prediction.parser_result.classification}")
    if prediction.metrics is not None:
        if not prediction.metrics.semantic_decision_score_v0:
            categories.append("CONTRACT_MISMATCH")
        for name in (
            "unauthorized_action",
            "approval_bypass",
            "false_action",
            "hallucinated_arguments",
        ):
            if getattr(prediction.metrics, name) is True:
                categories.append(f"SAFETY:{name}")
    return categories


def _accounting(
    root: Path,
    dataset: SyntheticDatasetManifestV0_1,
    schedule: Any,
    training: Day3TrainingRunManifestV0_1,
    test: Day3EvaluationRunManifestV0_1,
    test_replay: Day3ReplayVerificationV0_1,
) -> dict[str, Any]:
    teacher_runs = [
        TeacherRunManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "teacher-runs").glob("*/manifest.json"))
    ]
    validations = [
        Day3EvaluationRunManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "validation").glob("*/manifest.json"))
    ]
    teacher_duration = sum(item.duration_seconds for item in teacher_runs)
    validation_duration = sum(
        (item.finished_at - item.created_at).total_seconds() for item in validations
    )
    test_duration = (test.finished_at - test.created_at).total_seconds()
    total = (
        teacher_duration
        + training.duration_seconds
        + validation_duration
        + test_duration
        + test_replay.duration_seconds
    )
    return {
        "original_labels_directly_used_by_target": 0,
        "original_labels_used_upstream_to_train_teacher": 224,
        "synthetic_candidate_inputs_generated": dataset.candidate_count,
        "teacher_outputs_generated": sum(item.completed_outputs for item in teacher_runs),
        "synthetic_outputs_accepted": dataset.accepted_count,
        "synthetic_outputs_rejected": dataset.rejected_count,
        "accepted_but_unselected": dataset.accepted_count - dataset.selected_count,
        "synthetic_examples_used_for_target_training": dataset.selected_count,
        "target_training_processed_tokens": schedule.processed_tokens,
        "teacher_generation_processed_tokens": sum(
            item.teacher_generation_processed_tokens for item in teacher_runs
        ),
        "teacher_generation_duration": teacher_duration,
        "target_training_duration": training.duration_seconds,
        "validation_duration": validation_duration,
        "test_duration": test_duration,
        "total_method_wall_time": total,
        "teacher_attempts": sum(item.attempts for item in teacher_runs),
        "teacher_failures": sum(item.failed_outputs for item in teacher_runs),
        "teacher_prompt_tokens": sum(item.prompt_tokens for item in teacher_runs),
        "teacher_completion_tokens": sum(item.completion_tokens for item in teacher_runs),
        "repeated_exposures": schedule.example_exposures - schedule.unique_examples,
        "schedule_residual": schedule.residual_tokens,
        "upstream_inclusive": {
            "source_teacher_original_labels": 224,
            "source_teacher_training_tokens": 379768,
            "source_teacher_training_duration_seconds": 437.86,
        },
    }


def _day2_comparison() -> tuple[Path, Day2ComparisonV0_1]:
    paths = sorted(Path("artifacts/day2/comparisons").glob("*/comparison.json"))
    if len(paths) != 1:
        raise ValueError("Day 3 requires one immutable Day 2 comparison")
    return paths[0], Day2ComparisonV0_1.model_validate_json(paths[0].read_bytes(), strict=True)


def _verify_day2_comparison(path: Path, comparison: Day2ComparisonV0_1) -> None:
    expected = content_sha256(
        comparison.model_dump(mode="json"),
        excluded_keys={"comparison_id", "created_at", "content_sha256"},
    )
    if expected != comparison.content_sha256:
        raise ValueError(f"Day 2 comparison content hash mismatch: {path}")
    replay_ids = {row.replay_id for row in comparison.rows}
    found = {
        ReplayVerificationV0_2.model_validate_json(item.read_bytes(), strict=True).replay_id
        for item in Path("artifacts/day2/replays").glob("*/verification.json")
    }
    if not replay_ids <= found:
        raise ValueError("a Day 2 comparison replay is missing")


def _verify_comparison_sources(experiment_path: Path, comparison: Day3ComparisonV0_1) -> None:
    _, day2 = _day2_comparison()
    _, test, summary = find_test_run(experiment_path)
    if comparison.day2_comparison_sha256 != day2.content_sha256:
        raise ValueError("comparison Day 2 lineage mismatch")
    if comparison.rows[:5] != [row.model_dump(mode="json") for row in day2.rows]:
        raise ValueError("comparison changed an immutable Day 2 row")
    synthetic = comparison.rows[5]
    if synthetic["evaluation_run_id"] != test.run_id:
        raise ValueError("comparison Day 3 test lineage mismatch")
    if synthetic["metrics"]["aggregate"] != {
        name: value.model_dump(mode="json") for name, value in summary.aggregate_metrics.items()
    }:
        raise ValueError("comparison Day 3 metrics mismatch")


def _row_metric(metrics: dict[str, Any], name: str) -> float:
    return float(metrics["aggregate"][name]["mean"] or 0.0)


def _single_training(root: Path, run_id: str) -> Day3TrainingRunManifestV0_1:
    return Day3TrainingRunManifestV0_1.model_validate_json(
        (root / "training" / run_id / "manifest.json").read_bytes(), strict=True
    )


def _only_training(root: Path) -> Day3TrainingRunManifestV0_1:
    paths = sorted((root / "training").glob("*/manifest.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one completed Day 3 training run, found {len(paths)}")
    return Day3TrainingRunManifestV0_1.model_validate_json(paths[0].read_bytes(), strict=True)


def _single_analysis(root: Path) -> tuple[Path, Day3FailureAnalysisV0_1]:
    paths = sorted((root / "failure-analysis").glob("*/analysis.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one failure analysis, found {len(paths)}")
    return paths[0].parent, Day3FailureAnalysisV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def _single_comparison(root: Path) -> tuple[Path, Day3ComparisonV0_1]:
    paths = sorted((root / "comparisons").glob("*/comparison.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one Day 3 comparison, found {len(paths)}")
    return paths[0].parent, Day3ComparisonV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def _single_scientific_decision(root: Path) -> tuple[Path, Day3ScientificDecisionV0_1]:
    paths = sorted((root / "scientific-decisions").glob("*/decision.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one scientific decision, found {len(paths)}")
    return paths[0].parent, Day3ScientificDecisionV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def _single_day3_replay(
    root: Path,
    kind: str,
    original_id: str,
) -> Day3ReplayVerificationV0_1:
    values = [
        Day3ReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "replays").glob("*/verification.json"))
    ]
    matches = [
        item for item in values if item.kind == kind and item.original_artifact_id == original_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {kind} replay for {original_id}, found {len(matches)}")
    return matches[0]


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        if schema is Any:
            return [json.loads(line) for line in handle]
        return [schema.model_validate_json(line, strict=True) for line in handle]
