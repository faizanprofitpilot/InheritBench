"""Final five-system Day 2 comparison with complete lineage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.day2.config import load_experiment_config, load_method_config, method_config_hash
from inheritbench.day2.data import find_data_bundle, load_schedule, load_subset
from inheritbench.day2.schemas import (
    CheckpointDecisionV0_1,
    Day2ComparisonV0_1,
    EvaluationRunManifestV0_2,
    EvaluationSummaryV0_2,
    MethodComparisonRow,
    ReplayVerificationV0_2,
    SourceCapabilityDecisionV0_1,
    TrainingRunManifestV0_2,
)

_METHODS = (
    "source_base_supporting",
    "source_adapted_full",
    "target_untouched",
    "target_full_retrain",
    "target_limited_retrain_10pct",
)


def build_comparison(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = _resolve(experiment_path, experiment.artifact_root)
    gate = _confirmed_gate(root)
    bundle = find_data_bundle(experiment_path, experiment)
    test_subset = load_subset(bundle, "final_test")
    methods: dict[str, tuple[Path, Any]] = {
        load_method_config(_resolve(experiment_path, path)).method_id: (
            _resolve(experiment_path, path),
            load_method_config(_resolve(experiment_path, path)),
        )
        for path in experiment.method_config_paths
    }
    evaluation_runs = {method_id: _single_test_run(root, method_id) for method_id in _METHODS}
    summaries = {
        method_id: EvaluationSummaryV0_2.model_validate_json(
            (run_path / "summary.json").read_bytes(), strict=True
        )
        for method_id, run_path in evaluation_runs.items()
    }
    source_semantic = _metric(summaries["source_adapted_full"], "semantic_decision_score_v0")
    source_strict = _metric(summaries["source_adapted_full"], "strict_contract_score_v0")
    rows: list[MethodComparisonRow] = []
    for method_id in _METHODS:
        method_path, method = methods[method_id]
        del method_path
        run_path = evaluation_runs[method_id]
        manifest = EvaluationRunManifestV0_2.model_validate_json(
            (run_path / "manifest.json").read_bytes(), strict=True
        )
        replay = _single_replay(root, manifest.run_id)
        summary = summaries[method_id]
        semantic = _metric(summary, "semantic_decision_score_v0")
        strict = _metric(summary, "strict_contract_score_v0")
        error = "ZERO_DENOMINATOR" if source_semantic == 0 or source_strict == 0 else None
        rows.append(
            MethodComparisonRow(
                method_id=method_id,  # type: ignore[arg-type]
                status="COMPLETED",
                evaluation_run_id=manifest.run_id,
                replay_id=replay.replay_id,
                method_config_sha256=method_config_hash(method),
                adapter_id=manifest.adapter.adapter_id if manifest.adapter else None,
                metrics={
                    "aggregate": {
                        name: value.model_dump(mode="json")
                        for name, value in summary.aggregate_metrics.items()
                    },
                    "parser_classifications": summary.parser_classifications,
                    "prediction_counts": summary.prediction_counts,
                },
                breakdowns={
                    name: value.model_dump(mode="json")
                    for name, value in summary.breakdowns.items()
                },
                training=_training_details(root, bundle, method_id),
                strict_retention=None if source_strict == 0 else strict / source_strict,
                semantic_retention=None if source_semantic == 0 else semantic / source_semantic,
                retention_error=error,  # type: ignore[arg-type]
            )
        )
    created_at = datetime.now(UTC)
    comparison_id = f"day2-comparison-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day2-comparison-v0.1",
        "comparison_id": comparison_id,
        "status": "COMPLETED",
        "source_gate_sha256": gate.content_sha256,
        "dataset_sha256": test_subset.dataset_sha256,
        "test_subset_sha256": test_subset.content_sha256,
        "evaluator_version": "v0",
        "rows": [row.model_dump(mode="json") for row in rows],
        "created_at": created_at,
    }
    comparison = Day2ComparisonV0_1.model_validate(
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


def _training_details(root: Path, bundle: Path, method_id: str) -> dict[str, Any] | None:
    if method_id in {"source_base_supporting", "target_untouched"}:
        return None
    decision = _single_decision(root, method_id)
    training_path = root / "training" / decision.training_run_id / "manifest.json"
    training = TrainingRunManifestV0_2.model_validate_json(training_path.read_bytes(), strict=True)
    schedule_name = {
        "source_adapted_full": "source_primary",
        "target_full_retrain": "target_primary",
        "target_limited_retrain_10pct": "target_limited_primary",
    }[method_id]
    schedule = load_schedule(bundle, schedule_name)
    return {
        "training_run_id": training.run_id,
        "checkpoint_decision_id": decision.decision_id,
        "unique_labeled_examples": schedule.unique_examples,
        "actual_fraction": schedule.unique_examples / 224,
        "example_exposures": schedule.example_exposures,
        "processed_tokens": schedule.processed_tokens,
        "target_processed_tokens": schedule.target_processed_tokens,
        "budget_ratio": schedule.budget_ratio,
        "trainable_parameters": training.trainable_parameters,
        "adapter_bytes": (
            decision.selected_adapter.total_bytes if decision.selected_adapter else None
        ),
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
    }


def _confirmed_gate(root: Path) -> SourceCapabilityDecisionV0_1:
    values = [
        SourceCapabilityDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "source-gates").glob("*/decision.json"))
    ]
    confirmed = [item for item in values if item.status == "SOURCE_CAPABILITY_CONFIRMED"]
    if len(confirmed) != 1:
        raise ValueError("comparison requires exactly one confirmed source gate")
    return confirmed[0]


def _single_test_run(root: Path, method_id: str) -> Path:
    matches: list[Path] = []
    for path in sorted((root / "test").glob("*/manifest.json")):
        manifest = EvaluationRunManifestV0_2.model_validate_json(path.read_bytes(), strict=True)
        if manifest.method_id == method_id and manifest.status == "COMPLETED":
            matches.append(path.parent)
    if len(matches) != 1:
        raise ValueError(f"comparison requires one completed test run for {method_id}")
    return matches[0]


def _single_replay(root: Path, run_id: str) -> ReplayVerificationV0_2:
    matches: list[ReplayVerificationV0_2] = []
    for path in sorted((root / "replays").glob("*/verification.json")):
        replay = ReplayVerificationV0_2.model_validate_json(path.read_bytes(), strict=True)
        if replay.original_run_id == run_id:
            matches.append(replay)
    if len(matches) != 1:
        raise ValueError(f"comparison requires one passing replay for {run_id}")
    return matches[0]


def _single_decision(root: Path, method_id: str) -> CheckpointDecisionV0_1:
    matches: list[CheckpointDecisionV0_1] = []
    for path in sorted((root / "checkpoint-decisions").glob("*/decision.json")):
        decision = CheckpointDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        if decision.method_id == method_id and decision.status == "SELECTED":
            matches.append(decision)
    if len(matches) != 1:
        raise ValueError(f"comparison requires one checkpoint decision for {method_id}")
    return matches[0]


def _metric(summary: EvaluationSummaryV0_2, name: str) -> float:
    return summary.aggregate_metrics[name].mean or 0.0


def _resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    return direct if direct.exists() or path.parts[0] == "artifacts" else parent_file.parent / path
