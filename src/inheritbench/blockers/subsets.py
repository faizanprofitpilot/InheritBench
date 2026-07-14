"""Immutable split-safe manifests for blocker-resolution experiments."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.config import Sha256
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.data.opsroute.schemas import DatasetManifest, OpsRouteExample

_VALIDATION_IDS = (
    "opsroute_v010_refund_duplicate_auto_refund_14_b8c67d25",
    "opsroute_v010_refund_duplicate_approval_14_0afe2f3f",
    "opsroute_v010_refund_pending_payment_14_fa263dd7",
    "opsroute_v010_refund_incomplete_evidence_14_03f983ef",
    "opsroute_v010_subscription_eligible_cancellation_14_120956a1",
    "opsroute_v010_subscription_cancellation_approval_14_88285026",
    "opsroute_v010_subscription_no_subscription_request_14_9c2a5275",
    "opsroute_v010_subscription_ineligible_retention_14_89a3c6e8",
)
_VARIANT_PATTERN = re.compile(r"_(\d{2})_[0-9a-f]{8}$")


class SubsetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["blocker-subset-v0.1"]
    subset_id: str
    purpose: Literal["untouched_diagnostic", "micro_lora_training"]
    task_version: Literal["0.1.0"]
    dataset_sha256: Sha256
    source_split: Literal["train", "validation"]
    fixture_evidence: Literal[False]
    example_ids: list[str] = Field(min_length=1)
    record_sha256s: dict[str, Sha256]
    selection_rule: str
    content_sha256: Sha256


def build_subset_manifests(dataset_directory: Path) -> tuple[SubsetManifest, SubsetManifest]:
    dataset = DatasetManifest.model_validate_json(
        (dataset_directory / "manifest.json").read_bytes(), strict=True
    )
    validation_examples = load_examples(dataset_directory, list(_VALIDATION_IDS))
    _require_split(validation_examples, "validation")

    train_examples = _training_examples(dataset_directory)
    validation = _manifest(
        subset_id="validation-diagnostic-v0.1.0",
        purpose="untouched_diagnostic",
        dataset_sha256=dataset.dataset_sha256,
        source_split="validation",
        examples=validation_examples,
        selection_rule=(
            "fixed variant 14 examples: four per family balancing execute, approval, "
            "abstention, and refusal or clarification"
        ),
    )
    training = _manifest(
        subset_id="micro-lora-train-v0.1.0",
        purpose="micro_lora_training",
        dataset_sha256=dataset.dataset_sha256,
        source_split="train",
        examples=train_examples,
        selection_rule="variants 00 and 01 from each of the 16 archetypes",
    )
    return validation, training


def write_subset_manifests(dataset_directory: Path, output_root: Path) -> Path:
    validation, training = build_subset_manifests(dataset_directory)
    bundle_hash = content_sha256([validation.content_sha256, training.content_sha256])
    return write_atomic_bundle(
        output_root,
        f"subsets-{bundle_hash[:16]}",
        {
            "validation-diagnostic.json": canonical_json_bytes(validation) + b"\n",
            "micro-lora-train.json": canonical_json_bytes(training) + b"\n",
        },
    )


def _training_examples(dataset_directory: Path) -> list[OpsRouteExample]:
    examples: list[OpsRouteExample] = []
    with (dataset_directory / "train.jsonl").open("r", encoding="utf-8") as handle:
        import json

        for line in handle:
            candidate = OpsRouteExample.model_validate(json.loads(line), strict=True)
            match = _VARIANT_PATTERN.search(candidate.example_id)
            if match is not None and int(match.group(1)) in {0, 1}:
                examples.append(candidate)
    examples.sort(key=lambda example: example.example_id)
    if len(examples) != 32:
        raise ValueError(f"training subset resolved {len(examples)} records instead of 32")
    _require_split(examples, "train")
    archetype_counts: dict[tuple[str, str], int] = {}
    for example in examples:
        key = (example.scenario_family, example.archetype)
        archetype_counts[key] = archetype_counts.get(key, 0) + 1
    if len(archetype_counts) != 16 or set(archetype_counts.values()) != {2}:
        raise ValueError("training subset must contain two examples from every archetype")
    return examples


def _manifest(
    *,
    subset_id: str,
    purpose: Literal["untouched_diagnostic", "micro_lora_training"],
    dataset_sha256: str,
    source_split: Literal["train", "validation"],
    examples: list[OpsRouteExample],
    selection_rule: str,
) -> SubsetManifest:
    payload = {
        "schema_version": "blocker-subset-v0.1",
        "subset_id": subset_id,
        "purpose": purpose,
        "task_version": "0.1.0",
        "dataset_sha256": dataset_sha256,
        "source_split": source_split,
        "fixture_evidence": False,
        "example_ids": [example.example_id for example in examples],
        "record_sha256s": {example.example_id: example.record_sha256 for example in examples},
        "selection_rule": selection_rule,
    }
    return SubsetManifest.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _require_split(examples: list[OpsRouteExample], split: Literal["train", "validation"]) -> None:
    wrong = [example.example_id for example in examples if example.split != split]
    if wrong:
        raise ValueError(f"subset contains records outside {split}: {wrong}")
    if any(example.example_id.startswith("fixture_") for example in examples):
        raise ValueError("fixture evidence is prohibited")
