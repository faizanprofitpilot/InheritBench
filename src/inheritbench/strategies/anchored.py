"""Generic anchored behavioral-transfer supervision."""

from __future__ import annotations

from inheritbench.artifacts.hashing import (
    content_sha256,
    sha256_text,
)
from inheritbench.capability.evaluator import evaluate_output
from inheritbench.capability.loader import LoadedCapabilityPack
from inheritbench.capability.schemas import CapabilityLabeledRecord
from inheritbench.model_adapters.schemas import GenerationOutput
from inheritbench.strategies.schemas import (
    GroupDeficit,
    SupervisionAccounting,
    SupervisionResult,
    TeacherEvaluationResult,
)


def prepare_anchored_supervision(
    pack: LoadedCapabilityPack,
    teacher_outputs: list[GenerationOutput],
    *,
    minimum_examples_per_group: int,
    teacher_selection_namespace: str,
    anchor_selection_namespace: str,
    teacher_stage_sha256: str,
    anchors: list[CapabilityLabeledRecord] | None = None,
) -> SupervisionResult:
    evaluation = evaluate_teacher_outputs(
        pack,
        teacher_outputs,
        teacher_stage_sha256=teacher_stage_sha256,
    )
    selected = select_teacher_supervision(
        pack,
        evaluation,
        minimum_examples_per_group=minimum_examples_per_group,
        teacher_selection_namespace=teacher_selection_namespace,
    )
    return finalize_anchored_supervision(
        selected,
        anchors=anchors if anchors is not None else pack.anchors,
        anchor_selection_namespace=anchor_selection_namespace,
    )


def evaluate_teacher_outputs(
    pack: LoadedCapabilityPack,
    teacher_outputs: list[GenerationOutput],
    *,
    teacher_stage_sha256: str,
) -> TeacherEvaluationResult:
    input_map = {record.record_id: record for record in pack.inputs["transfer_pool"]}
    oracle_map = pack.oracle_map("transfer_pool")
    output_map = {output.record_id: output for output in teacher_outputs}
    if set(output_map) != set(input_map):
        raise ValueError("teacher outputs must cover every transfer-pool input exactly once")
    accepted: list[CapabilityLabeledRecord] = []
    rejected: list[str] = []
    for record_id in sorted(input_map):
        record = input_map[record_id]
        output = output_map[record_id]
        if output.status != "COMPLETED" or not output.raw_output.strip():
            rejected.append(record_id)
            continue
        evaluation = evaluate_output(
            record=record,
            oracle=oracle_map[record_id],
            raw_output=output.raw_output,
            config=pack.evaluator,
            output_schema=pack.output_schema,
            cross_field_schema=pack.cross_field_schema,
            vocabularies=pack.vocabularies,
            safety_rules=pack.safety_rules,
            trusted_plugin=pack.trusted_plugin,
        )
        if (
            evaluation.parser_classification != "STRICT_VALID"
            or not evaluation.semantic_match
            or any(item.severity == "blocker" for item in evaluation.safety_findings)
        ):
            rejected.append(record_id)
            continue
        label = evaluation.strict_candidate
        labeled_payload = {
            "schema_version": "inheritbench.capability-labeled-record.v0.2",
            "record_id": record_id,
            "input_record": record,
            "assistant_label": label,
            "label_origin": "teacher",
            "assistant_label_sha256": sha256_text(label),
        }
        labeled_payload["content_sha256"] = content_sha256(labeled_payload)
        labeled = CapabilityLabeledRecord.model_validate(labeled_payload, strict=True)
        accepted.append(labeled)

    body = {
        "schema_version": "inheritbench.teacher-evaluation.v0.1",
        "strategy_id": "anchored-behavioral-transfer-v0.1",
        "accepted_records": sorted(accepted, key=lambda item: item.record_id),
        "rejected_record_ids": sorted(rejected),
        "teacher_stage_sha256": teacher_stage_sha256,
    }
    body["content_sha256"] = content_sha256(body)
    return TeacherEvaluationResult.model_validate(body, strict=True)


