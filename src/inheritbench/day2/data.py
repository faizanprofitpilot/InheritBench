"""Immutable Day 2 split manifests and deterministic training schedules."""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json,
    canonical_json_bytes,
    content_sha256,
    sha256_text,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.config import ModelConfig, load_model_config
from inheritbench.data.opsroute.schemas import DatasetManifest, OpsRouteExample
from inheritbench.day2.config import load_experiment_config, load_method_config
from inheritbench.day2.schemas import (
    Day2DataBundleManifest,
    Day2ExperimentConfig,
    Day2SubsetManifest,
    MethodConfigV0_2,
    ScheduleItem,
    SubsetEntry,
    TrainingScheduleManifestV0_1,
)
from inheritbench.models.prompts import build_messages, render_prompt

_LIMITED_VERSION = "day2-limited-v0.1"
_LIMITED_EXTRA_QUOTAS: tuple[tuple[str, str], ...] = (
    ("refund_policy_routing", "execute"),
    ("refund_policy_routing", "request_approval"),
    ("refund_policy_routing", "refuse"),
    ("refund_policy_routing", "no_action"),
    ("subscription_cancellation_retention", "execute"),
    ("subscription_cancellation_retention", "request_approval"),
    ("subscription_cancellation_retention", "refuse"),
    ("subscription_cancellation_retention", "ask_clarification"),
)


def freeze_data(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    dataset_directory = _resolve(experiment_path, experiment.dataset_directory)
    output_root = _resolve(experiment_path, experiment.data_output_root)
    dataset = DatasetManifest.model_validate_json(
        (dataset_directory / "manifest.json").read_bytes(), strict=True
    )
    splits = {
        split: _read_split(dataset_directory / f"{split}.jsonl")
        for split in ("train", "validation", "test")
    }
    _validate_frozen_splits(splits)
    train = splits["train"]
    limited = select_limited_examples(train, experiment.seed, experiment.limited_selection_version)
    subsets = {
        "full_train": _subset(
            "day2-full-train-v0.1",
            "training",
            dataset.dataset_sha256,
            "train",
            train,
            "all 224 frozen train records sorted by example_id",
            None,
        ),
        "limited_train": _subset(
            "day2-limited-train-v0.1",
            "training",
            dataset.dataset_sha256,
            "train",
            limited,
            "one SHA-256-ranked record per archetype plus eight locked family/decision quotas",
            len(limited) / len(train),
        ),
        "full_validation": _subset(
            "day2-full-validation-v0.1",
            "validation",
            dataset.dataset_sha256,
            "validation",
            splits["validation"],
            "all 32 frozen validation records",
            None,
        ),
        "final_test": _subset(
            "day2-final-test-v0.1",
            "final_test",
            dataset.dataset_sha256,
            "test",
            splits["test"],
            "all 32 frozen test records; inaccessible before freeze",
            None,
        ),
    }
    method_paths = {}
    for path in experiment.method_config_paths:
        resolved = _resolve(experiment_path, path)
        method_paths[load_method_config(resolved).method_id] = resolved
    source_method = load_method_config(method_paths["source_adapted_full"])
    target_method = load_method_config(method_paths["target_full_retrain"])
    limited_method = load_method_config(method_paths["target_limited_retrain_10pct"])
    source_model = load_model_config(
        _resolve(method_paths["source_adapted_full"], source_method.model_config_path)
    )
    target_model = load_model_config(
        _resolve(method_paths["target_full_retrain"], target_method.model_config_path)
    )
    source_tokens = training_token_counts(
        source_model, train, source_method.prompt_template_version
    )
    target_tokens = training_token_counts(
        target_model, train, target_method.prompt_template_version
    )
    schedules = {
        "source_primary": _full_schedule(
            source_method, subsets["full_train"], source_model, source_tokens
        ),
        "target_primary": _full_schedule(
            target_method, subsets["full_train"], target_model, target_tokens
        ),
        "target_limited_primary": _limited_schedule(
            limited_method,
            subsets["limited_train"],
            target_model,
            {item.example_id: target_tokens[item.example_id] for item in limited},
        ),
    }
    _validate_locked_facts(subsets, schedules)
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "dataset_sha256": dataset.dataset_sha256,
            "subsets": {name: item.content_sha256 for name, item in subsets.items()},
            "schedules": {name: item.content_sha256 for name, item in schedules.items()},
        }
    )
    bundle_id = f"day2-data-{identity[:16]}"
    destination = output_root / bundle_id
    if destination.exists():
        stored = Day2DataBundleManifest.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.dataset_sha256 != dataset.dataset_sha256:
            raise ValueError("existing Day 2 data bundle has a different dataset hash")
        if stored.subset_sha256s != {name: item.content_sha256 for name, item in subsets.items()}:
            raise ValueError("existing Day 2 subset hashes differ")
        if stored.schedule_sha256s != {
            name: item.content_sha256 for name, item in schedules.items()
        }:
            raise ValueError("existing Day 2 schedule hashes differ")
        return destination
    payload = {
        "schema_version": "day2-data-bundle-v0.1",
        "bundle_id": bundle_id,
        "dataset_sha256": dataset.dataset_sha256,
        "subset_sha256s": {name: item.content_sha256 for name, item in subsets.items()},
        "schedule_sha256s": {name: item.content_sha256 for name, item in schedules.items()},
        "created_at": created_at,
    }
    bundle = Day2DataBundleManifest.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys={"created_at"})},
        strict=True,
    )
    files = {
        **{f"{name}.json": canonical_json_bytes(item) + b"\n" for name, item in subsets.items()},
        **{f"{name}.json": canonical_json_bytes(item) + b"\n" for name, item in schedules.items()},
        "manifest.json": canonical_json_bytes(bundle) + b"\n",
    }
    return write_atomic_bundle(output_root, bundle_id, files)


