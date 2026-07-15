"""Replay, comparisons, analysis, and independent recovery/distribution decisions."""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import verify_reference, write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.day2.schemas import Day2ComparisonV0_1
from inheritbench.day3.schemas import SyntheticDatasetManifestV0_1
from inheritbench.day3_matched.baseline import find_baseline
from inheritbench.day3_matched.config import (
    config_sha256,
    load_experiment_config,
    load_method_config,
    load_pool_config,
    resolve,
)
from inheritbench.day3_matched.distribution import (
    _local_snapshot,
    audit_distribution,
    audit_leakage,
    build_fingerprint,
    find_fingerprint,
)
from inheritbench.day3_matched.evaluation import (
    find_test_run,
    replay_evaluation,
)
from inheritbench.day3_matched.filtering import (
    filter_teacher_outputs,
    find_schedule,
    find_synthetic_dataset,
    freeze_schedule,
)
from inheritbench.day3_matched.schemas import (
    Day3RecoveryDecisionV0_1,
    MatchedDistributionDecisionV0_1,
    MatchedFailureAnalysisV0_1,
    MatchedMethodComparisonV0_1,
    MatchedPublicationManifestV0_1,
    MatchedReplayVerificationV0_1,
    MatchedSyntheticDatasetManifestV0_1,
    MatchedTeacherPredictionV0_1,
    MatchedTeacherRunManifestV0_1,
    MatchedTrainingRunManifestV0_1,
    ReplayKind,
    SyntheticAttemptComparisonV0_1,
)
from inheritbench.day3_matched.training import find_checkpoint_decision
from inheritbench.evaluation.parser import parse_action_contract


