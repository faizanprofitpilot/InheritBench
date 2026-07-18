"""Direct-label target LoRA supervision preparation."""

from __future__ import annotations

from inheritbench.capability.loader import LoadedCapabilityPack
from inheritbench.strategies.schemas import SupervisionAccounting, SupervisionResult


def prepare_direct_supervision(pack: LoadedCapabilityPack) -> SupervisionResult:
    if not pack.direct_train:
        return SupervisionResult(
            status="FAILED",
            strategy_id="direct-target-lora-v0.1",
            records=[],
            deficits=[],
            accounting=SupervisionAccounting(
                direct_labels=0,
                anchor_labels=0,
                teacher_labels=0,
                upstream_original_labels=0,
                candidate_inputs=0,
                accepted_teacher_outputs=0,
                rejected_teacher_outputs=0,
                selected_training_records=0,
            ),
            rejected_record_ids=[],
            teacher_stage_sha256=None,
        )
    record_ids = [record.record_id for record in pack.direct_train]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("direct training records contain duplicate IDs")
    return SupervisionResult(
        status="FROZEN",
        strategy_id="direct-target-lora-v0.1",
        records=sorted(pack.direct_train, key=lambda item: item.record_id),
        deficits=[],
        accounting=SupervisionAccounting(
            direct_labels=len(pack.direct_train),
            anchor_labels=0,
            teacher_labels=0,
            upstream_original_labels=0,
            candidate_inputs=0,
            accepted_teacher_outputs=0,
            rejected_teacher_outputs=0,
            selected_training_records=len(pack.direct_train),
        ),
        rejected_record_ids=[],
        teacher_stage_sha256=None,
    )
