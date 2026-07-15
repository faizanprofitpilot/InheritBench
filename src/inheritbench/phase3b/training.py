"""Phase 3B schedule, mixed-label encoding, and anchored OLMo training."""

from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_text
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.day3_matched.distribution import _local_snapshot
from inheritbench.models.loader import LoadedModel
from inheritbench.models.prompts import build_messages, render_prompt
from inheritbench.phase3b.config import (
    load_experiment_config,
    load_method_config,
    resolve,
)
from inheritbench.phase3b.confirmatory import find_confirmatory_bundle
from inheritbench.phase3b.schemas import (
    ConfirmatoryLeakageAuditV0_1,
    HybridScheduleItem,
    HybridTrainingRecordV0_1,
    HybridTrainingScheduleV0_1,
)
from inheritbench.phase3b.selection import find_hybrid_dataset, load_hybrid_records

_SCHEDULE_EXCLUSIONS = {"schedule_id", "created_at", "content_sha256"}


def freeze_schedule(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    method_path = resolve(experiment_path, experiment.method_config_path)
    method = load_method_config(method_path)
    dataset_path, dataset = find_hybrid_dataset(experiment_path)
    records = load_hybrid_records(dataset_path)
    if len(records) != 224:
        raise ValueError("Phase 3B schedule requires exactly 224 hybrid records")
    find_confirmatory_bundle(experiment_path)
    _require_leakage_audit(experiment_path)
    target = load_model_config(resolve(method_path, method.model_config_path))
    from transformers import AutoTokenizer

    tokenizer: Any = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        _local_snapshot(target.tokenizer_id, target.tokenizer_revision),
        trust_remote_code=False,
        local_files_only=True,
    )
    token_counts = {
        item.training_record_id: training_sequence_length(tokenizer, item) for item in records
    }
    by_id = {item.training_record_id: item for item in records}
    remaining: int = method.target_processed_tokens
    items: list[HybridScheduleItem] = []
    cycle = 0
    while remaining:
        added = False
        ordered = sorted(
            token_counts,
            key=lambda record_id: sha256_text(
                f"20260714:phase3b-hybrid-schedule-v0.1:cycle:{cycle}:{record_id}"
            ),
        )
        for record_id in ordered:
            tokens = token_counts[record_id]
            if tokens <= remaining:
                record = by_id[record_id]
                items.append(
                    HybridScheduleItem(
                        cursor=len(items),
                        cycle=cycle,
                        training_record_id=record_id,
                        label_origin=record.label_origin,
                        sequence_tokens=tokens,
                    )
                )
                remaining -= tokens
                added = True
        if not added:
            break
        cycle += 1
    exposures = Counter(item.training_record_id for item in items)
    origin_exposures = Counter(item.label_origin for item in items)
    if max(exposures.values()) - min(exposures.values()) > 1:
        raise ValueError("whole-dataset schedule preferentially exposes some records")
    processed = sum(item.sequence_tokens for item in items)
    optimizer_steps = math.ceil(len(items) / method.training.gradient_accumulation_steps)
    checkpoints = [
        math.ceil(optimizer_steps / 3),
        math.ceil(2 * optimizer_steps / 3),
        optimizer_steps,
    ]
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase3b-hybrid-schedule-v0.1",
        "schedule_id": "pending",
        "hybrid_dataset_sha256": dataset.content_sha256,
        "tokenizer_id": target.tokenizer_id,
        "tokenizer_revision": target.tokenizer_revision,
        "seed": 20260714,
        "ordering_namespace": "phase3b-hybrid-schedule-v0.1",
        "target_processed_tokens": method.target_processed_tokens,
        "processed_tokens": processed,
        "residual_tokens": method.target_processed_tokens - processed,
        "budget_ratio": processed / method.target_processed_tokens,
        "unique_examples": 224,
        "total_exposures": len(items),
        "optimizer_steps": optimizer_steps,
        "warmup_steps": math.ceil(optimizer_steps * method.training.warmup_ratio),
        "checkpoint_steps": checkpoints,
        "token_counts": dict(sorted(token_counts.items())),
        "exposure_counts_by_record": dict(sorted(exposures.items())),
        "exposure_counts_by_origin": dict(sorted(origin_exposures.items())),
        "items": [item.model_dump(mode="json") for item in items],
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_SCHEDULE_EXCLUSIONS)
    schedule_id = f"phase3b-hybrid-schedule-{identity[:16]}"
    schedule = HybridTrainingScheduleV0_1.model_validate(
        {**payload, "schedule_id": schedule_id, "content_sha256": identity}, strict=True
    )
    return write_atomic_bundle(
        resolve(experiment_path, experiment.artifact_root) / "schedules",
        schedule_id,
        {"schedule.json": canonical_json_bytes(schedule) + b"\n"},
    )


def find_schedule(experiment_path: Path) -> tuple[Path, HybridTrainingScheduleV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "schedules"
    paths = sorted(root.glob("*/schedule.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one frozen Phase 3B schedule, found {len(paths)}")
    return paths[0].parent, HybridTrainingScheduleV0_1.model_validate_json(
        paths[0].read_bytes(), strict=True
    )


def training_sequence_length(tokenizer: Any, record: HybridTrainingRecordV0_1) -> int:
    prompt = render_prompt(tokenizer, record, "0.1.0")
    messages = [
        *build_messages(record, "0.1.0"),
        {"role": "assistant", "content": record.assistant_label},
    ]
    full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"assistant template changed prompt prefix: {record.training_record_id}")
    if len(full_ids) > 1024:
        raise ValueError(f"training sequence exceeds 1024 tokens: {record.training_record_id}")
    return len(full_ids)


def encode_training_record(loaded: LoadedModel, record: HybridTrainingRecordV0_1) -> dict[str, Any]:
    prompt = render_prompt(loaded.tokenizer, record, "0.1.0")
    messages = [
        *build_messages(record, "0.1.0"),
        {"role": "assistant", "content": record.assistant_label},
    ]
    full = loaded.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    prompt_ids = loaded.tokenizer(prompt, add_special_tokens=False)["input_ids"]
    encoded = loaded.tokenizer(full, return_tensors="pt", add_special_tokens=False)
    if encoded["input_ids"].shape[1] > 1024:
        raise ValueError(f"training record exceeds 1024 tokens: {record.training_record_id}")
    if encoded["input_ids"][0, : len(prompt_ids)].tolist() != prompt_ids:
        raise ValueError(f"training prompt prefix mismatch: {record.training_record_id}")
    labels = encoded["input_ids"].clone()
    labels[:, : len(prompt_ids)] = -100
    batch = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
    batch["labels"] = labels.to(loaded.device)
    return batch


def _require_leakage_audit(experiment_path: Path) -> ConfirmatoryLeakageAuditV0_1:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "leakage-audits"
    paths = sorted(root.glob("*/audit.json"))
    if len(paths) != 1:
        raise ValueError("Phase 3B schedule requires one confirmatory leakage audit")
    audit = ConfirmatoryLeakageAuditV0_1.model_validate_json(paths[0].read_bytes(), strict=True)
    if audit.status != "PASS":
        raise ValueError("Phase 3B schedule requires a passing leakage audit")
    return audit