def find_data_bundle(experiment_path: Path, experiment: Day2ExperimentConfig) -> Path:
    root = _resolve(experiment_path, experiment.data_output_root)
    candidates = sorted(path for path in root.glob("day2-data-*") if path.is_dir())
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one frozen Day 2 data bundle, found {len(candidates)}")
    return candidates[0]


def load_subset(bundle: Path, name: str) -> Day2SubsetManifest:
    return Day2SubsetManifest.model_validate_json(
        (bundle / f"{name}.json").read_bytes(), strict=True
    )


def load_schedule(bundle: Path, name: str) -> TrainingScheduleManifestV0_1:
    return TrainingScheduleManifestV0_1.model_validate_json(
        (bundle / f"{name}.json").read_bytes(), strict=True
    )


def select_limited_examples(
    train: list[OpsRouteExample], seed: int = 20260714, version: str = _LIMITED_VERSION
) -> list[OpsRouteExample]:
    by_archetype: dict[tuple[str, str], list[OpsRouteExample]] = {}
    for example in train:
        by_archetype.setdefault((example.scenario_family, example.archetype), []).append(example)
    if len(by_archetype) != 16:
        raise ValueError("limited selection requires exactly 16 archetypes")
    selected: dict[str, OpsRouteExample] = {}
    for examples in by_archetype.values():
        chosen = min(
            examples,
            key=lambda item: sha256_text(f"{seed}:{version}:archetype:{item.example_id}"),
        )
        selected[chosen.example_id] = chosen
    for family, decision in _LIMITED_EXTRA_QUOTAS:
        eligible = [
            item
            for item in train
            if item.example_id not in selected
            and item.scenario_family == family
            and item.expected.decision == decision
        ]
        if not eligible:
            raise ValueError(f"limited quota has no candidate: {family}/{decision}")
        chosen = min(
            eligible,
            key=lambda item: sha256_text(f"{seed}:{version}:extra:{item.example_id}"),
        )
        selected[chosen.example_id] = chosen
    result = sorted(selected.values(), key=lambda item: item.example_id)
    if len(result) != 24:
        raise ValueError(f"limited selection produced {len(result)} records")
    return result


