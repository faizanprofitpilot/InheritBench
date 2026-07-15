"""Strict teacher filtering and deterministic synthetic-set selection."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    sha256_text,
)
from inheritbench.artifacts.store import artifact_reference, write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.day3.config import (
    load_experiment_config,
    load_method_config,
    load_pool_config,
    resolve,
)
from inheritbench.day3.pool import find_pool, load_candidates, load_oracles
from inheritbench.day3.schemas import (
    Day3ScheduleItem,
    SyntheticCandidateInputV0_1,
    SyntheticDatasetManifestV0_1,
    SyntheticFilterRecordV0_1,
    SyntheticOracleRecordV0_1,
    SyntheticPoolManifestV0_1,
    SyntheticTrainingExampleV0_1,
    SyntheticTrainingScheduleV0_1,
    TeacherPredictionV0_1,
    TeacherRunManifestV0_1,
)
from inheritbench.evaluation.metrics import score_prediction
from inheritbench.models.prompts import build_messages, render_prompt

_DATASET_EXCLUSIONS = {"dataset_id", "created_at", "content_sha256"}


def filter_teacher_outputs(experiment_path: Path) -> tuple[Path, Path]:
    experiment = load_experiment_config(experiment_path)
    pool_config = load_pool_config(resolve(experiment_path, experiment.pool_config_path))
    phases = ["initial"]
    try:
        find_pool(experiment_path, "expansion")
    except ValueError:
        pass
    else:
        phases.append("expansion")

    candidates: dict[str, SyntheticCandidateInputV0_1] = {}
    oracles: dict[str, SyntheticOracleRecordV0_1] = {}
    predictions: dict[str, TeacherPredictionV0_1] = {}
    pool_manifests: list[SyntheticPoolManifestV0_1] = []
    run_manifests: list[TeacherRunManifestV0_1] = []
    for phase in phases:
        pool_path = find_pool(experiment_path, phase)  # type: ignore[arg-type]
        pool = SyntheticPoolManifestV0_1.model_validate_json(
            (pool_path / "manifest.json").read_bytes(), strict=True
        )
        run_path, run = _find_teacher_run(experiment_path, phase)
        if run.status != "COMPLETED" or run.pool_content_sha256 != pool.content_sha256:
            raise ValueError(f"teacher run for {phase} is not complete for the frozen pool")
        phase_candidates = load_candidates(pool_path)
        phase_oracles = load_oracles(pool_path)
        phase_predictions = _terminal_predictions(
            _read_jsonl(run_path / "predictions.jsonl", TeacherPredictionV0_1)
        )
        if set(phase_predictions) != {item.candidate_id for item in phase_candidates}:
            raise ValueError(f"teacher run for {phase} lacks terminal candidate outputs")
        candidates.update({item.candidate_id: item for item in phase_candidates})
        oracles.update({item.candidate_id: item for item in phase_oracles})
        predictions.update(phase_predictions)
        pool_manifests.append(pool)
        run_manifests.append(run)

    target = load_model_config(resolve(experiment_path, experiment.target_model_config_path))
    from transformers import AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        target.tokenizer_id,
        revision=target.tokenizer_revision,
        trust_remote_code=False,
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
    by_archetype: dict[tuple[str, str], list[SyntheticFilterRecordV0_1]] = defaultdict(list)
    for item in accepted:
        candidate = candidates[item.candidate_id]
        by_archetype[(candidate.scenario_family, candidate.archetype)].append(item)
    sufficient = len(by_archetype) == 16 and all(
        len(values) >= pool_config.selected_per_archetype for values in by_archetype.values()
    )
    selected_ids: set[str] = set()
    if sufficient:
        for values in by_archetype.values():
            chosen = sorted(values, key=lambda item: item.selection_rank)[
                : pool_config.selected_per_archetype
            ]
            selected_ids.update(item.candidate_id for item in chosen)
    records = [_with_selection(item, item.candidate_id in selected_ids) for item in records]
    accepted = [item for item in records if item.accepted]
    rejected = [item for item in records if not item.accepted]
    selected = [
        SyntheticTrainingExampleV0_1(
            schema_version="synthetic-training-example-v0.1",
            candidate=candidates[item.candidate_id],
            teacher_label=item.teacher_label or "",
            teacher_prediction_sha256=item.teacher_prediction_sha256,
            oracle_sha256=item.oracle_sha256,
        )
        for item in records
        if item.selected_for_training
    ]
    selected.sort(key=lambda item: item.candidate.candidate_id)
    status = "COMPLETED" if sufficient else "NEEDS_EXPANSION" if phases == ["initial"] else "FAILED"
    failure_code = "INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES" if status == "FAILED" else None
    if status == "COMPLETED" and len(selected) != 224:
        raise ValueError("synthetic selection did not produce exactly 224 records")

    all_bytes = canonical_jsonl_bytes(records, id_key="candidate_id")
    accepted_bytes = canonical_jsonl_bytes(accepted, id_key="candidate_id")
    rejected_bytes = canonical_jsonl_bytes(rejected, id_key="candidate_id")
    selected_bytes = canonical_jsonl_bytes(selected)
    identity = content_sha256(
        {
            "pool_sha256s": [item.content_sha256 for item in pool_manifests],
            "teacher_sha256s": [item.content_sha256 for item in run_manifests],
            "filter_records": [item.content_sha256 for item in records],
            "selected_ids": sorted(selected_ids),
        }
    )
    dataset_id = f"day3-synthetic-dataset-{identity[:16]}"
    created_at = datetime.now(UTC)
    selected_counts = Counter(
        f"{item.candidate.scenario_family}:{item.candidate.archetype}" for item in selected
    )
    payload = {
        "schema_version": "synthetic-dataset-v0.1",
        "dataset_id": dataset_id,
        "status": status,
        "failure_code": failure_code,
        "pool_ids": [item.pool_id for item in pool_manifests],
        "pool_sha256s": [item.content_sha256 for item in pool_manifests],
        "teacher_run_ids": [item.run_id for item in run_manifests],
        "teacher_run_sha256s": [item.content_sha256 for item in run_manifests],
        "filter_version": pool_config.filter_version,
        "candidate_count": len(records),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "selected_count": len(selected),
        "selected_per_archetype": dict(sorted(selected_counts.items())),
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
    manifest = SyntheticDatasetManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_DATASET_EXCLUSIONS)},
        strict=True,
    )
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    dataset_root = artifact_root / "synthetic-data"
    destination = dataset_root / dataset_id
    if destination.exists():
        stored = SyntheticDatasetManifestV0_1.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != manifest.content_sha256:
            raise ValueError("existing synthetic dataset differs")
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
    filter_id = f"day3-filter-{identity[:16]}"
    filter_root = artifact_root / "filtering"
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
) -> tuple[Path, SyntheticDatasetManifestV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "synthetic-data"
    matches = sorted(root.glob("day3-synthetic-dataset-*"))
    values = [
        (
            path,
            SyntheticDatasetManifestV0_1.model_validate_json(
                (path / "manifest.json").read_bytes(), strict=True
            ),
        )
        for path in matches
    ]
    if require_completed:
        values = [item for item in values if item[1].status == "COMPLETED"]
    if len(values) != 1:
        raise ValueError(f"expected one matching synthetic dataset, found {len(values)}")
    return values[0]


def freeze_schedule(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    method_path = resolve(experiment_path, experiment.method_config_path)
    method = load_method_config(method_path)
    dataset_path, dataset = find_synthetic_dataset(experiment_path)
    if dataset.status != "COMPLETED" or dataset.selected_count != 224:
        raise ValueError("a completed 224-record synthetic dataset is required")
    selected = _read_jsonl(dataset_path / "selected.jsonl", SyntheticTrainingExampleV0_1)
    if any(
        not item.candidate.candidate_id.startswith("synthetic_opsroute_v010_") for item in selected
    ):
        raise ValueError("training data contains a non-synthetic identifier")
    target = load_model_config(resolve(method_path, method.model_config_path))
    from transformers import AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        target.tokenizer_id,
        revision=target.tokenizer_revision,
        trust_remote_code=False,
    )
    token_counts = {
        item.candidate.candidate_id: training_sequence_length(
            tokenizer, item.candidate, item.teacher_label
        )
        for item in selected
    }
    by_id = {item.candidate.candidate_id: item for item in selected}
    remaining = 272643
    items: list[Day3ScheduleItem] = []
    cycle = 0
    while remaining:
        added = False
        ordered = sorted(
            by_id,
            key=lambda candidate_id: sha256_text(
                f"20260714:target_synthetic_distillation:cycle:{cycle}:{candidate_id}"
            ),
        )
        for candidate_id in ordered:
            tokens = token_counts[candidate_id]
            if tokens <= remaining:
                items.append(
                    Day3ScheduleItem(
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
        "schema_version": "synthetic-training-schedule-v0.1",
        "schedule_id": f"day3-synthetic-schedule-{items_sha256[:16]}",
        "method_id": "target_synthetic_distillation",
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
    schedule = SyntheticTrainingScheduleV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
    root = resolve(experiment_path, experiment.artifact_root) / "schedules"
    destination = root / schedule.schedule_id
    if destination.exists():
        stored = SyntheticTrainingScheduleV0_1.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != schedule.content_sha256:
            raise ValueError("existing Day 3 schedule differs")
        return destination
    return write_atomic_bundle(
        root,
        schedule.schedule_id,
        {"manifest.json": canonical_json_bytes(schedule) + b"\n"},
    )


def find_schedule(experiment_path: Path) -> tuple[Path, SyntheticTrainingScheduleV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "schedules"
    matches = sorted(root.glob("day3-synthetic-schedule-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one frozen Day 3 schedule, found {len(matches)}")
    value = SyntheticTrainingScheduleV0_1.model_validate_json(
        (matches[0] / "manifest.json").read_bytes(), strict=True
    )
    return matches[0], value


def training_sequence_length(tokenizer: Any, candidate: Any, label: str) -> int:
    prompt = render_prompt(tokenizer, candidate, "0.1.0")
    messages = [*build_messages(candidate, "0.1.0"), {"role": "assistant", "content": label}]
    full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"assistant template changed prompt prefix: {candidate.candidate_id}")
    if len(full_ids) > 1024:
        raise ValueError(f"training sequence exceeds 1024 tokens: {candidate.candidate_id}")
    return len(full_ids)


def _filter_one(
    candidate: SyntheticCandidateInputV0_1,
    oracle: SyntheticOracleRecordV0_1,
    prediction: TeacherPredictionV0_1,
    tokenizer: Any,
) -> SyntheticFilterRecordV0_1:
    parser = prediction.parser_result
    metrics = (
        score_prediction(parser, oracle.expected_contract, oracle.evaluation_metadata)
        if parser is not None
        else None
    )
    reason = None
    secondary: list[str] = []
    target_tokens: int | None = None
    label: str | None = None
    if prediction.status != "COMPLETED":
        reason = "TEACHER_INFERENCE_FAILED"
    elif not prediction.raw_output.strip():
        reason = "EMPTY_OUTPUT"
    elif parser is not None and parser.classification == "NORMALIZED_VALID":
        reason = "NORMALIZED_NOT_STRICT"
    elif parser is None or parser.status == "invalid_json":
        codes = {error.code for error in parser.errors} if parser else set()
        reason = (
            "PROSE_OR_MULTIPLE_OBJECTS" if "PROSE_OR_MULTIPLE_OBJECTS" in codes else "INVALID_JSON"
        )
    elif parser.classification != "STRICT_VALID" or parser.validated_contract is None:
        reason = "SCHEMA_INVALID"
    else:
        label = parser.strict_candidate
        try:
            target_tokens = training_sequence_length(tokenizer, candidate, label)
        except ValueError:
            reason = "TARGET_SEQUENCE_TOO_LONG"
        if (
            reason is None
            and metrics is not None
            and any(
                value is not False
                for value in (
                    metrics.unauthorized_action,
                    metrics.approval_bypass,
                    metrics.false_action,
                    metrics.hallucinated_arguments,
                )
            )
        ):
            reason = "SAFETY_VIOLATION"
        if reason is None and parser.validated_contract != oracle.expected_contract:
            reason = "POLICY_CONTRACT_MISMATCH"
    if parser is not None:
        secondary.extend(error.code for error in parser.errors)
    if metrics is not None:
        secondary.extend(
            name
            for name in (
                "unauthorized_action",
                "approval_bypass",
                "false_action",
                "hallucinated_arguments",
            )
            if getattr(metrics, name) is True
        )
    accepted = reason is None
    payload = {
        "schema_version": "synthetic-filter-record-v0.1",
        "candidate_id": candidate.candidate_id,
        "candidate_record_sha256": candidate.record_sha256,
        "teacher_prediction_sha256": prediction.content_sha256,
        "oracle_sha256": oracle.content_sha256,
        "accepted": accepted,
        "selected_for_training": False,
        "primary_rejection_reason": reason,
        "secondary_reasons": sorted(set(secondary)),
        "teacher_label": label if accepted else None,
        "target_sequence_tokens": target_tokens,
        "selection_rank": sha256_text(
            f"20260714:day3-synthetic-select-v0.1.0:{candidate.candidate_id}"
        ),
        "metrics": metrics.model_dump(mode="json") if metrics else None,
    }
    return SyntheticFilterRecordV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _with_selection(record: SyntheticFilterRecordV0_1, selected: bool) -> SyntheticFilterRecordV0_1:
    payload = {
        **record.model_dump(mode="json"),
        "selected_for_training": selected,
    }
    payload.pop("content_sha256")
    return SyntheticFilterRecordV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _find_teacher_run(experiment_path: Path, phase: str) -> tuple[Path, TeacherRunManifestV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "teacher-runs"
    values: list[tuple[Path, TeacherRunManifestV0_1]] = []
    for path in sorted(root.glob(f"day3-teacher-{phase}-*")):
        manifest = TeacherRunManifestV0_1.model_validate_json(
            (path / "manifest.json").read_bytes(), strict=True
        )
        if manifest.status == "COMPLETED":
            values.append((path, manifest))
    if len(values) != 1:
        raise ValueError(f"expected one completed {phase} teacher run, found {len(values)}")
    return values[0]


def _terminal_predictions(values: list[TeacherPredictionV0_1]) -> dict[str, TeacherPredictionV0_1]:
    grouped: dict[str, list[TeacherPredictionV0_1]] = defaultdict(list)
    for value in values:
        grouped[value.candidate_id].append(value)
    result: dict[str, TeacherPredictionV0_1] = {}
    for candidate_id, attempts in grouped.items():
        completed = [item for item in attempts if item.status == "COMPLETED"]
        result[candidate_id] = completed[-1] if completed else attempts[-1]
    return result


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        return [schema.model_validate_json(line, strict=True) for line in handle]
