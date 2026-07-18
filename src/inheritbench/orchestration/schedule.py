"""Deterministic whole-sequence training schedules."""

from __future__ import annotations

import math
from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256, sha256_file, sha256_text
from inheritbench.capability.schemas import (
    CapabilityLabeledRecord,
    StrategyProfile,
    TrainingProfile,
)
from inheritbench.model_adapters.schemas import ScheduleItem, TrainingSchedule


def build_schedule(
    *,
    records: list[CapabilityLabeledRecord],
    sequence_lengths: dict[str, int],
    profile: TrainingProfile,
    namespace: str,
    seed: int,
) -> TrainingSchedule:
    if not records:
        raise ValueError("cannot build a training schedule without records")
    record_map = {record.record_id: record for record in records}
    if set(record_map) != set(sequence_lengths):
        raise ValueError("sequence lengths do not cover training records exactly")
    items: list[ScheduleItem] = []
    processed = 0
    cycle = 0
    cursor = 0
    while True:
        ordered = sorted(
            record_map,
            key=lambda record_id: sha256_text(f"{seed}:{namespace}:{cycle}:{record_id}"),
        )
        added = False
        for record_id in ordered:
            tokens = sequence_lengths[record_id]
            if processed + tokens > profile.target_processed_tokens:
                continue
            items.append(
                ScheduleItem(
                    cursor=cursor,
                    record_id=record_id,
                    sequence_tokens=tokens,
                    cycle=cycle,
                    accumulation_group=cursor // profile.gradient_accumulation_steps,
                    optimizer_step=cursor // profile.gradient_accumulation_steps + 1,
                )
            )
            processed += tokens
            cursor += 1
            added = True
        if not added or processed >= profile.target_processed_tokens:
            break
        cycle += 1
        if cycle > 10000:
            raise RuntimeError("schedule cycle limit exceeded")
    if not items:
        raise ValueError("token budget is smaller than every training sequence")
    optimizer_steps = math.ceil(len(items) / profile.gradient_accumulation_steps)
    warmup_steps = math.ceil(optimizer_steps * profile.warmup_ratio)
    checkpoints = sorted(
        {
            max(1, min(optimizer_steps, math.ceil(optimizer_steps * fraction)))
            for fraction in profile.checkpoint_fractions
        }
    )
    order_hash = content_sha256([item.model_dump(mode="json") for item in items])
    schedule_id = f"schedule-{order_hash[:16]}"
    body = {
        "schema_version": "inheritbench.training-schedule.v0.2",
        "schedule_id": schedule_id,
        "policy_type": "deterministic-hash-v0.1",
        "seed": seed,
        "namespace": namespace,
        "items": [item.model_dump(mode="json") for item in items],
        "processed_tokens": processed,
        "residual_tokens": profile.target_processed_tokens - processed,
        "optimizer_steps": optimizer_steps,
        "warmup_steps": warmup_steps,
        "checkpoint_steps": checkpoints,
        "order_sha256": order_hash,
    }
    body["content_sha256"] = content_sha256(body)
    return TrainingSchedule.model_validate(body, strict=True)


def resolve_schedule(
    *,
    records: list[CapabilityLabeledRecord],
    sequence_lengths: dict[str, int],
    profile: StrategyProfile,
    pack_root: Path,
    seed: int,
) -> TrainingSchedule:
    policy = profile.schedule_policy
    if policy.type == "deterministic-hash-v0.1":
        return build_schedule(
            records=records,
            sequence_lengths=sequence_lengths,
            profile=profile.training,
            namespace=policy.namespace,
            seed=seed,
        )
    path = (pack_root / policy.artifact).resolve()
    if pack_root.resolve() not in path.parents:
        raise ValueError("frozen schedule escapes the capability-pack root")
    if sha256_file(path) != policy.sha256:
        raise ValueError("frozen schedule hash mismatch")
    schedule = TrainingSchedule.model_validate_json(path.read_bytes(), strict=True)
    if schedule.policy_type != "frozen-record-order-v0.1":
        raise ValueError("frozen schedule artifact declares the wrong policy")
    if schedule.seed != seed:
        raise ValueError("frozen schedule seed differs from the plan")
    record_ids = {record.record_id for record in records}
    schedule_ids = {item.record_id for item in schedule.items}
    if schedule_ids != record_ids:
        raise ValueError("frozen schedule does not cover supervision records exactly")
    for item in schedule.items:
        if sequence_lengths.get(item.record_id) != item.sequence_tokens:
            raise ValueError(f"frozen schedule token mismatch for {item.record_id}")
        expected_group = item.cursor // profile.training.gradient_accumulation_steps
        if item.accumulation_group != expected_group or item.optimizer_step != expected_group + 1:
            raise ValueError("frozen schedule accumulation boundary mismatch")
    if schedule.processed_tokens != sum(item.sequence_tokens for item in schedule.items):
        raise ValueError("frozen schedule processed-token mismatch")
    if schedule.optimizer_steps != math.ceil(
        len(schedule.items) / profile.training.gradient_accumulation_steps
    ):
        raise ValueError("frozen schedule optimizer-step mismatch")
    body = schedule.model_dump(mode="json")
    stored = body.pop("content_sha256")
    if content_sha256(body) != stored:
        raise ValueError("frozen schedule content hash mismatch")
    return schedule