def analyze_failures(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    dataset_path, dataset = find_synthetic_dataset(experiment_path, require_completed=False)
    filter_records = [
        json.loads(line)
        for line in (dataset_path / "filter_records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    teacher_rejections = Counter(
        item["primary_rejection_reason"]
        for item in filter_records
        if item["primary_rejection_reason"] is not None
    )
    test_categories: Counter[str] = Counter()
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    source_hashes = [dataset.content_sha256]
    test_manifest = None
    try:
        test_path, found_test, _ = find_test_run(experiment_path)
    except ValueError:
        pass
    else:
        test_manifest = found_test
        source_hashes.append(found_test.content_sha256)
        for line in (test_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
            prediction = json.loads(line)
            categories = _test_failure_categories(prediction)
            for category in categories:
                test_categories[category] += 1
                grouped[f"family:{prediction['scenario_family']}"][category] += 1
                grouped[f"archetype:{prediction['archetype']}"][category] += 1
                grouped[f"expected_decision:{prediction['expected_contract']['decision']}"][
                    category
                ] += 1
    identity = content_sha256(
        {
            "dataset": dataset.content_sha256,
            "test": test_manifest.content_sha256 if test_manifest else None,
            "teacher_rejections": teacher_rejections,
            "test_categories": test_categories,
        }
    )
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "day3-matched-failure-analysis-v0.1",
        "analysis_id": f"day3-matched-failure-analysis-{identity[:16]}",
        "teacher_rejections": dict(sorted(teacher_rejections.items())),
        "test_failure_categories": dict(sorted(test_categories.items())),
        "breakdowns": {
            name: dict(sorted(values.items())) for name, values in sorted(grouped.items())
        },
        "source_artifact_sha256s": source_hashes,
        "created_at": created_at,
    }
    analysis = MatchedFailureAnalysisV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"analysis_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    destination = root / "failure-analysis" / analysis.analysis_id
    if destination.exists():
        stored = MatchedFailureAnalysisV0_1.model_validate_json(
            (destination / "analysis.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != analysis.content_sha256:
            raise ValueError("existing matched failure analysis differs")
        return destination
    return write_atomic_bundle(
        root / "failure-analysis",
        analysis.analysis_id,
        {"analysis.json": canonical_json_bytes(analysis) + b"\n"},
    )


def build_attempt_comparison(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    _, baseline = find_baseline(experiment_path)
    original_path = (
        resolve(experiment_path, experiment.original_day3_artifact_root)
        / "synthetic-data"
        / "day3-synthetic-dataset-9d186a0dde24549f"
    )
    original = SyntheticDatasetManifestV0_1.model_validate_json(
        (original_path / "manifest.json").read_bytes(), strict=True
    )
    original_rejections = _rejection_counts(original_path / "rejected.jsonl")
    _, matched = find_synthetic_dataset(experiment_path, require_completed=False)
    matched_path = root / "synthetic-data" / matched.dataset_id
    matched_rejections = _rejection_counts(matched_path / "rejected.jsonl")
    rows = [
        {
            "attempt_id": "independent_pool_attempt",
            "candidate_distribution": "independent_procedural",
            "status": "TERMINAL_NEGATIVE",
            "candidate_count": original.candidate_count,
            "accepted_count": original.accepted_count,
            "rejected_count": original.rejected_count,
            "selected_count": original.selected_count,
            "acceptance_rate": original.accepted_count / original.candidate_count,
            "rejection_categories": original_rejections,
            "validation": None,
            "test": None,
            "dataset_sha256": original.content_sha256,
        },
        {
            "attempt_id": "distribution_matched_attempt",
            "candidate_distribution": "frozen_train_distribution_matched",
            "status": matched.status,
            "candidate_count": matched.candidate_count,
            "accepted_count": matched.accepted_count,
            "rejected_count": matched.rejected_count,
            "selected_count": matched.selected_count,
            "acceptance_rate": matched.accepted_count / matched.candidate_count,
            "rejection_categories": matched_rejections,
            "validation": _checkpoint_status(experiment_path),
            "test": _test_status(experiment_path),
            "dataset_sha256": matched.content_sha256,
        },
    ]
    identity = content_sha256(rows)
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "day3-synthetic-attempt-comparison-v0.1",
        "comparison_id": f"day3-matched-attempt-comparison-{identity[:16]}",
        "status": "COMPLETED",
        "rows": rows,
        "historical_baseline_sha256": baseline.content_sha256,
        "matched_dataset_sha256": matched.content_sha256,
        "created_at": created_at,
    }
    comparison = SyntheticAttemptComparisonV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"comparison_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    destination = root / "comparisons" / comparison.comparison_id
    if destination.exists():
        stored = SyntheticAttemptComparisonV0_1.model_validate_json(
            (destination / "attempt_comparison.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != comparison.content_sha256:
            raise ValueError("existing attempt comparison differs")
        return destination
    return write_atomic_bundle(
        root / "comparisons",
        comparison.comparison_id,
        {"attempt_comparison.json": canonical_json_bytes(comparison) + b"\n"},
    )


def build_method_comparison(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    day2_path = next((Path.cwd() / "artifacts/day2/comparisons").glob("*/comparison.json"))
    day2 = Day2ComparisonV0_1.model_validate_json(day2_path.read_bytes(), strict=True)
    _test_path, test, summary = find_test_run(experiment_path)
    test_replay = _single_replay(root, "evaluation", test.run_id)
    analysis_path = analyze_failures(experiment_path)
    analysis = MatchedFailureAnalysisV0_1.model_validate_json(
        (analysis_path / "analysis.json").read_bytes(), strict=True
    )
    attempt_path = build_attempt_comparison(experiment_path)
    attempt = SyntheticAttemptComparisonV0_1.model_validate_json(
        (attempt_path / "attempt_comparison.json").read_bytes(), strict=True
    )
    _, decision = find_checkpoint_decision(experiment_path)
    if decision.status != "SELECTED" or decision.selected_adapter is None:
        raise ValueError("method comparison requires a selected matched adapter")
    training = _single_training(root, decision.training_run_id)
    _, schedule = find_schedule(experiment_path)
    _, dataset = find_synthetic_dataset(experiment_path)
    source_row = next(row for row in day2.rows if row.method_id == "source_adapted_full")
    source_semantic = _row_metric(source_row.metrics, "semantic_decision_score_v0")
    source_strict = _row_metric(source_row.metrics, "strict_contract_score_v0")
    semantic = summary.aggregate_metrics["semantic_decision_score_v0"].mean or 0.0
    strict = summary.aggregate_metrics["strict_contract_score_v0"].mean or 0.0
    matched_row = {
        "method_id": "target_synthetic_distillation_matched",
        "status": "COMPLETED",
        "evaluation_run_id": test.run_id,
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
            "direct_original_labels": 0,
            "upstream_original_labels": 224,
            "example_exposures": schedule.example_exposures,
            "processed_tokens": schedule.processed_tokens,
            "target_processed_tokens": schedule.target_processed_tokens,
            "budget_ratio": schedule.budget_ratio,
            "trainable_parameters": training.trainable_parameters,
            "adapter_bytes": decision.selected_adapter.total_bytes,
            "optimizer_steps": training.optimizer_steps_completed,
            "duration_seconds": training.duration_seconds,
            "device": training.resolved_device,
            "dtype": training.resolved_dtype,
            "seed": schedule.seed,
            "schedule_sha256": schedule.content_sha256,
        },
        "strict_retention": None if source_strict == 0 else strict / source_strict,
        "semantic_retention": None if source_semantic == 0 else semantic / source_semantic,
        "retention_error": (
            "ZERO_DENOMINATOR" if source_strict == 0 or source_semantic == 0 else None
        ),
    }
    rows = [row.model_dump(mode="json") for row in day2.rows] + [matched_row]
    accounting = _accounting(root, dataset, schedule, training, test)
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "day2": day2.content_sha256,
            "test": test.content_sha256,
            "attempt": attempt.content_sha256,
            "analysis": analysis.content_sha256,
        }
    )
    payload = {
        "schema_version": "day3-matched-method-comparison-v0.1",
        "comparison_id": f"day3-matched-method-comparison-{identity[:16]}",
        "status": "COMPLETED",
        "day2_comparison_sha256": day2.content_sha256,
        "attempt_comparison_sha256": attempt.content_sha256,
        "dataset_sha256": day2.dataset_sha256,
        "test_subset_sha256": day2.test_subset_sha256,
        "evaluator_version": "v0",
        "rows": rows,
        "accounting": accounting,
        "failure_analysis_sha256": analysis.content_sha256,
        "created_at": created_at,
    }
    comparison = MatchedMethodComparisonV0_1.model_validate(
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
        comparison.comparison_id,
        {"method_comparison.json": canonical_json_bytes(comparison) + b"\n"},
    )


def replay_artifact(experiment_path: Path, kind: ReplayKind, artifact: Path) -> Path:
    started = time.perf_counter()
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    original_id: str
    records: int
    if kind == "evaluation":
        return replay_evaluation(artifact, root / "replays")
    if kind == "fingerprint":
        _, stored_fingerprint = find_fingerprint(experiment_path)
        pool_config = load_pool_config(resolve(experiment_path, experiment.pool_config_path))
        source = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
        from transformers import AutoTokenizer

        auto_tokenizer: Any = AutoTokenizer
        tokenizer: Any = auto_tokenizer.from_pretrained(
            _local_snapshot(source.tokenizer_id, source.tokenizer_revision),
            trust_remote_code=False,
            local_files_only=True,
        )
        rebuilt = build_fingerprint(experiment_path, pool_config, tokenizer)
        if rebuilt.content_sha256 != stored_fingerprint.content_sha256:
            raise ValueError("fingerprint replay mismatch")
        original_id = stored_fingerprint.fingerprint_id
        records = stored_fingerprint.train_records
    elif kind in {"distribution", "leakage"}:
        phase: Literal["initial", "expansion"] = (
            "expansion" if "expansion" in artifact.name else "initial"
        )
        if kind == "distribution":
            audit_distribution(experiment_path, phase)
        else:
            audit_leakage(experiment_path, phase)
        original_id = artifact.name
        records = json.loads((artifact / "manifest.json").read_text())["candidate_count"]
    elif kind == "teacher":
        manifest = MatchedTeacherRunManifestV0_1.model_validate_json(
            (artifact / "manifest.json").read_bytes(), strict=True
        )
        verify_reference(artifact, manifest.prediction_artifact)
        predictions = _read_jsonl(artifact / "predictions.jsonl", MatchedTeacherPredictionV0_1)
        for item in predictions:
            if (
                item.status == "COMPLETED"
                and parse_action_contract(item.raw_output) != item.parser_result
            ):
                raise ValueError("matched teacher parser replay mismatch")
        original_id = manifest.run_id
        records = len(predictions)
    elif kind == "filter":
        stored_dataset = MatchedSyntheticDatasetManifestV0_1.model_validate_json(
            (artifact / "manifest.json").read_bytes(), strict=True
        )
        rebuilt_path, _ = filter_teacher_outputs(experiment_path)
        rebuilt_dataset = MatchedSyntheticDatasetManifestV0_1.model_validate_json(
            (rebuilt_path / "manifest.json").read_bytes(), strict=True
        )
        if rebuilt_dataset.content_sha256 != stored_dataset.content_sha256:
            raise ValueError("matched filter replay mismatch")
        original_id = stored_dataset.dataset_id
        records = stored_dataset.candidate_count
    elif kind == "schedule":
        stored_path, stored_schedule = find_schedule(experiment_path)
        rebuilt_path = freeze_schedule(experiment_path)
        if rebuilt_path != stored_path:
            raise ValueError("matched schedule replay path mismatch")
        original_id = stored_schedule.schedule_id
        records = len(stored_schedule.items)
    elif kind == "failure_analysis":
        stored_analysis = MatchedFailureAnalysisV0_1.model_validate_json(
            (artifact / "analysis.json").read_bytes(), strict=True
        )
        rebuilt_path = analyze_failures(experiment_path)
        rebuilt_analysis = MatchedFailureAnalysisV0_1.model_validate_json(
            (rebuilt_path / "analysis.json").read_bytes(), strict=True
        )
        if rebuilt_analysis.content_sha256 != stored_analysis.content_sha256:
            raise ValueError("matched failure-analysis replay mismatch")
        original_id = stored_analysis.analysis_id
        records = sum(stored_analysis.teacher_rejections.values())
    elif kind == "attempt_comparison":
        stored_attempt = SyntheticAttemptComparisonV0_1.model_validate_json(
            (artifact / "attempt_comparison.json").read_bytes(), strict=True
        )
        rebuilt_path = build_attempt_comparison(experiment_path)
        rebuilt_attempt = SyntheticAttemptComparisonV0_1.model_validate_json(
            (rebuilt_path / "attempt_comparison.json").read_bytes(), strict=True
        )
        if rebuilt_attempt.content_sha256 != stored_attempt.content_sha256:
            raise ValueError("attempt comparison replay mismatch")
        original_id = stored_attempt.comparison_id
        records = len(stored_attempt.rows)
    elif kind == "method_comparison":
        stored_method = MatchedMethodComparisonV0_1.model_validate_json(
            (artifact / "method_comparison.json").read_bytes(), strict=True
        )
        _verify_method_comparison_sources(experiment_path, stored_method)
        original_id = stored_method.comparison_id
        records = len(stored_method.rows)
    elif kind == "training":
        stored_training = MatchedTrainingRunManifestV0_1.model_validate_json(
            (artifact / "manifest.json").read_bytes(), strict=True
        )
        _, schedule = find_schedule(experiment_path)
        if stored_training.schedule_sha256 != schedule.content_sha256:
            raise ValueError("training schedule lineage mismatch")
        original_id = stored_training.run_id
        records = stored_training.optimizer_steps_completed
    else:
        stored_decision = Day3RecoveryDecisionV0_1.model_validate_json(
            (artifact / "decision.json").read_bytes(), strict=True
        )
        _verify_recovery_decision(experiment_path, stored_decision)
        original_id = stored_decision.decision_id
        records = len(stored_decision.evidence_sha256s)
    created_at = datetime.now(UTC)
    replay_id = f"day3-matched-replay-{kind}-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day3-matched-replay-verification-v0.1",
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
    verification = MatchedReplayVerificationV0_1.model_validate(
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


def finalize_recovery(experiment_path: Path, blocked_reason: str | None = None) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if blocked_reason is not None:
        _, baseline = find_baseline(experiment_path)
        return _write_recovery(
            root,
            "RECOVERY_BLOCKED",
            "DAY4_BLOCKED",
            blocked_reason,
            "NOT_AVAILABLE",
            [baseline.content_sha256],
        )
    _, dataset = find_synthetic_dataset(experiment_path, require_completed=False)
    integrity_evidence = _required_integrity_replays(experiment_path, dataset)
    analysis_path, analysis = _single_analysis(root)
    del analysis_path
    analysis_replay = _single_replay(root, "failure_analysis", analysis.analysis_id)
    attempt_path = build_attempt_comparison(experiment_path)
    attempt = SyntheticAttemptComparisonV0_1.model_validate_json(
        (attempt_path / "attempt_comparison.json").read_bytes(), strict=True
    )
    attempt_replay = _single_replay(root, "attempt_comparison", attempt.comparison_id)
    evidence = [
        dataset.content_sha256,
        *integrity_evidence,
        analysis.content_sha256,
        analysis_replay.content_sha256,
        attempt.content_sha256,
        attempt_replay.content_sha256,
    ]
    if dataset.status == "TERMINAL_NEGATIVE":
        return _write_recovery(
            root,
            "RECOVERY_TERMINAL_NEGATIVE",
            "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT",
            dataset.failure_code or "INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES",
            attempt.comparison_id,
            evidence,
            dataset_id=dataset.dataset_id,
        )
    training = _only_training(root)
    _, decision = find_checkpoint_decision(experiment_path)
    evidence.extend([training.content_sha256, decision.content_sha256])
    if decision.status == "TERMINAL_NEGATIVE":
        return _write_recovery(
            root,
            "RECOVERY_TERMINAL_NEGATIVE",
            "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT",
            decision.failure_code or "NO_SAFETY_ELIGIBLE_CHECKPOINT",
            attempt.comparison_id,
            evidence,
            dataset_id=dataset.dataset_id,
            training_run_id=training.run_id,
            checkpoint_decision_id=decision.decision_id,
        )
    _, test, summary = find_test_run(experiment_path)
    evaluation_replay = _single_replay(root, "evaluation", test.run_id)
    comparison_path, comparison = _single_method_comparison(root)
    del comparison_path
    comparison_replay = _single_replay(root, "method_comparison", comparison.comparison_id)
    if training.status != "COMPLETED":
        raise ValueError("recovery completion requires completed target training")
    if test.status != "COMPLETED" or summary.prediction_counts.get("completed") != 32:
        raise ValueError("recovery completion requires 32 completed held-out predictions")
    evidence.extend(
        [
            test.content_sha256,
            evaluation_replay.content_sha256,
            comparison.content_sha256,
            comparison_replay.content_sha256,
        ]
    )
    return _write_recovery(
        root,
        "RECOVERY_SCIENTIFICALLY_COMPLETED",
        "DAY4_UNBLOCKED",
        "ALL_RECOVERY_SCIENTIFIC_GATES_PASSED",
        attempt.comparison_id,
        evidence,
        dataset_id=dataset.dataset_id,
        training_run_id=training.run_id,
        checkpoint_decision_id=decision.decision_id,
        test_run_id=test.run_id,
        method_comparison_id=comparison.comparison_id,
    )


def _required_integrity_replays(
    experiment_path: Path, dataset: MatchedSyntheticDatasetManifestV0_1
) -> list[str]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    _, fingerprint = find_fingerprint(experiment_path)
    values = [
        _single_replay(root, "fingerprint", fingerprint.fingerprint_id).content_sha256,
        _single_replay(root, "filter", dataset.dataset_id).content_sha256,
    ]
    for pool_id in dataset.pool_ids:
        values.extend(
            [
                _single_replay(root, "distribution", pool_id).content_sha256,
                _single_replay(root, "leakage", pool_id).content_sha256,
            ]
        )
    for run_id in dataset.teacher_run_ids:
        values.append(_single_replay(root, "teacher", run_id).content_sha256)
    return values


def finalize_distribution(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    _, recovery = _single_recovery(root)
    publications = [
        MatchedPublicationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "publications").glob("*/publication.json"))
    ]
    verified = [item for item in publications if item.status == "PUBLISHED_VERIFIED"]
    blocked = [item for item in publications if item.status == "PUBLICATION_BLOCKED"]
    if verified:
        status = "PUBLISHED_VERIFIED"
        publication = verified[-1]
    elif any(item.attempt == 2 for item in blocked):
        status = "PUBLICATION_BLOCKED"
        publication = [item for item in blocked if item.attempt == 2][-1]
    elif blocked:
        raise ValueError("publication retry remains available")
    else:
        status = "NOT_ATTEMPTED"
        publication = None
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "recovery": recovery.content_sha256,
            "publication": publication.content_sha256 if publication else None,
        }
    )
    payload = {
        "schema_version": "day3-matched-distribution-decision-v0.1",
        "decision_id": f"day3-matched-distribution-decision-{identity[:16]}",
        "publication_status": status,
        "recovery_decision_sha256": recovery.content_sha256,
        "publication_sha256": publication.content_sha256 if publication else None,
        "day4_gate": recovery.day4_gate,
        "created_at": created_at,
    }
    decision = MatchedDistributionDecisionV0_1.model_validate(
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
        decision.decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def _write_recovery(
    root: Path,
    status: Literal[
        "RECOVERY_SCIENTIFICALLY_COMPLETED", "RECOVERY_TERMINAL_NEGATIVE", "RECOVERY_BLOCKED"
    ],
    gate: Literal[
        "DAY4_UNBLOCKED", "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT", "DAY4_BLOCKED"
    ],
    reason: str,
    attempt_comparison_id: str,
    evidence: list[str],
    *,
    dataset_id: str | None = None,
    training_run_id: str | None = None,
    checkpoint_decision_id: str | None = None,
    test_run_id: str | None = None,
    method_comparison_id: str | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {"status": status, "gate": gate, "reason": reason, "evidence": evidence}
    )
    payload = {
        "schema_version": "day3-recovery-decision-v0.1",
        "decision_id": f"day3-recovery-decision-{identity[:16]}",
        "recovery_status": status,
        "day4_gate": gate,
        "reason_code": reason,
        "dataset_id": dataset_id,
        "training_run_id": training_run_id,
        "checkpoint_decision_id": checkpoint_decision_id,
        "test_run_id": test_run_id,
        "attempt_comparison_id": attempt_comparison_id,
        "method_comparison_id": method_comparison_id,
        "evidence_sha256s": evidence,
        "further_day3_attempts_allowed": False,
        "automatic_day4_started": False,
        "created_at": created_at,
    }
    decision = Day3RecoveryDecisionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"decision_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    destination = root / "recovery-decisions" / decision.decision_id
    if destination.exists():
        stored = Day3RecoveryDecisionV0_1.model_validate_json(
            (destination / "decision.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != decision.content_sha256:
            raise ValueError("existing recovery decision differs")
        return destination
    return write_atomic_bundle(
        root / "recovery-decisions",
        decision.decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def _accounting(
    root: Path, dataset: Any, schedule: Any, training: Any, test: Any
) -> dict[str, Any]:
    teacher_runs = [
        MatchedTeacherRunManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "teacher-runs").glob("*/manifest.json"))
    ]
    return {
        "original_labels_directly_used_by_target": 0,
        "original_labels_used_upstream_to_train_teacher": 224,
        "synthetic_candidate_inputs_generated": dataset.candidate_count,
        "teacher_outputs_generated": sum(item.completed_outputs for item in teacher_runs),
        "synthetic_outputs_accepted": dataset.accepted_count,
        "synthetic_outputs_rejected": dataset.rejected_count,
        "synthetic_examples_used_for_target_training": dataset.selected_count,
        "target_training_processed_tokens": schedule.processed_tokens,
        "teacher_generation_processed_tokens": sum(
            item.teacher_generation_processed_tokens for item in teacher_runs
        ),
        "teacher_generation_duration": sum(item.duration_seconds for item in teacher_runs),
        "target_training_duration": training.duration_seconds,
        "test_duration_seconds": (test.finished_at - test.created_at).total_seconds(),
        "source_teacher_upstream": {
            "original_labels": 224,
            "training_tokens": 379768,
            "training_duration_seconds": 437.86,
        },
    }


def _test_failure_categories(prediction: dict[str, Any]) -> list[str]:
    if prediction["status"] == "FAILED":
        return ["INFRASTRUCTURE_FAILURE"]
    categories = []
    parser = prediction.get("parser_result")
    metrics = prediction.get("metrics")
    if parser:
        categories.append(f"PARSER:{parser['classification']}")
    if metrics:
        if not metrics["semantic_decision_score_v0"]:
            categories.append("CONTRACT_MISMATCH")
        for name in (
            "false_action",
            "unauthorized_action",
            "approval_bypass",
            "hallucinated_arguments",
        ):
            if metrics[name] is True:
                categories.append(f"SAFETY:{name}")
    return categories


def _rejection_counts(path: Path) -> dict[str, int]:
    counts = Counter(
        json.loads(line)["primary_rejection_reason"]
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    return dict(sorted(counts.items()))


def _checkpoint_status(experiment_path: Path) -> dict[str, Any] | None:
    try:
        _, decision = find_checkpoint_decision(experiment_path)
    except ValueError:
        return None
    return {
        "status": decision.status,
        "selected_checkpoint_id": decision.selected_checkpoint_id,
        "decision_sha256": decision.content_sha256,
    }


def _test_status(experiment_path: Path) -> dict[str, Any] | None:
    try:
        _, manifest, summary = find_test_run(experiment_path)
    except ValueError:
        return None
    return {
        "status": manifest.status,
        "run_id": manifest.run_id,
        "completed": summary.prediction_counts.get("completed"),
        "manifest_sha256": manifest.content_sha256,
    }


def _row_metric(metrics: Any, name: str) -> float:
    value = metrics["aggregate"][name]
    return float(value["mean"] or 0.0)


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        return [schema.model_validate_json(line, strict=True) for line in handle]


def _single_training(root: Path, run_id: str) -> MatchedTrainingRunManifestV0_1:
    return MatchedTrainingRunManifestV0_1.model_validate_json(
        (root / "training" / run_id / "manifest.json").read_bytes(), strict=True
    )


def _only_training(root: Path) -> MatchedTrainingRunManifestV0_1:
    paths = sorted((root / "training").glob("*/manifest.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one completed matched training run, found {len(paths)}")
    return MatchedTrainingRunManifestV0_1.model_validate_json(paths[0].read_bytes(), strict=True)


def _single_analysis(root: Path) -> tuple[Path, MatchedFailureAnalysisV0_1]:
    paths = sorted((root / "failure-analysis").glob("*/analysis.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one matched failure analysis, found {len(paths)}")
    return paths[0].parent, MatchedFailureAnalysisV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def _single_method_comparison(root: Path) -> tuple[Path, MatchedMethodComparisonV0_1]:
    paths = sorted((root / "comparisons").glob("*/method_comparison.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one matched method comparison, found {len(paths)}")
    return paths[0].parent, MatchedMethodComparisonV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def _single_recovery(root: Path) -> tuple[Path, Day3RecoveryDecisionV0_1]:
    paths = sorted((root / "recovery-decisions").glob("*/decision.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one recovery decision, found {len(paths)}")
    return paths[0].parent, Day3RecoveryDecisionV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def _single_replay(root: Path, kind: str, original_id: str) -> MatchedReplayVerificationV0_1:
    values = [
        MatchedReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "replays").glob("*/verification.json"))
    ]
    matches = [
        item for item in values if item.kind == kind and item.original_artifact_id == original_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {kind} replay for {original_id}, found {len(matches)}")
    return matches[0]


def _verify_method_comparison_sources(
    experiment_path: Path, comparison: MatchedMethodComparisonV0_1
) -> None:
    day2_path = next((Path.cwd() / "artifacts/day2/comparisons").glob("*/comparison.json"))
    day2 = Day2ComparisonV0_1.model_validate_json(day2_path.read_bytes(), strict=True)
    if day2.content_sha256 != comparison.day2_comparison_sha256:
        raise ValueError("Day 2 comparison hash mismatch")
    _, test, _ = find_test_run(experiment_path)
    if not any(row.get("evaluation_run_id") == test.run_id for row in comparison.rows):
        raise ValueError("matched method comparison does not reference the frozen test")


def _verify_recovery_decision(experiment_path: Path, decision: Day3RecoveryDecisionV0_1) -> None:
    root = resolve(experiment_path, load_experiment_config(experiment_path).artifact_root)
    attempt_paths = sorted((root / "comparisons").glob("*/attempt_comparison.json"))
    if not attempt_paths:
        raise ValueError("recovery decision lacks attempt-comparison evidence")
    attempt = SyntheticAttemptComparisonV0_1.model_validate_json(
        attempt_paths[-1].read_bytes(), strict=True
    )
    if attempt.comparison_id != decision.attempt_comparison_id:
        raise ValueError("recovery decision attempt comparison mismatch")