def training_token_counts(
    model: ModelConfig, examples: list[OpsRouteExample], prompt_version: str
) -> dict[str, int]:
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    snapshot = snapshot_download(
        repo_id=model.tokenizer_id,
        revision=model.tokenizer_revision,
        local_files_only=True,
    )
    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        snapshot,
        trust_remote_code=False,
        local_files_only=True,
    )
    counts: dict[str, int] = {}
    for example in examples:
        prompt = render_prompt(tokenizer, example, prompt_version)
        messages = [
            *build_messages(example, prompt_version),
            {"role": "assistant", "content": canonical_json(example.expected)},
        ]
        full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
        if full_ids[: len(prompt_ids)] != prompt_ids:
            raise ValueError(f"assistant template changed prompt prefix: {example.example_id}")
        if len(full_ids) > 1024:
            raise ValueError(f"training sequence exceeds 1024 tokens: {example.example_id}")
        counts[example.example_id] = len(full_ids)
    return counts


def _full_schedule(
    method: MethodConfigV0_2,
    subset: Day2SubsetManifest,
    model: ModelConfig,
    token_counts: dict[str, int],
) -> TrainingScheduleManifestV0_1:
    assert method.training is not None
    one_exposure = sum(token_counts.values())
    if method.training.target_processed_tokens % one_exposure:
        raise ValueError(f"{method.method_id} token budget is not a whole exposure")
    cycles = method.training.target_processed_tokens // one_exposure
    items: list[ScheduleItem] = []
    for cycle in range(cycles):
        ordered = sorted(
            subset.example_ids,
            key=lambda example_id: sha256_text(
                f"{method.seed}:{method.method_id}:epoch:{cycle}:{example_id}"
            ),
        )
        items.extend(
            ScheduleItem(
                cursor=len(items),
                cycle=cycle,
                example_id=example_id,
                sequence_tokens=token_counts[example_id],
            )
            for example_id in ordered
        )
    return _schedule_manifest(method, subset, model, token_counts, items)


def _limited_schedule(
    method: MethodConfigV0_2,
    subset: Day2SubsetManifest,
    model: ModelConfig,
    token_counts: dict[str, int],
) -> TrainingScheduleManifestV0_1:
    assert method.training is not None
    remaining = method.training.target_processed_tokens
    items: list[ScheduleItem] = []
    cycle = 0
    while remaining:
        added = False
        ordered = sorted(
            subset.example_ids,
            key=lambda example_id: sha256_text(
                f"{method.seed}:{method.method_id}:epoch:{cycle}:{example_id}"
            ),
        )
        for example_id in ordered:
            tokens = token_counts[example_id]
            if tokens <= remaining:
                items.append(
                    ScheduleItem(
                        cursor=len(items),
                        cycle=cycle,
                        example_id=example_id,
                        sequence_tokens=tokens,
                    )
                )
                remaining -= tokens
                added = True
        if not added:
            break
        cycle += 1
    return _schedule_manifest(method, subset, model, token_counts, items)