def select_teacher_supervision(
    pack: LoadedCapabilityPack,
    evaluation: TeacherEvaluationResult,
    *,
    minimum_examples_per_group: int,
    teacher_selection_namespace: str,
) -> SupervisionResult:
    accepted: dict[str, list[CapabilityLabeledRecord]] = {}
    for record in evaluation.accepted_records:
        accepted.setdefault(record.input_record.group, []).append(record)

    selected: list[CapabilityLabeledRecord] = []
    deficits: list[GroupDeficit] = []
    all_groups = sorted(record.group for record in pack.inputs["transfer_pool"])
    all_groups = sorted(set(all_groups))
    for group in all_groups:
        teacher_group = sorted(
            accepted.get(group, []),
            key=lambda item: sha256_text(f"{teacher_selection_namespace}:{item.record_id}"),
        )
        selected_teacher = teacher_group[:minimum_examples_per_group]
        selected.extend(selected_teacher)
        need = minimum_examples_per_group - len(selected_teacher)
        if need > 0:
            deficits.append(
                GroupDeficit(
                    group=group,
                    required=minimum_examples_per_group,
                    accepted_teacher=len(selected_teacher),
                    accepted_anchors=0,
                    deficit=need,
                )
            )
    return SupervisionResult(
        status="ANCHORS_REQUIRED" if deficits else "FROZEN",
        strategy_id="anchored-behavioral-transfer-v0.1",
        records=sorted(selected, key=lambda item: item.record_id),
        deficits=deficits,
        accounting=SupervisionAccounting(
            direct_labels=0,
            anchor_labels=0,
            teacher_labels=len(selected),
            upstream_original_labels=int(
                pack.readiness_rules.get("accounting", {}).get(
                    "upstream_original_labels_used_to_train_teacher", 0
                )
            ),
            candidate_inputs=len(pack.inputs["transfer_pool"]),
            accepted_teacher_outputs=len(evaluation.accepted_records),
            rejected_teacher_outputs=len(evaluation.rejected_record_ids),
            selected_training_records=len(selected),
        ),
        rejected_record_ids=evaluation.rejected_record_ids,
        teacher_stage_sha256=evaluation.teacher_stage_sha256,
    )


def finalize_anchored_supervision(
    selected_teacher: SupervisionResult,
    *,
    anchors: list[CapabilityLabeledRecord],
    anchor_selection_namespace: str,
) -> SupervisionResult:
    if selected_teacher.strategy_id != "anchored-behavioral-transfer-v0.1":
        raise ValueError("teacher selection has the wrong strategy")
    anchors_by_group: dict[str, list[CapabilityLabeledRecord]] = {}
    for anchor in anchors:
        if anchor.label_origin != "anchor":
            raise ValueError("anchor files may contain only label_origin=anchor")
        anchors_by_group.setdefault(anchor.input_record.group, []).append(anchor)
    selected_anchors: list[CapabilityLabeledRecord] = []
    remaining_deficits: list[GroupDeficit] = []
    for deficit in selected_teacher.deficits:
        ranked = sorted(
            anchors_by_group.get(deficit.group, []),
            key=lambda item: sha256_text(f"{anchor_selection_namespace}:{item.record_id}"),
        )
        chosen = ranked[: deficit.deficit]
        selected_anchors.extend(chosen)
        remaining = deficit.deficit - len(chosen)
        if remaining:
            remaining_deficits.append(
                GroupDeficit(
                    group=deficit.group,
                    required=deficit.required,
                    accepted_teacher=deficit.accepted_teacher,
                    accepted_anchors=len(chosen),
                    deficit=remaining,
                )
            )
    records = sorted(
        [*selected_teacher.records, *selected_anchors],
        key=lambda item: item.record_id,
    )
    accounting = selected_teacher.accounting.model_copy(
        update={
            "direct_labels": len(selected_anchors),
            "anchor_labels": len(selected_anchors),
            "selected_training_records": len(records),
        }
    )
    return SupervisionResult(
        status="ANCHORS_REQUIRED" if remaining_deficits else "FROZEN",
        strategy_id=selected_teacher.strategy_id,
        records=records,
        deficits=remaining_deficits,
        accounting=accounting,
        rejected_record_ids=selected_teacher.rejected_record_ids,
        teacher_stage_sha256=selected_teacher.teacher_stage_sha256,
    )


def normalized_teacher_outputs(
    records: list[dict[str, object]],
) -> list[GenerationOutput]:
    outputs: list[GenerationOutput] = []
    for record in records:
        raw_output = record.get("raw_output")
        if not isinstance(raw_output, str):
            raw_output = ""
        record_id = str(record["record_id"])
        outputs.append(
            GenerationOutput(
                record_id=record_id,
                status="COMPLETED" if raw_output else "FAILED",
                raw_output=raw_output,
                prompt_sha256=str(record["prompt_sha256"]),
                input_ids_sha256=str(record["input_ids_sha256"]),
                prompt_tokens=_integer(record.get("prompt_tokens", 0)),
                completion_tokens=_integer(record.get("completion_tokens", 0)),
                error=None if raw_output else "historical teacher output missing",
                latency_ms=_integer(record.get("latency_ms", 0)),
            )
        )
    return outputs


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("normalized teacher numeric field must be an integer")
    return value
