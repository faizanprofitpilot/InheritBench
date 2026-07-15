"""Unchanged strict filtering, selection, and synthetic schedule freezing."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    sha256_text,
)
from inheritbench.artifacts.store import artifact_reference, write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.day3.filtering import _filter_one as day3_filter_one
from inheritbench.day3.filtering import training_sequence_length
from inheritbench.day3_matched.config import (
    load_experiment_config,
    load_method_config,
    load_pool_config,
    resolve,
)
from inheritbench.day3_matched.distribution import (
    _local_snapshot,
    find_pool,
    load_candidates,
    load_oracles,
    load_pool_manifest,
)
from inheritbench.day3_matched.schemas import (
    MatchedFilterDecisionV0_1,
    MatchedScheduleItem,
    MatchedSyntheticDatasetManifestV0_1,
    MatchedTeacherPredictionV0_1,
    MatchedTeacherRunManifestV0_1,
    MatchedTrainingExampleV0_1,
    MatchedTrainingScheduleV0_1,
)
from inheritbench.day3_matched.teacher import find_teacher_run

_DATASET_EXCLUSIONS = {"dataset_id", "created_at", "content_sha256"}


def filter_teacher_outputs(experiment_path: Path) -> tuple[Path, Path]:
    experiment = load_experiment_config(experiment_path)
    pool_config = load_pool_config(resolve(experiment_path, experiment.pool_config_path))
    phases: list[Literal["initial", "expansion"]] = ["initial"]
    try:
        find_pool(experiment_path, "expansion")
    except ValueError:
        pass
    else:
        phases.append("expansion")
    candidates: dict[str, Any] = {}
    oracles: dict[str, Any] = {}
    predictions: dict[str, MatchedTeacherPredictionV0_1] = {}
    pools = []
    runs: list[MatchedTeacherRunManifestV0_1] = []
    for phase in phases:
        pool_path = find_pool(experiment_path, phase)
        pool = load_pool_manifest(pool_path)
        run_path, run = find_teacher_run(experiment_path, phase)
        if run.status != "COMPLETED" or run.pool_content_sha256 != pool.content_sha256:
            raise ValueError(f"teacher run for {phase} is not complete for the frozen pool")
        phase_candidates = load_candidates(pool_path)
        phase_oracles = load_oracles(pool_path)
        phase_predictions = _terminal_predictions(
            _read_jsonl(run_path / "predictions.jsonl", MatchedTeacherPredictionV0_1)
        )
        if set(phase_predictions) != {item.candidate_id for item in phase_candidates}:
            raise ValueError(f"teacher run for {phase} lacks terminal candidate outputs")
        candidates.update({item.candidate_id: item for item in phase_candidates})
        oracles.update({item.candidate_id: item for item in phase_oracles})
        predictions.update(phase_predictions)
        pools.append(pool)
        runs.append(run)
    target = load_model_config(resolve(experiment_path, experiment.target_model_config_path))
    from transformers import AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        _local_snapshot(target.tokenizer_id, target.tokenizer_revision),
        trust_remote_code=False,
        local_files_only=True,
    )
    records = [
        _filter_one(
            candidates[candidate_id],
            oracles[candidate_id],
            predictions[candidate_id],
            tokenizer,
        )
        for candidate_id in sorted(candidates)
    ]
    accepted = [item for item in records if item.accepted]
    by_archetype: dict[tuple[str, str], list[MatchedFilterDecisionV0_1]] = defaultdict(list)
    for item in accepted:
        candidate = candidates[item.candidate_id]
        by_archetype[(candidate.scenario_family, candidate.archetype)].append(item)
    sufficient = len(by_archetype) == 16 and all(
        len(values) >= pool_config.selected_per_archetype for values in by_archetype.values()
    )
    selected_ids: set[str] = set()
    if sufficient:
        for values in by_archetype.values():
            selected_ids.update(
                item.candidate_id
                for item in sorted(values, key=lambda value: value.selection_rank)[
                    : pool_config.selected_per_archetype
                ]
            )
    records = [_with_selection(item, item.candidate_id in selected_ids) for item in records]
    accepted = [item for item in records if item.accepted]
    rejected = [item for item in records if not item.accepted]
    selected = [
        MatchedTrainingExampleV0_1(
            schema_version="day3-matched-training-example-v0.1",
            candidate=candidates[item.candidate_id],
            teacher_label=item.teacher_label or "",
            teacher_prediction_sha256=item.teacher_prediction_sha256,
            oracle_sha256=item.oracle_sha256,
        )
        for item in records
        if item.selected_for_training
    ]
    selected.sort(key=lambda item: item.candidate.candidate_id)
    status = (
        "COMPLETED"
        if sufficient
        else "NEEDS_EXPANSION"
        if phases == ["initial"]
        else "TERMINAL_NEGATIVE"
    )
    failure_code = (
        "INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES" if status == "TERMINAL_NEGATIVE" else None
    )
    if status == "COMPLETED" and len(selected) != 224:
        raise ValueError("matched selection did not produce exactly 224 records")
    all_bytes = canonical_jsonl_bytes(records, id_key="candidate_id")
    accepted_bytes = canonical_jsonl_bytes(accepted, id_key="candidate_id")
    rejected_bytes = canonical_jsonl_bytes(rejected, id_key="candidate_id")
    selected_bytes = canonical_jsonl_bytes(selected)
    identity = content_sha256(
        {
            "pools": [item.content_sha256 for item in pools],
            "teacher_runs": [item.content_sha256 for item in runs],
            "filter_records": [item.content_sha256 for item in records],
            "selected_ids": sorted(selected_ids),
        }
    )
    dataset_id = f"day3-matched-synthetic-dataset-{identity[:16]}"
    selected_counts = Counter(
        f"{item.candidate.scenario_family}:{item.candidate.archetype}" for item in selected
    )
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "day3-matched-synthetic-dataset-v0.1",
        "dataset_id": dataset_id,
        "attempt_id": "distribution_matched_attempt",
        "status": status,
        "failure_code": failure_code,
        "pool_ids": [item.pool_id for item in pools],
        "pool_sha256s": [item.content_sha256 for item in pools],
        "teacher_run_ids": [item.run_id for item in runs],
        "teacher_run_sha256s": [item.content_sha256 for item in runs],
        "distribution_audit_sha256s": [item.distribution_audit_sha256 for item in pools],
        "leakage_audit_sha256s": [item.leakage_audit_sha256 for item in pools],
        "filter_version": pool_config.filter_version,
        "candidate_count": len(records),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "selected_count": len(selected),
        "selected_per_archetype": dict(sorted(selected_counts.items())),
        "original_labels_directly_used_by_target": 0,
        "original_labels_used_upstream_to_train_teacher": 224,
        "accepted_artifact": artifact_reference(
            "accepted.jsonl", accepted_bytes, content_sha256=content_sha256(accepted)
        ).model_dump(mode="json"),
        "rejected_artifact": artifact_reference(
            "rejected.jsonl", rejected_bytes, content_sha256=content_sha256(rejected)
        ).model_dump(mode="json"),
        "selected_artifact": artifact_reference(
            "selected.jsonl", selected_bytes, content_sha256=content_sha256(selected)
        ).model_dump(mode="json"),
        "created_at": created_at,
    }
    manifest = MatchedSyntheticDatasetManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_DATASET_EXCLUSIONS),
        },
        strict=True,
    )
    root = resolve(experiment_path, experiment.artifact_root)
    dataset_root = root / "synthetic-data"
    destination = dataset_root / dataset_id
    if destination.exists():
        stored = MatchedSyntheticDatasetManifestV0_1.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != manifest.content_sha256:
            raise ValueError("existing matched synthetic dataset differs")
    else:
        destination = write_atomic_bundle(
            dataset_root,
            dataset_id,
            {
                "filter_records.jsonl": all_bytes,
                "accepted.jsonl": accepted_bytes,
                "rejected.jsonl": rejected_bytes,
                "selected.jsonl": selected_bytes,
                "manifest.json": canonical_json_bytes(manifest) + b"\n",
            },
        )
    filter_id = f"day3-matched-filter-{identity[:16]}"
    filter_root = root / "filtering"
    filter_path = filter_root / filter_id
    if not filter_path.exists():
        filter_path = write_atomic_bundle(
            filter_root,
            filter_id,
            {
                "filter_records.jsonl": all_bytes,
                "lineage.json": canonical_json_bytes(
                    {
                        "filter_id": filter_id,
                        "attempt_id": "distribution_matched_attempt",
                        "dataset_id": dataset_id,
                        "dataset_sha256": manifest.content_sha256,
                        "filter_version": pool_config.filter_version,
                    }
                )
                + b"\n",
            },
        )
    return destination, filter_path


def find_synthetic_dataset(
    experiment_path: Path, *, require_completed: bool = True
) -> tuple[Path, MatchedSyntheticDatasetManifestV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "synthetic-data"
    values = [
        (
            path,
            MatchedSyntheticDatasetManifestV0_1.model_validate_json(
                (path / "manifest.json").read_bytes(), strict=True
            ),
        )
        for path in sorted(root.glob("day3-matched-synthetic-dataset-*"))
    ]
    if require_completed:
        values = [item for item in values if item[1].status == "COMPLETED"]
    else:
        maximum_pools = max((len(item[1].pool_ids) for item in values), default=0)
        values = [item for item in values if len(item[1].pool_ids) == maximum_pools]
    if len(values) != 1:
        raise ValueError(f"expected one matching synthetic dataset, found {len(values)}")
    return values[0]


def freeze_schedule(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    method_path = resolve(experiment_path, experiment.method_config_path)
    method = load_method_config(method_path)
    dataset_path, dataset = find_synthetic_dataset(experiment_path)
    if dataset.status != "COMPLETED" or dataset.selected_count != 224:
        raise ValueError("a completed 224-record matched synthetic dataset is required")
    _validate_training_path(dataset_path)
    selected = _read_jsonl(dataset_path / "selected.jsonl", MatchedTrainingExampleV0_1)
    if any(
        not item.candidate.candidate_id.startswith("matched_synthetic_opsroute_v010_")
        for item in selected
    ):
        raise ValueError("matched training data contains a non-matched identifier")
    target = load_model_config(resolve(method_path, method.model_config_path))
    from transformers import AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        _local_snapshot(target.tokenizer_id, target.tokenizer_revision),
        trust_remote_code=False,
        local_files_only=True,
    )
    token_counts = {
        item.candidate.candidate_id: training_sequence_length(
            tokenizer, item.candidate, item.teacher_label
        )
        for item in selected
    }
    remaining = 272643
    items: list[MatchedScheduleItem] = []
    cycle = 0
    while remaining:
        added = False
        ordered = sorted(
            token_counts,
            key=lambda candidate_id: sha256_text(
                f"20260714:target_synthetic_distillation:cycle:{cycle}:{candidate_id}"
            ),
        )
        for candidate_id in ordered:
            tokens = token_counts[candidate_id]
            if tokens <= remaining:
                items.append(
                    MatchedScheduleItem(
                        cursor=len(items),
                        cycle=cycle,
                        candidate_id=candidate_id,
                        sequence_tokens=tokens,
                    )
                )
                remaining -= tokens
                added = True
        if not added:
            break
        cycle += 1
    exposures = Counter(item.candidate_id for item in items)
    processed = sum(item.sequence_tokens for item in items)
    optimizer_steps = math.ceil(len(items) / method.training.gradient_accumulation_steps)
    checkpoints = [
        math.ceil(optimizer_steps / 3),
        math.ceil(2 * optimizer_steps / 3),
        optimizer_steps,
    ]
    items_sha256 = content_sha256([item.model_dump(mode="json") for item in items])
    payload = {
        "schema_version": "day3-matched-training-schedule-v0.1",
        "schedule_id": f"day3-matched-schedule-{items_sha256[:16]}",
        "method_id": "target_synthetic_distillation_matched",
        "synthetic_dataset_sha256": dataset.content_sha256,
        "tokenizer_id": target.tokenizer_id,
        "tokenizer_revision": target.tokenizer_revision,
        "seed": 20260714,
        "target_processed_tokens": 272643,
        "processed_tokens": processed,
        "residual_tokens": 272643 - processed,
        "budget_ratio": processed / 272643,
        "unique_examples": 224,
        "example_exposures": len(items),
        "optimizer_steps": optimizer_steps,
        "warmup_steps": math.ceil(optimizer_steps * 0.05),
        "checkpoint_steps": checkpoints,
        "token_counts": dict(sorted(token_counts.items())),
        "per_example_exposures": dict(sorted(exposures.items())),
        "items": [item.model_dump(mode="json") for item in items],
    }
    schedule = MatchedTrainingScheduleV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
    root = resolve(experiment_path, experiment.artifact_root) / "schedules"
    destination = root / schedule.schedule_id
    if destination.exists():
        stored = MatchedTrainingScheduleV0_1.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != schedule.content_sha256:
            raise ValueError("existing matched schedule differs")
        return destination
    return write_atomic_bundle(
        root,
        schedule.schedule_id,
        {"manifest.json": canonical_json_bytes(schedule) + b"\n"},
    )


def find_schedule(experiment_path: Path) -> tuple[Path, MatchedTrainingScheduleV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "schedules"
    matches = sorted(root.glob("day3-matched-schedule-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one matched schedule, found {len(matches)}")
    value = MatchedTrainingScheduleV0_1.model_validate_json(
        (matches[0] / "manifest.json").read_bytes(), strict=True
    )
    return matches[0], value


def _filter_one(
    candidate: Any,
    oracle: Any,
    prediction: MatchedTeacherPredictionV0_1,
    tokenizer: Any,
) -> MatchedFilterDecisionV0_1:
    original = day3_filter_one(candidate, oracle, cast(Any, prediction), tokenizer)
    payload = {
        "schema_version": "day3-matched-filter-record-v0.1",
        **original.model_dump(mode="json", exclude={"schema_version", "content_sha256"}),
    }
    return MatchedFilterDecisionV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _with_selection(record: MatchedFilterDecisionV0_1, selected: bool) -> MatchedFilterDecisionV0_1:
    payload = record.model_dump(mode="json", exclude={"content_sha256"})
    payload["selected_for_training"] = selected
    return MatchedFilterDecisionV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _terminal_predictions(
    values: list[MatchedTeacherPredictionV0_1],
) -> dict[str, MatchedTeacherPredictionV0_1]:
    grouped: dict[str, list[MatchedTeacherPredictionV0_1]] = defaultdict(list)
    for value in values:
        grouped[value.candidate_id].append(value)
    result = {}
    for candidate_id, attempts in grouped.items():
        completed = [item for item in attempts if item.status == "COMPLETED"]
        result[candidate_id] = completed[-1] if completed else attempts[-1]
    return result


def _validate_training_path(dataset_path: Path) -> None:
    resolved = dataset_path.resolve()
    allowed_root = (Path.cwd() / "artifacts/day3-matched/synthetic-data").resolve()
    if not resolved.is_relative_to(allowed_root):
        raise ValueError("target training may open only matched synthetic-data artifacts")
    lowered = str(resolved).lower()
    if "oracle" in lowered or "data/opsroute" in lowered or "artifacts/day3/" in lowered:
        raise ValueError("target training cannot access original labels or oracle paths")


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        return [schema.model_validate_json(line, strict=True) for line in handle]
