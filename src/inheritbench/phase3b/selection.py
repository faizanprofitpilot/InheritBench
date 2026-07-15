"""Deterministic Phase 3B synthetic and original-anchor selection."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json,
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.store import artifact_reference, write_atomic_bundle
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day3_matched.schemas import (
    MatchedCandidateInputV0_1,
    MatchedFilterDecisionV0_1,
)
from inheritbench.phase3b.config import load_experiment_config, resolve
from inheritbench.phase3b.schemas import (
    HybridDatasetManifestV0_1,
    HybridLabelAccounting,
    HybridSelectionPolicyV0_1,
    HybridTrainingRecordV0_1,
    OriginalAnchorSelectionV0_1,
    Phase3BHistoricalBaselineV0_1,
    SyntheticSelectionV0_1,
)

_BLINDSPOT = ("refund_policy_routing", "duplicate_auto_refund")
_SYNTHETIC_NAMESPACE = "phase3b-synthetic-selection-v0.1"
_ANCHOR_NAMESPACE = "phase3b-anchor-selection-v0.1"
_SELECTION_EXCLUSIONS = {"selection_id", "created_at", "content_sha256"}
_DATASET_EXCLUSIONS = {"dataset_id", "created_at", "content_sha256"}


def freeze_hybrid_selection(experiment_path: Path) -> tuple[Path, Path, Path]:
    experiment = load_experiment_config(experiment_path)
    _require_baseline(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    policy = HybridSelectionPolicyV0_1(
        schema_version="phase3b-selection-policy-v0.1",
        synthetic_rank_namespace="phase3b-synthetic-selection-v0.1",
        anchor_rank_namespace="phase3b-anchor-selection-v0.1",
        group_key="scenario_family+archetype",
        selected_per_group=14,
        blindspot_family="refund_policy_routing",
        blindspot_archetype="duplicate_auto_refund",
        blindspot_synthetic_count=4,
        anchor_count=10,
        synthetic_count=214,
        total_count=224,
        performance_fields_permitted=False,
    )
    policy_sha256 = content_sha256(policy)
    candidates = _matched_candidates()
    accepted = _accepted_filters()
    synthetic_records, synthetic = _select_synthetic(candidates, accepted, policy_sha256)
    anchor_records, anchors = _select_anchors(experiment_path, policy_sha256)
    created_at = datetime.now(UTC)
    synthetic_path = _write_synthetic(root, synthetic, created_at)
    anchor_path = _write_anchors(root, anchors, anchor_records, created_at)
    records = sorted(
        [*synthetic_records, *anchor_records], key=lambda item: item.training_record_id
    )
    if len(records) != 224 or len({item.training_record_id for item in records}) != 224:
        raise ValueError("hybrid selection must contain 224 unique training records")
    family_counts = Counter(item.scenario_family for item in records)
    group_counts = Counter(f"{item.scenario_family}:{item.archetype}" for item in records)
    record_bytes = canonical_jsonl_bytes(records, id_key="training_record_id")
    record_ref = artifact_reference(
        "records.jsonl",
        record_bytes,
        content_sha256=content_sha256([item.content_sha256 for item in records]),
    )
    accounting = HybridLabelAccounting(
        original_labels_directly_used_by_target=10,
        original_labels_used_upstream_to_train_teacher=224,
        original_labeled_records_used_to_design_distribution=224,
        synthetic_labels_used_by_target=214,
        original_anchor_labels_used_by_target=10,
        total_unique_target_training_examples=224,
        synthetic_candidates_previously_generated=768,
        accepted_synthetic_pool_available=719,
        selected_synthetic_examples=214,
        selected_original_anchor_examples=10,
        teacher_generation_processed_tokens=323601,
        teacher_generation_duration_seconds=1122.69,
        source_teacher_training_tokens=379768,
        source_teacher_training_duration_seconds=437.86,
    )
    payload = {
        "schema_version": "phase3b-hybrid-dataset-v0.1",
        "dataset_id": "pending",
        "status": "FROZEN",
        "synthetic_selection_sha256": synthetic.content_sha256,
        "anchor_selection_sha256": anchors.content_sha256,
        "records_artifact": record_ref.model_dump(mode="json"),
        "synthetic_count": 214,
        "anchor_count": 10,
        "total_count": 224,
        "family_counts": dict(sorted(family_counts.items())),
        "group_counts": dict(sorted(group_counts.items())),
        "accounting": accounting.model_dump(mode="json"),
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_DATASET_EXCLUSIONS)
    dataset_id = f"phase3b-hybrid-dataset-{identity[:16]}"
    manifest = HybridDatasetManifestV0_1.model_validate(
        {**payload, "dataset_id": dataset_id, "content_sha256": identity}, strict=True
    )
    hybrid_path = write_atomic_bundle(
        root / "hybrid-data",
        dataset_id,
        {
            "records.jsonl": record_bytes,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
            "lineage.json": canonical_json_bytes(
                {
                    "synthetic_selection_path": str(synthetic_path),
                    "anchor_selection_path": str(anchor_path),
                    "selection_policy": policy,
                }
            )
            + b"\n",
        },
    )
    return synthetic_path, anchor_path, hybrid_path


def find_hybrid_dataset(experiment_path: Path) -> tuple[Path, HybridDatasetManifestV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "hybrid-data"
    paths = sorted(root.glob("*/manifest.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one frozen Phase 3B hybrid dataset, found {len(paths)}")
    return paths[0].parent, HybridDatasetManifestV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def load_hybrid_records(path: Path) -> list[HybridTrainingRecordV0_1]:
    return _read_jsonl(path / "records.jsonl", HybridTrainingRecordV0_1)


def _select_synthetic(
    candidates: dict[str, MatchedCandidateInputV0_1],
    accepted: list[MatchedFilterDecisionV0_1],
    policy_sha256: str,
) -> tuple[list[HybridTrainingRecordV0_1], SyntheticSelectionV0_1]:
    by_group: dict[tuple[str, str], list[MatchedFilterDecisionV0_1]] = defaultdict(list)
    ranks: dict[str, str] = {}
    for item in accepted:
        candidate = candidates[item.candidate_id]
        by_group[(candidate.scenario_family, candidate.archetype)].append(item)
        ranks[item.candidate_id] = sha256_text(f"{_SYNTHETIC_NAMESPACE}:{item.candidate_id}")
    if len(by_group) != 16:
        raise ValueError("matched accepted pool must cover all 16 family/archetype groups")
    selected: list[MatchedFilterDecisionV0_1] = []
    selected_by_group: dict[str, list[str]] = {}
    for group, values in sorted(by_group.items()):
        if group == _BLINDSPOT:
            chosen = sorted(values, key=lambda item: item.candidate_id)
            if len(chosen) != 4:
                raise ValueError("blind-spot synthetic selection must use exactly four outputs")
        else:
            if len(values) < 14:
                raise ValueError(f"insufficient accepted matched outputs for {group}")
            chosen = sorted(values, key=lambda item: ranks[item.candidate_id])[:14]
        selected.extend(chosen)
        selected_by_group[f"{group[0]}:{group[1]}"] = [item.candidate_id for item in chosen]
    if len(selected) != 214:
        raise ValueError("synthetic selection must contain exactly 214 records")
    records = [
        _synthetic_training_record(candidates[item.candidate_id], item, policy_sha256, ranks)
        for item in selected
    ]
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase3b-synthetic-selection-v0.1",
        "selection_id": "pending",
        "policy_sha256": policy_sha256,
        "matched_dataset_sha256": (
            "cdcb330e7e9fcb0189e0bf0a841ab452cfdceffd5f2b971a53419812d4fe8ce5"
        ),
        "matched_filter_sha256": sha256_file(
            Path.cwd()
            / "artifacts/day3-matched/filtering"
            / "day3-matched-filter-36eea02e066b021a/filter_records.jsonl"
        ),
        "accepted_pool_count": 719,
        "selected_ids": sorted(item.candidate_id for item in selected),
        "selected_by_group": dict(sorted(selected_by_group.items())),
        "selection_ranks": dict(sorted(ranks.items())),
        "blindspot_selected_ids": selected_by_group["refund_policy_routing:duplicate_auto_refund"],
        "teacher_label_sha256s": {
            item.candidate_id: sha256_text(item.teacher_label or "") for item in selected
        },
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_SELECTION_EXCLUSIONS)
    selection = SyntheticSelectionV0_1.model_validate(
        {
            **payload,
            "selection_id": f"phase3b-synthetic-selection-{identity[:16]}",
            "content_sha256": identity,
        },
        strict=True,
    )
    return records, selection


def _select_anchors(
    experiment_path: Path, policy_sha256: str
) -> tuple[list[HybridTrainingRecordV0_1], OriginalAnchorSelectionV0_1]:
    experiment = load_experiment_config(experiment_path)
    train = _read_jsonl(
        resolve(experiment_path, experiment.dataset_directory) / "train.jsonl",
        OpsRouteExample,
    )
    eligible = sorted(
        (
            item
            for item in train
            if item.split == "train"
            and item.scenario_family == _BLINDSPOT[0]
            and item.archetype == _BLINDSPOT[1]
        ),
        key=lambda item: item.example_id,
    )
    if len(eligible) != 14:
        raise ValueError("expected 14 original duplicate-auto training records")
    ranks = {
        item.example_id: sha256_text(f"{_ANCHOR_NAMESPACE}:{item.example_id}") for item in eligible
    }
    ordered = sorted(eligible, key=lambda item: ranks[item.example_id])
    selected = ordered[:10]
    unselected = ordered[10:]
    records = [
        _anchor_training_record(item, policy_sha256, ranks[item.example_id]) for item in selected
    ]
    selected_bytes = canonical_jsonl_bytes(records, id_key="training_record_id")
    selected_ref = artifact_reference(
        "records.jsonl",
        selected_bytes,
        content_sha256=content_sha256([item.content_sha256 for item in records]),
    )
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase3b-anchor-selection-v0.1",
        "selection_id": "pending",
        "policy_sha256": policy_sha256,
        "train_artifact_sha256": sha256_file(
            resolve(experiment_path, experiment.dataset_directory) / "train.jsonl"
        ),
        "eligible_ids": [item.example_id for item in eligible],
        "ranks": dict(sorted(ranks.items())),
        "selected_ids": [item.example_id for item in selected],
        "unselected_ids": [item.example_id for item in unselected],
        "selected_records_artifact": selected_ref.model_dump(mode="json"),
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_SELECTION_EXCLUSIONS)
    selection = OriginalAnchorSelectionV0_1.model_validate(
        {
            **payload,
            "selection_id": f"phase3b-anchor-selection-{identity[:16]}",
            "content_sha256": identity,
        },
        strict=True,
    )
    return records, selection


def _synthetic_training_record(
    candidate: MatchedCandidateInputV0_1,
    decision: MatchedFilterDecisionV0_1,
    policy_sha256: str,
    ranks: dict[str, str],
) -> HybridTrainingRecordV0_1:
    if not decision.accepted or not decision.teacher_label:
        raise ValueError("synthetic Phase 3B records must be immutable accepted outputs")
    payload = {
        "schema_version": "phase3b-training-record-v0.1",
        "training_record_id": f"phase3b-teacher-{candidate.candidate_id}",
        "scenario_family": candidate.scenario_family,
        "archetype": candidate.archetype,
        "input": candidate.input.model_dump(mode="json"),
        "label_origin": "teacher_output",
        "assistant_label": decision.teacher_label,
        "assistant_label_sha256": sha256_text(decision.teacher_label),
        "parent_artifact_path": (
            "artifacts/day3-matched/filtering/"
            "day3-matched-filter-36eea02e066b021a/filter_records.jsonl"
        ),
        "parent_artifact_sha256": decision.content_sha256,
        "source_record_id": candidate.candidate_id,
        "source_record_sha256": candidate.record_sha256,
        "selection_rank": ranks[candidate.candidate_id],
        "selection_sha256": policy_sha256,
    }
    return HybridTrainingRecordV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _anchor_training_record(
    example: OpsRouteExample, policy_sha256: str, rank: str
) -> HybridTrainingRecordV0_1:
    label = canonical_json(example.expected)
    payload = {
        "schema_version": "phase3b-training-record-v0.1",
        "training_record_id": f"phase3b-anchor-{example.example_id}",
        "scenario_family": example.scenario_family,
        "archetype": example.archetype,
        "input": example.input.model_dump(mode="json"),
        "label_origin": "original_anchor",
        "assistant_label": label,
        "assistant_label_sha256": sha256_text(label),
        "parent_artifact_path": "data/opsroute/v0.1.0/train.jsonl",
        "parent_artifact_sha256": example.record_sha256,
        "source_record_id": example.example_id,
        "source_record_sha256": example.record_sha256,
        "selection_rank": rank,
        "selection_sha256": policy_sha256,
    }
    return HybridTrainingRecordV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _write_synthetic(root: Path, selection: SyntheticSelectionV0_1, created_at: datetime) -> Path:
    del created_at
    return write_atomic_bundle(
        root / "synthetic-selections",
        selection.selection_id,
        {"selection.json": canonical_json_bytes(selection) + b"\n"},
    )


def _write_anchors(
    root: Path,
    selection: OriginalAnchorSelectionV0_1,
    records: list[HybridTrainingRecordV0_1],
    created_at: datetime,
) -> Path:
    del created_at
    return write_atomic_bundle(
        root / "anchor-selections",
        selection.selection_id,
        {
            "records.jsonl": canonical_jsonl_bytes(records, id_key="training_record_id"),
            "selection.json": canonical_json_bytes(selection) + b"\n",
        },
    )


def _matched_candidates() -> dict[str, MatchedCandidateInputV0_1]:
    values: dict[str, MatchedCandidateInputV0_1] = {}
    for path in [
        Path.cwd()
        / "artifacts/day3-matched/pools"
        / "day3-matched-pool-initial-e272e8a7b827bb01/candidate_inputs.jsonl",
        Path.cwd()
        / "artifacts/day3-matched/pools"
        / "day3-matched-pool-expansion-dc0b0c265b3c3ed1/candidate_inputs.jsonl",
    ]:
        for item in _read_jsonl(path, MatchedCandidateInputV0_1):
            values[item.candidate_id] = item
    if len(values) != 768:
        raise ValueError("expected exactly 768 matched candidates")
    return values


def _accepted_filters() -> list[MatchedFilterDecisionV0_1]:
    path = (
        Path.cwd() / "artifacts/day3-matched/synthetic-data/"
        "day3-matched-synthetic-dataset-36eea02e066b021a/accepted.jsonl"
    )
    values = _read_jsonl(path, MatchedFilterDecisionV0_1)
    if len(values) != 719 or any(not item.accepted for item in values):
        raise ValueError("matched accepted artifact must contain exactly 719 accepted outputs")
    return values


def _require_baseline(experiment_path: Path) -> Phase3BHistoricalBaselineV0_1:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "historical-baselines"
    paths = sorted(root.glob("*/baseline.json"))
    if len(paths) != 1:
        raise ValueError("Phase 3B hybrid selection requires one historical baseline")
    return Phase3BHistoricalBaselineV0_1.model_validate_json(paths[0].read_bytes(), strict=True)


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    return [schema.model_validate_json(line, strict=True) for line in path.read_text().splitlines()]