def _schedule_manifest(
    method: MethodConfigV0_2,
    subset: Day2SubsetManifest,
    model: ModelConfig,
    token_counts: dict[str, int],
    items: list[ScheduleItem],
) -> TrainingScheduleManifestV0_1:
    assert method.training is not None
    processed = sum(item.sequence_tokens for item in items)
    exposures = Counter(item.example_id for item in items)
    item_identity = sha256_text(":".join(item.example_id for item in items))[:16]
    payload = {
        "schema_version": "training-schedule-v0.1",
        "schedule_id": f"{method.method_id}-{item_identity}",
        "method_id": method.method_id,
        "subset_content_sha256": subset.content_sha256,
        "tokenizer_id": model.tokenizer_id,
        "tokenizer_revision": model.tokenizer_revision,
        "seed": method.seed,
        "ordering_rule": "SHA256(seed:method_id:epoch:cycle:example_id), whole examples only",
        "target_processed_tokens": method.training.target_processed_tokens,
        "processed_tokens": processed,
        "residual_tokens": method.training.target_processed_tokens - processed,
        "budget_ratio": processed / method.training.target_processed_tokens,
        "unique_examples": len(exposures),
        "example_exposures": len(items),
        "optimizer_steps": math.ceil(len(items) / method.training.gradient_accumulation_steps),
        "gradient_accumulation_steps": method.training.gradient_accumulation_steps,
        "warmup_steps": method.training.scheduler.warmup_steps,
        "checkpoint_steps": method.training.checkpoint_steps,
        "per_example_exposures": dict(sorted(exposures.items())),
        "token_counts": dict(sorted(token_counts.items())),
        "items": [item.model_dump(mode="json") for item in items],
    }
    return TrainingScheduleManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _subset(
    subset_id: str,
    purpose: Literal["training", "validation", "final_test"],
    dataset_sha256: str,
    split: Literal["train", "validation", "test"],
    examples: list[OpsRouteExample],
    rule: str,
    fraction: float | None,
) -> Day2SubsetManifest:
    entries = [
        SubsetEntry(
            example_id=item.example_id,
            record_sha256=item.record_sha256,
            split=item.split,
            scenario_family=item.scenario_family,
            archetype=item.archetype,
            expected_decision=item.expected.decision,
            selection_rank=sha256_text(f"20260714:{_LIMITED_VERSION}:manifest:{item.example_id}"),
        )
        for item in sorted(examples, key=lambda value: value.example_id)
    ]
    payload = {
        "schema_version": "day2-subset-v0.1",
        "subset_id": subset_id,
        "purpose": purpose,
        "dataset_sha256": dataset_sha256,
        "source_split": split,
        "fixture_evidence": False,
        "selection_version": _LIMITED_VERSION,
        "selection_rule": rule,
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "actual_fraction_of_train": fraction,
    }
    return Day2SubsetManifest.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _read_split(path: Path) -> list[OpsRouteExample]:
    with path.open("r", encoding="utf-8") as handle:
        return [OpsRouteExample.model_validate(json.loads(line), strict=True) for line in handle]


def _validate_frozen_splits(splits: dict[str, list[OpsRouteExample]]) -> None:
    expected = {"train": 224, "validation": 32, "test": 32}
    for split, count in expected.items():
        records = splits[split]
        if len(records) != count or any(record.split != split for record in records):
            raise ValueError(f"{split} must contain exactly {count} matching records")
        if any(record.example_id.startswith("fixture_") for record in records):
            raise ValueError("fixture evidence is prohibited")
    identifiers = [item.example_id for records in splits.values() for item in records]
    signatures = [item.semantic_signature for records in splits.values() for item in records]
    if len(identifiers) != len(set(identifiers)) or len(signatures) != len(set(signatures)):
        raise ValueError("Day 2 split overlap or semantic leakage detected")


def _validate_locked_facts(
    subsets: dict[str, Day2SubsetManifest],
    schedules: dict[str, TrainingScheduleManifestV0_1],
) -> None:
    limited = subsets["limited_train"]
    decisions = Counter(entry.expected_decision for entry in limited.entries)
    families = Counter(entry.scenario_family for entry in limited.entries)
    if families != {"refund_policy_routing": 12, "subscription_cancellation_retention": 12}:
        raise ValueError(f"unexpected limited family composition: {families}")
    if decisions != {
        "execute": 6,
        "refuse": 6,
        "request_approval": 5,
        "no_action": 4,
        "ask_clarification": 3,
    }:
        raise ValueError(f"unexpected limited decision composition: {decisions}")
    if len({(entry.scenario_family, entry.archetype) for entry in limited.entries}) != 16:
        raise ValueError("limited subset does not cover all 16 archetypes")
    source = schedules["source_primary"]
    full = schedules["target_primary"]
    small = schedules["target_limited_primary"]
    expected = (
        (source.processed_tokens, source.example_exposures, source.optimizer_steps),
        (full.processed_tokens, full.example_exposures, full.optimizer_steps),
        (small.processed_tokens, small.example_exposures, small.optimizer_steps),
    )
    if expected != ((379768, 896, 224), (272643, 672, 168), (272634, 672, 168)):
        raise ValueError(f"locked tokenizer budgets changed: {expected}")


def _resolve(parent_file: Path, candidate: str) -> Path:
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        return candidate_path
    direct = Path.cwd() / candidate_path
    if direct.exists() or candidate_path.parts[0] in {"artifacts", "adapters"}:
        return direct
    return parent_file.parent / candidate_path
