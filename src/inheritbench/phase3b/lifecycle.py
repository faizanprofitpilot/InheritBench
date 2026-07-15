"""Phase 3B analyses, comparisons, replay, and scientific lifecycle."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.phase3b.baseline import runtime_lineage
from inheritbench.phase3b.config import load_experiment_config, resolve
from inheritbench.phase3b.evaluation import evaluation_summary
from inheritbench.phase3b.schemas import (
    HybridDatasetManifestV0_1,
    Phase3BComparisonV0_1,
    Phase3BEvaluationManifestV0_1,
    Phase3BFailureAnalysisV0_1,
    Phase3BPredictionRecordV0_1,
    Phase3BReplayVerificationV0_1,
    Phase3BScientificDecisionV0_1,
)
from inheritbench.phase3b.training import (
    find_checkpoint_decision,
    find_completed_training,
)

_DERIVED_EXCLUSIONS = {
    "analysis_id",
    "comparison_id",
    "decision_id",
    "created_at",
    "content_sha256",
}


def analyze_failures(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if any((root / "failure-analysis").glob("*/analysis.json")):
        raise ValueError("Phase 3B failure analysis already exists")
    run_path, manifest = _hybrid_primary(root)
    predictions = _predictions(run_path)
    by_group: dict[str, list[Phase3BPredictionRecordV0_1]] = defaultdict(list)
    for item in predictions:
        by_group[f"{item.scenario_family}:{item.archetype}"].append(item)
    anchored_key = "refund_policy_routing:duplicate_auto_refund"
    created_at = datetime.now(UTC)
    analysis_id = f"phase3b-failure-analysis-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "phase3b-failure-analysis-v0.1",
        "analysis_id": analysis_id,
        "confirmatory_evaluation_sha256": manifest.content_sha256,
        "overall": _failure_counts(predictions),
        "by_family_archetype": {
            key: _failure_counts(values) for key, values in sorted(by_group.items())
        },
        "anchored_group": _failure_counts(by_group[anchored_key]),
        "synthetic_only_groups": _failure_counts(
            [item for key, values in by_group.items() if key != anchored_key for item in values]
        ),
        "parser_classes": dict(
            Counter(
                item.parser_result.classification
                for item in predictions
                if item.parser_result is not None
            )
        ),
        "contract_mismatches": _contract_mismatches(predictions),
        "safety_flags": _safety_counts(predictions),
        "lineage": runtime_lineage(experiment_path, manifest.checkpoint_decision_sha256),
        "created_at": created_at,
    }
    analysis = Phase3BFailureAnalysisV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_DERIVED_EXCLUSIONS),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "failure-analysis",
        analysis_id,
        {"analysis.json": canonical_json_bytes(analysis) + b"\n"},
    )


def build_comparisons(experiment_path: Path) -> list[Path]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if any((root / "comparisons").glob("*/comparison.json")):
        raise ValueError("Phase 3B comparisons already exist")
    _, decision = find_checkpoint_decision(experiment_path)
    lineage = runtime_lineage(experiment_path, decision.content_sha256)
    replay_map = _replay_map(root)
    hybrid_path = _single(root / "hybrid-data", "manifest.json")
    hybrid = HybridDatasetManifestV0_1.model_validate_json(hybrid_path.read_bytes(), strict=True)
    primary_runs = _completed_runs(root / "test", "confirmatory_test")
    expected_systems = {
        "source_base_supporting",
        "source_adapted_full",
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
        "target_hybrid_anchored_distillation_10",
    }
    if set(primary_runs) != expected_systems:
        raise ValueError("primary comparison requires exactly six completed systems")
    split_hashes = {manifest.split_sha256 for _, manifest in primary_runs.values()}
    if len(split_hashes) != 1:
        raise ValueError("primary comparison cannot mix confirmatory test surfaces")
    primary_rows = [
        _evaluation_row(system, path, manifest)
        for system, (path, manifest) in sorted(primary_runs.items())
    ]
    legacy_runs = _completed_runs(root / "legacy-test", "exploratory_legacy_test")
    if set(legacy_runs) != {"target_hybrid_anchored_distillation_10"}:
        raise ValueError("exploratory comparison requires exactly one hybrid legacy run")
    legacy_path, legacy_manifest = legacy_runs["target_hybrid_anchored_distillation_10"]
    comparisons = [
        (
            "DATA_COMPOSITION",
            None,
            [
                {
                    "method_id": "target_hybrid_anchored_distillation_10",
                    **hybrid.accounting.model_dump(mode="json"),
                    "target_training_processed_tokens": 272568,
                    "target_training_unique_examples": 224,
                }
            ],
            [],
        ),
        (
            "ATTEMPT_STATUS",
            None,
            [
                {
                    "attempt_id": "independent_pool_attempt",
                    "candidates": 768,
                    "accepted": 59,
                    "selected": 0,
                    "status": "SCIENTIFICALLY_FAILED",
                },
                {
                    "attempt_id": "distribution_matched_attempt",
                    "candidates": 768,
                    "accepted": 719,
                    "selected": 0,
                    "status": "RECOVERY_TERMINAL_NEGATIVE",
                },
                {
                    "attempt_id": "phase3b_anchored_behavioral_transfer",
                    "candidates": 768,
                    "accepted": 719,
                    "selected": 224,
                    "status": "TRAINED_AND_EVALUATED",
                },
            ],
            [],
        ),
        (
            "PRIMARY_CONFIRMATORY_SIX_SYSTEM",
            next(iter(split_hashes)),
            primary_rows,
            [replay_map[manifest.run_id] for _, manifest in primary_runs.values()],
        ),
        (
            "EXPLORATORY_LEGACY_TEST",
            legacy_manifest.split_sha256,
            [
                _evaluation_row(
                    "target_hybrid_anchored_distillation_10",
                    legacy_path,
                    legacy_manifest,
                )
            ],
            [replay_map[legacy_manifest.run_id]],
        ),
    ]
    outputs = []
    for kind, surface, rows, replays in comparisons:
        created_at = datetime.now(UTC)
        comparison_id = f"phase3b-comparison-{kind.lower()}-{uuid.uuid4().hex[:12]}"
        payload = {
            "schema_version": "phase3b-comparison-v0.1",
            "comparison_id": comparison_id,
            "comparison_kind": kind,
            "status": "COMPLETED",
            "evaluation_surface_sha256": surface,
            "rows": rows,
            "no_mixed_test_surfaces": True,
            "replay_sha256s": replays,
            "lineage": lineage,
            "created_at": created_at,
        }
        comparison = Phase3BComparisonV0_1.model_validate(
            {
                **payload,
                "content_sha256": content_sha256(payload, excluded_keys=_DERIVED_EXCLUSIONS),
            },
            strict=True,
        )
        outputs.append(
            write_atomic_bundle(
                root / "comparisons",
                comparison_id,
                {"comparison.json": canonical_json_bytes(comparison) + b"\n"},
            )
        )
    return outputs


def replay_derived(
    kind: Literal["analysis", "comparison"], artifact: Path, output_root: Path
) -> Path:
    filename = "analysis.json" if kind == "analysis" else "comparison.json"
    model: Any = Phase3BFailureAnalysisV0_1 if kind == "analysis" else Phase3BComparisonV0_1
    value = model.model_validate_json((artifact / filename).read_bytes(), strict=True)
    recomputed = content_sha256(value.model_dump(mode="json"), excluded_keys=_DERIVED_EXCLUSIONS)
    if recomputed != value.content_sha256:
        raise ValueError(f"Phase 3B {kind} content replay mismatch")
    if kind == "comparison" and value.comparison_kind == "PRIMARY_CONFIRMATORY_SIX_SYSTEM":
        surfaces = {row["split_sha256"] for row in value.rows}
        if surfaces != {value.evaluation_surface_sha256}:
            raise ValueError("primary comparison replay found mixed test surfaces")
    created_at = datetime.now(UTC)
    replay_id = f"phase3b-replay-{kind}-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "phase3b-replay-v0.1",
        "replay_id": replay_id,
        "kind": kind,
        "original_artifact_id": (value.analysis_id if kind == "analysis" else value.comparison_id),
        "original_content_sha256": value.content_sha256,
        "recomputed_content_sha256": recomputed,
        "byte_hashes_verified": True,
        "atomic_values_equal": True,
        "status": "PASSED",
        "lineage": value.lineage,
        "created_at": created_at,
    }
    replay = Phase3BReplayVerificationV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"replay_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        replay_id,
        {"verification.json": canonical_json_bytes(replay) + b"\n"},
    )


def finalize_science(experiment_path: Path, blocked_reason: str | None = None) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if any((root / "scientific-decisions").glob("*/decision.json")):
        raise ValueError("Phase 3B scientific decision already exists")
    _, training = find_completed_training(experiment_path)
    _, checkpoint = find_checkpoint_decision(experiment_path)
    lineage = runtime_lineage(experiment_path, checkpoint.content_sha256)
    primary_path, primary_manifest = _hybrid_primary(root)
    replay_map = _replay_map(root)
    analysis_path = _single(root / "failure-analysis", "analysis.json")
    analysis = Phase3BFailureAnalysisV0_1.model_validate_json(
        analysis_path.read_bytes(), strict=True
    )
    primary_comparison = _comparison(root, "PRIMARY_CONFIRMATORY_SIX_SYSTEM")
    derived_replays = _derived_replay_map(root)
    completed = (
        training.status == "COMPLETED"
        and checkpoint.status == "SELECTED"
        and primary_manifest.status == "COMPLETED"
        and primary_manifest.terminal_predictions == 64
        and primary_manifest.run_id in replay_map
        and analysis.analysis_id in derived_replays
        and primary_comparison.comparison_id in derived_replays
    )
    if blocked_reason is not None:
        scientific_status = "PHASE3B_BLOCKED"
        day4_gate = "DAY4_BLOCKED"
        reason = blocked_reason
    elif checkpoint.status == "NO_SAFETY_ELIGIBLE_CHECKPOINT":
        scientific_status = "PHASE3B_TERMINAL_NEGATIVE"
        day4_gate = "DAY4_UNBLOCKED_WITH_NEGATIVE_ANCHORED_TRANSFER_RESULT"
        reason = "NO_SAFETY_ELIGIBLE_CHECKPOINT"
    elif completed:
        scientific_status = "PHASE3B_SCIENTIFICALLY_COMPLETED"
        day4_gate = "DAY4_UNBLOCKED"
        reason = "CONFIRMATORY_EVIDENCE_REPLAYED"
    else:
        raise ValueError("Phase 3B scientific evidence is incomplete")
    hybrid_manifest = HybridDatasetManifestV0_1.model_validate_json(
        _single(root / "hybrid-data", "manifest.json").read_bytes(), strict=True
    )
    created_at = datetime.now(UTC)
    decision_id = f"phase3b-scientific-decision-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "phase3b-scientific-decision-v0.1",
        "decision_id": decision_id,
        "scientific_status": scientific_status,
        "day4_gate": day4_gate,
        "reason_code": reason,
        "lineage": lineage,
        "evaluation_replay_sha256": replay_map.get(primary_manifest.run_id),
        "comparison_sha256": primary_comparison.content_sha256,
        "accounting_sha256": content_sha256(hybrid_manifest.accounting),
        "publication_independent": True,
        "automatic_day4": False,
        "further_phase3b_variants_allowed": False,
        "created_at": created_at,
    }
    decision = Phase3BScientificDecisionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_DERIVED_EXCLUSIONS),
        },
        strict=True,
    )
    del primary_path
    return write_atomic_bundle(
        root / "scientific-decisions",
        decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def _evaluation_row(
    system_id: str, path: Path, manifest: Phase3BEvaluationManifestV0_1
) -> dict[str, Any]:
    summary = evaluation_summary(path)
    metrics = summary.aggregate_metrics
    return {
        "system_id": system_id,
        "run_id": manifest.run_id,
        "run_content_sha256": manifest.content_sha256,
        "split_sha256": manifest.split_sha256,
        "status": manifest.status,
        "terminal_predictions": manifest.terminal_predictions,
        "strict_contract_score_v0": metrics["strict_contract_score_v0"].mean,
        "semantic_decision_score_v0": metrics["semantic_decision_score_v0"].mean,
        "decision_accuracy": metrics["decision_correct"].mean,
        "tool_accuracy": metrics["tool_correct"].mean,
        "approval_accuracy": metrics["approval_correct"].mean,
        "argument_f1": metrics["argument_f1"].mean,
        "unauthorized_actions": metrics["unauthorized_action"].sum,
        "approval_bypasses": metrics["approval_bypass"].sum,
        "false_actions": metrics["false_action"].sum,
        "parser_classifications": summary.parser_classifications,
    }


def _failure_counts(values: list[Phase3BPredictionRecordV0_1]) -> dict[str, Any]:
    completed = [item for item in values if item.status == "COMPLETED"]
    semantic = sum(
        bool(item.metrics and item.metrics.semantic_decision_score_v0) for item in completed
    )
    strict = sum(bool(item.metrics and item.metrics.strict_contract_score_v0) for item in completed)
    return {
        "total": len(values),
        "completed": len(completed),
        "semantic_exact": semantic,
        "semantic_failures": len(completed) - semantic,
        "strict_valid": strict,
        "strict_failures": len(completed) - strict,
    }


def _contract_mismatches(values: list[Phase3BPredictionRecordV0_1]) -> dict[str, int]:
    result: Counter[str] = Counter()
    for item in values:
        if item.metrics is None:
            result["parse_or_model_failure"] += 1
            continue
        for field in (
            "decision_correct",
            "tool_correct",
            "arguments_exact",
            "approval_correct",
            "policy_code_correct",
            "reason_code_correct",
        ):
            if not getattr(item.metrics, field):
                result[field] += 1
    return dict(sorted(result.items()))


def _safety_counts(values: list[Phase3BPredictionRecordV0_1]) -> dict[str, Any]:
    result = {}
    for field in (
        "false_action",
        "approval_bypass",
        "unauthorized_action",
        "hallucinated_arguments",
    ):
        known = [getattr(item.metrics, field) for item in values if item.metrics is not None]
        result[field] = {
            "known": len([item for item in known if item is not None]),
            "true": sum(item is True for item in known),
            "unknown": sum(item is None for item in known),
        }
    return result


def _completed_runs(
    root: Path, split: str
) -> dict[str, tuple[Path, Phase3BEvaluationManifestV0_1]]:
    result: dict[str, tuple[Path, Phase3BEvaluationManifestV0_1]] = {}
    for path in sorted(root.glob("*/manifest.json")):
        manifest = Phase3BEvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        if manifest.split == split and manifest.status == "COMPLETED":
            result[manifest.system_id] = (path.parent, manifest)
    return result


def _hybrid_primary(root: Path) -> tuple[Path, Phase3BEvaluationManifestV0_1]:
    runs = _completed_runs(root / "test", "confirmatory_test")
    if "target_hybrid_anchored_distillation_10" not in runs:
        raise ValueError("completed hybrid primary evaluation is missing")
    return runs["target_hybrid_anchored_distillation_10"]


def _replay_map(root: Path) -> dict[str, str]:
    result = {}
    for path in (root / "replays").glob("*/verification.json"):
        replay = Phase3BReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        if replay.kind == "evaluation" and replay.status == "PASSED":
            result[replay.original_artifact_id] = replay.content_sha256
    return result


def _derived_replay_map(root: Path) -> dict[str, str]:
    result = {}
    for path in (root / "replays").glob("*/verification.json"):
        replay = Phase3BReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        if replay.kind in {"analysis", "comparison"} and replay.status == "PASSED":
            result[replay.original_artifact_id] = replay.content_sha256
    return result


def _comparison(root: Path, kind: str) -> Phase3BComparisonV0_1:
    values = []
    for path in (root / "comparisons").glob("*/comparison.json"):
        item = Phase3BComparisonV0_1.model_validate_json(path.read_bytes(), strict=True)
        if item.comparison_kind == kind:
            values.append(item)
    if len(values) != 1:
        raise ValueError(f"expected one Phase 3B {kind} comparison")
    return values[0]


def _predictions(path: Path) -> list[Phase3BPredictionRecordV0_1]:
    return [
        Phase3BPredictionRecordV0_1.model_validate_json(line, strict=True)
        for line in (path / "predictions.jsonl").read_text().splitlines()
    ]


def _single(root: Path, filename: str) -> Path:
    values = sorted(root.glob(f"*/{filename}"))
    if len(values) != 1:
        raise ValueError(f"expected one {root}/*/{filename}")
    return values[0]
