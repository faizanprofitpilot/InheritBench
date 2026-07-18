"""Execute and resume the generic immutable succession graph."""

from __future__ import annotations

import json
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.store import write_atomic_bundle, write_atomic_file
from inheritbench.capability.loader import load_capability_pack, validate_added_anchors
from inheritbench.capability.schemas import CapabilityLabeledRecord, StrategyProfile
from inheritbench.config import load_model_config
from inheritbench.model_adapters.registry import default_registry
from inheritbench.model_adapters.schemas import (
    GenerationOutput,
    TrainingInitialization,
    TrainingResult,
)
from inheritbench.orchestration.broker import StageDataBroker
from inheritbench.orchestration.evaluation import (
    checkpoint_decision,
    evaluate_generations,
    summarize,
)
from inheritbench.orchestration.planner import verify_plan_inputs
from inheritbench.orchestration.readiness import derive_readiness
from inheritbench.orchestration.replay import replay_run
from inheritbench.orchestration.schedule import resolve_schedule
from inheritbench.orchestration.schemas import (
    CheckpointDecision,
    EvaluationRecord,
    FinalizedWebBundle,
    StageManifest,
    SuccessionPlan,
    SurfaceSummary,
)
from inheritbench.orchestration.storage import (
    finalize_active,
    latest_stage,
    load_plan,
    write_final_file,
    write_stage,
)
from inheritbench.strategies.anchored import (
    evaluate_teacher_outputs,
    finalize_anchored_supervision,
    prepare_anchored_supervision,
    select_teacher_supervision,
)
from inheritbench.strategies.direct_lora import prepare_direct_supervision
from inheritbench.strategies.schemas import SupervisionResult, TeacherEvaluationResult


def execute_run(run_directory: Path) -> Path:
    return _execute(run_directory.resolve(), resume=False)


def resume_run(run_directory: Path) -> Path:
    return _execute(run_directory.resolve(), resume=True)


def add_anchors(run_directory: Path, records_path: Path) -> Path:
    run_directory = run_directory.resolve()
    plan = load_plan(run_directory)
    if plan.strategy_id != "anchored-behavioral-transfer-v0.1":
        raise ValueError("anchors may only be added to anchored transfer runs")
    current = latest_stage(run_directory)
    if current is None or current.stage != "ANCHORS_REQUIRED":
        raise ValueError("run is not waiting for anchors")
    records = _load_labeled(records_path)
    if not records:
        raise ValueError("anchor file is empty")
    pack = load_capability_pack(
        Path(plan.pack_root),
        allow_fixture=True,
        require_executable=True,
    )
    validate_added_anchors(pack, records)
    deficit_groups = {
        item["group"]: int(item["deficit"]) for item in current.payload["supervision"]["deficits"]
    }
    if plan.schema_version == "inheritbench.succession-plan.v0.3":
        binding = plan.authorized_anchor_pool
        if binding is None:
            raise ValueError("anchored v0.3 plan lacks an authorized anchor pool")
        if records_path.stat().st_size != binding.bytes:
            raise ValueError("anchor pool byte count differs from the immutable plan")
        if sha256_file(records_path) != binding.byte_sha256:
            raise ValueError("anchor pool hash differs from the immutable plan")
        records_sha256 = content_sha256([item.model_dump(mode="json") for item in records])
        if len(records) != binding.records or records_sha256 != binding.records_sha256:
            raise ValueError("anchor pool record identity differs from the immutable plan")
        selected: list[CapabilityLabeledRecord] = []
        ranks = {
            record.record_id: sha256_text(f"{binding.ranking_namespace}:{record.record_id}")
            for record in records
        }
        selected_by_group: dict[str, list[str]] = {}
        eligible_by_group: dict[str, list[str]] = {}
        for group, deficit in sorted(deficit_groups.items()):
            eligible = sorted(
                (record for record in records if record.input_record.group == group),
                key=lambda item: ranks[item.record_id],
            )
            if len(eligible) < deficit:
                raise ValueError(f"authorized anchor pool cannot satisfy deficit for {group}")
            chosen = eligible[:deficit]
            selected.extend(chosen)
            eligible_by_group[group] = [item.record_id for item in eligible]
            selected_by_group[group] = [item.record_id for item in chosen]
        if len(selected) != sum(deficit_groups.values()):
            raise ValueError("selected anchor count does not equal the declared deficit")
        selected_ids = {item.record_id for item in selected}
        unselected_ids = sorted(
            (item.record_id for item in records if item.record_id not in selected_ids),
            key=lambda record_id: ranks[record_id],
        )
        selected = sorted(selected, key=lambda item: item.record_id)
        counts = {group: len(ids) for group, ids in sorted(selected_by_group.items())}
        manifest: dict[str, Any] = {
            "schema_version": "inheritbench.anchor-intervention.v0.2",
            "run_id": plan.run_id,
            "canonical_plan_id": plan.canonical_plan_id,
            "execution_id": plan.execution_id,
            "authorized_pool_byte_sha256": binding.byte_sha256,
            "authorized_pool_records_sha256": binding.records_sha256,
            "ranking_namespace": binding.ranking_namespace,
            "eligible_by_group": eligible_by_group,
            "selected_by_group": selected_by_group,
            "selected_ids": [item.record_id for item in selected],
            "unselected_ids": unselected_ids,
            "selection_ranks": dict(sorted(ranks.items())),
            "records": len(selected),
            "groups": counts,
            "records_sha256": content_sha256([item.model_dump(mode="json") for item in selected]),
            "parent_stage_sha256": current.content_sha256,
        }
        manifest["content_sha256"] = content_sha256(manifest)
    else:
        selected = records
        legacy_counts: dict[str, int] = {}
        for record in selected:
            group = record.input_record.group
            legacy_counts[group] = legacy_counts.get(group, 0) + 1
            if group not in deficit_groups:
                raise ValueError(f"anchor group {group} has no declared deficit")
        for group, count in legacy_counts.items():
            if count > deficit_groups[group]:
                raise ValueError(f"too many anchors for {group}")
        manifest = {
            "schema_version": "inheritbench.anchor-intervention.v0.1",
            "run_id": plan.run_id,
            "records": len(selected),
            "groups": legacy_counts,
            "records_sha256": content_sha256([item.model_dump(mode="json") for item in selected]),
            "parent_stage_sha256": current.content_sha256,
        }
    payload = b"".join(canonical_json_bytes(record) + b"\n" for record in selected)
    intervention_id = f"anchors-{manifest['records_sha256'][:16]}"
    manifest["intervention_id"] = intervention_id
    if manifest["schema_version"] == "inheritbench.anchor-intervention.v0.2":
        manifest["content_sha256"] = content_sha256(manifest, excluded_keys={"content_sha256"})
    destination = write_atomic_bundle(
        run_directory / "interventions",
        intervention_id,
        {
            "anchors.jsonl": payload,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )
    if plan.schema_version == "inheritbench.succession-plan.v0.3":
        write_stage(
            run_directory,
            stage="ANCHORS_ADDED",
            sequence=current.sequence + 1,
            parent_stage_sha256=current.content_sha256,
            status="COMPLETED",
            payload={"intervention": manifest},
        )
    return destination


def _execute(run_directory: Path, *, resume: bool) -> Path:
    plan = load_plan(run_directory)
    existing_current = latest_stage(run_directory)
    if existing_current is not None and existing_current.stage == "COMPLETED":
        verify_plan_inputs(plan)
        return run_directory
    if existing_current is not None and existing_current.status == "FAILED":
        raise ValueError(f"run is terminal: {existing_current.stage}")
    try:
        verify_plan_inputs(plan)
        pack = load_capability_pack(
            Path(plan.pack_root),
            allow_fixture=True,
            require_executable=True,
        )
        if pack.validation.content_sha256 != plan.pack_validation_sha256:
            raise ValueError("capability validation changed after planning")
        source_config = load_model_config(Path(plan.source_config_path))
        target_config = load_model_config(Path(plan.target_config_path))
        registry = default_registry()
        source_adapter = registry.resolve(plan.source_registry_id, source_config)
        target_adapter = registry.resolve(plan.target_registry_id, target_config)
        profile = StrategyProfile.model_validate(plan.strategy_profile, strict=True)
    except BaseException as exc:
        current = latest_stage(run_directory)
        if current is None or current.status != "FAILED":
            _terminal(
                run_directory,
                _failure_state(exc),
                0 if current is None else current.sequence + 1,
                None if current is None else current.content_sha256,
                {"error": f"{type(exc).__name__}: {exc}"},
            )
        raise
    current = latest_stage(run_directory)
    if current is not None and not resume and current.stage != "PLAN_FROZEN":
        raise ValueError("existing run progress requires succession resume")

    stages = _stage_map(run_directory)
    parent = current.content_sha256 if current is not None else None
    sequence = current.sequence + 1 if current is not None else 0
    try:
        if "PACK_VALIDATED" not in stages:
            _, current = write_stage(
                run_directory,
                stage="PACK_VALIDATED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={
                    "validation_sha256": pack.validation.content_sha256,
                    "record_counts": pack.validation.record_counts,
                },
            )
            parent, sequence = current.content_sha256, sequence + 1
        if "MODELS_PREFLIGHTED" not in stages:
            source_identity = source_adapter.probe(
                source_config,
                device=plan.device,
                adapter_directory=_source_adapter_directory(plan),
            )
            target_identity = target_adapter.probe(target_config, device=plan.device)
            _, current = write_stage(
                run_directory,
                stage="MODELS_PREFLIGHTED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={
                    "source": source_identity.model_dump(mode="json"),
                    "target": target_identity.model_dump(mode="json"),
                },
            )
            parent, sequence = current.content_sha256, sequence + 1
        if "PLAN_FROZEN" not in stages:
            _, current = write_stage(
                run_directory,
                stage="PLAN_FROZEN",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={"plan_sha256": plan.plan_sha256},
            )
            parent, sequence = current.content_sha256, sequence + 1
        stages = _stage_map(run_directory)
        source_records, source_summary = _evaluate_surface(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            config=source_config,
            adapter=source_adapter,
            surface="source_gate",
            stage="SOURCE_GATE_COMPLETED",
            system_role="source",
            adapter_directory=_source_adapter_directory(plan),
            sequence=sequence,
            parent=parent,
            existing=stages.get("SOURCE_GATE_COMPLETED"),
        )
        if "SOURCE_GATE_COMPLETED" not in stages:
            latest = latest_stage(run_directory)
            assert latest is not None
            parent, sequence = latest.content_sha256, latest.sequence + 1
        if not _surface_passes(
            source_summary,
            _rules(pack.readiness_rules, "source_gate", fallback="clean"),
        ):
            return _terminal(
                run_directory,
                "SOURCE_CAPABILITY_GATE_FAILED",
                sequence,
                parent,
                {"summary": source_summary.model_dump(mode="json")},
            )
        stages = _stage_map(run_directory)
        target_base_records, target_base_summary = _evaluate_surface(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            config=target_config,
            adapter=target_adapter,
            surface="source_gate",
            stage="TARGET_BASELINE_COMPLETED",
            system_role="target_base",
            adapter_directory=None,
            sequence=sequence,
            parent=parent,
            existing=stages.get("TARGET_BASELINE_COMPLETED"),
        )
        if "TARGET_BASELINE_COMPLETED" not in stages:
            latest = latest_stage(run_directory)
            assert latest is not None
            parent, sequence = latest.content_sha256, latest.sequence + 1
        stages = _stage_map(run_directory)
        supervision = _supervision(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            source_config=source_config,
            source_adapter=source_adapter,
            profile=profile,
            sequence=sequence,
            parent=parent,
            stages=stages,
        )
        if supervision.status == "ANCHORS_REQUIRED":
            return run_directory
        if supervision.status != "FROZEN":
            return _terminal(
                run_directory,
                "SUPERVISION_GATE_FAILED",
                sequence,
                parent,
                {"supervision": supervision.model_dump(mode="json")},
            )
        latest = latest_stage(run_directory)
        assert latest is not None
        parent, sequence = latest.content_sha256, latest.sequence + 1
        stages = _stage_map(run_directory)
        training_result = _training(
            run_directory=run_directory,
            plan=plan,
            target_config=target_config,
            target_adapter=target_adapter,
            profile=profile,
            supervision=supervision,
            maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
            sequence=sequence,
            parent=parent,
            existing=stages.get("TRAINING"),
        )
        if training_result.status != "COMPLETED":
            return _terminal(
                run_directory,
                "EXECUTION_FAILED",
                sequence,
                parent,
                {"training": training_result.model_dump(mode="json")},
            )
        latest = latest_stage(run_directory)
        assert latest is not None
        parent, sequence = latest.content_sha256, latest.sequence + 1
        stages = _stage_map(run_directory)
        decision = _select_checkpoint(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            target_config=target_config,
            target_adapter=target_adapter,
            training=training_result,
            profile=profile,
            sequence=sequence,
            parent=parent,
            existing=stages.get("CHECKPOINT_SELECTED"),
        )
        if decision.status != "SELECTED":
            return _terminal(
                run_directory,
                "NO_SAFETY_ELIGIBLE_CHECKPOINT",
                sequence,
                parent,
                {"decision": decision.model_dump(mode="json")},
            )
        assert decision.selected_adapter_directory is not None
        assert decision.selected_adapter_sha256 is not None
        assert decision.selected_checkpoint_id is not None
        candidate_identity = target_adapter.verify_adapter(
            target_config,
            Path(decision.selected_adapter_directory),
            device=plan.device,
        )
        latest = latest_stage(run_directory)
        assert latest is not None
        parent, sequence = latest.content_sha256, latest.sequence + 1
        stages = _stage_map(run_directory)
        if (
            plan.schema_version == "inheritbench.succession-plan.v0.3"
            and "CANDIDATE_FROZEN" not in stages
        ):
            _, current = write_stage(
                run_directory,
                stage="CANDIDATE_FROZEN",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={
                    "checkpoint_id": decision.selected_checkpoint_id,
                    "adapter_sha256": decision.selected_adapter_sha256,
                    "fresh_base_reload": candidate_identity.model_dump(mode="json"),
                },
            )
            parent, sequence = current.content_sha256, sequence + 1
        stages = _stage_map(run_directory)
        confirmatory_records, confirmatory_summary = _evaluate_surface(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            config=target_config,
            adapter=target_adapter,
            surface="confirmatory",
            stage="CONFIRMATORY_COMPLETED",
            system_role="target_selected",
            adapter_directory=Path(decision.selected_adapter_directory),
            checkpoint_id=decision.selected_checkpoint_id,
            sequence=sequence,
            parent=parent,
            existing=stages.get("CONFIRMATORY_COMPLETED"),
        )
        if "CONFIRMATORY_COMPLETED" not in stages:
            latest = latest_stage(run_directory)
            assert latest is not None
            parent, sequence = latest.content_sha256, latest.sequence + 1
        stages = _stage_map(run_directory)
        adversarial_records, adversarial_summary = _evaluate_surface(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            config=target_config,
            adapter=target_adapter,
            surface="adversarial",
            stage="ADVERSARIAL_COMPLETED",
            system_role="target_selected",
            adapter_directory=Path(decision.selected_adapter_directory),
            checkpoint_id=decision.selected_checkpoint_id,
            sequence=sequence,
            parent=parent,
            existing=stages.get("ADVERSARIAL_COMPLETED"),
        )
        if "ADVERSARIAL_COMPLETED" not in stages:
            latest = latest_stage(run_directory)
            assert latest is not None
            parent, sequence = latest.content_sha256, latest.sequence + 1
        readiness = derive_readiness(
            run_id=plan.run_id,
            rules=pack.readiness_rules,
            source_gate=source_summary,
            target_baseline=target_base_summary,
            confirmatory=confirmatory_summary,
            adversarial=adversarial_summary,
            supervision=supervision.accounting,
            selected_checkpoint_id=decision.selected_checkpoint_id,
            adapter_sha256=decision.selected_adapter_sha256,
        )
        stages = _stage_map(run_directory)
        if "READINESS_FINALIZED" not in stages:
            _, current = write_stage(
                run_directory,
                stage="READINESS_FINALIZED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={"readiness": readiness.model_dump(mode="json")},
            )
            parent, sequence = current.content_sha256, sequence + 1
        successor = _export_adapter(
            run_directory,
            plan,
            target_adapter,
            target_config,
            decision,
        )
        stages = _stage_map(run_directory)
        if "ADAPTER_EXPORTED" not in stages:
            _, current = write_stage(
                run_directory,
                stage="ADAPTER_EXPORTED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload=successor,
            )
            parent, sequence = current.content_sha256, sequence + 1
        stages = _stage_map(run_directory)
        if (
            plan.schema_version == "inheritbench.succession-plan.v0.3"
            and "RELOAD_VERIFIED" not in stages
        ):
            _, current = write_stage(
                run_directory,
                stage="RELOAD_VERIFIED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={
                    "adapter_sha256": successor["adapter_sha256"],
                    "model": successor["model"],
                    "fresh_base_reload_verified": True,
                },
            )
            parent, sequence = current.content_sha256, sequence + 1
        _write_final_outputs(
            run_directory=run_directory,
            plan=plan,
            source_records=source_records,
            target_base_records=target_base_records,
            confirmatory_records=confirmatory_records,
            adversarial_records=adversarial_records,
            source_summary=source_summary,
            target_base_summary=target_base_summary,
            confirmatory_summary=confirmatory_summary,
            adversarial_summary=adversarial_summary,
            supervision=supervision,
            training=training_result,
            decision=decision,
            readiness=readiness,
            successor=successor,
            include_derived_bundle=(plan.schema_version == "inheritbench.succession-plan.v0.2"),
        )
        if plan.schema_version == "inheritbench.succession-plan.v0.3":
            replay_path = _ensure_replay(run_directory)
            replay_manifest = _json_file(replay_path / "replay_manifest.json")
            replay_receipt = _json_file(replay_path / "replay_receipt.json")
            _write_or_verify_json(run_directory / "replay_manifest.json", replay_manifest)
            _write_or_verify_json(run_directory / "replay_receipt.json", replay_receipt)
            stages = _stage_map(run_directory)
            if "REPLAY_VERIFIED" not in stages:
                latest = latest_stage(run_directory)
                assert latest is not None
                _, current = write_stage(
                    run_directory,
                    stage="REPLAY_VERIFIED",
                    sequence=latest.sequence + 1,
                    parent_stage_sha256=latest.content_sha256,
                    status="COMPLETED",
                    payload={
                        "replay_receipt_sha256": replay_receipt["content_sha256"],
                        "status": replay_receipt["status"],
                    },
                )
                parent, sequence = current.content_sha256, current.sequence + 1
        stages = _stage_map(run_directory)
        if "COMPLETED" not in stages:
            latest = latest_stage(run_directory)
            if latest is not None:
                parent, sequence = latest.content_sha256, latest.sequence + 1
            _, current = write_stage(
                run_directory,
                stage="COMPLETED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="COMPLETED",
                payload={
                    "readiness_status": readiness.status,
                    "readiness_sha256": readiness.content_sha256,
                    "adapter_sha256": decision.selected_adapter_sha256,
                },
            )
        if plan.schema_version == "inheritbench.succession-plan.v0.3":
            _write_v03_execution_evidence(run_directory, plan)
        finalize_active(run_directory)
        if plan.schema_version == "inheritbench.succession-plan.v0.2":
            replay_run(run_directory, output_root=run_directory / "replays")
        return run_directory
    except BaseException as exc:
        current = latest_stage(run_directory)
        if current is None or current.status != "FAILED":
            with suppress(BaseException):
                _terminal(
                    run_directory,
                    _failure_state(exc),
                    (current.sequence + 1) if current is not None else 0,
                    current.content_sha256 if current is not None else None,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
        raise


def _evaluate_surface(
    *,
    run_directory: Path,
    plan: SuccessionPlan,
    pack: Any,
    config: Any,
    adapter: Any,
    surface: str,
    stage: str,
    system_role: str,
    adapter_directory: Path | None,
    sequence: int,
    parent: str | None,
    existing: StageManifest | None,
    checkpoint_id: str | None = None,
) -> tuple[list[EvaluationRecord], SurfaceSummary]:
    if existing is not None:
        records = [
            EvaluationRecord.model_validate(item, strict=True)
            for item in existing.payload["records"]
        ]
        return records, SurfaceSummary.model_validate(existing.payload["summary"], strict=True)
    broker = StageDataBroker(pack, stage)
    inputs = broker.inputs(surface)
    oracles = broker.oracles(surface)
    identity, generations = adapter.generate(
        config,
        inputs,
        device=plan.device,
        maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
        seed=plan.seed,
        adapter_directory=adapter_directory,
    )
    records = evaluate_generations(
        pack=pack,
        surface=surface,
        system_role=system_role,
        checkpoint_id=checkpoint_id,
        model=identity,
        inputs=inputs,
        oracles=oracles,
        generations=generations,
    )
    summary = summarize(surface, records)
    write_stage(
        run_directory,
        stage=stage,
        sequence=sequence,
        parent_stage_sha256=parent,
        status="COMPLETED",
        payload={
            "records": [item.model_dump(mode="json") for item in records],
            "summary": summary.model_dump(mode="json"),
        },
    )
    return records, summary


def _supervision(
    *,
    run_directory: Path,
    plan: SuccessionPlan,
    pack: Any,
    source_config: Any,
    source_adapter: Any,
    profile: StrategyProfile,
    sequence: int,
    parent: str | None,
    stages: dict[str, StageManifest],
) -> SupervisionResult:
    existing = stages.get("SUPERVISION_FROZEN")
    if existing is not None:
        return SupervisionResult.model_validate(existing.payload["supervision"], strict=True)
    if plan.strategy_id == "direct-target-lora-v0.1":
        broker = StageDataBroker(pack, "SUPERVISION_PREPARING")
        if broker.direct_training() != pack.direct_train:
            raise RuntimeError("direct-label broker mismatch")
        result = prepare_direct_supervision(pack)
        write_stage(
            run_directory,
            stage="SUPERVISION_PREPARING",
            sequence=sequence,
            parent_stage_sha256=parent,
            status="COMPLETED",
            payload={"strategy": plan.strategy_id, "direct_labels": len(result.records)},
        )
        latest = latest_stage(run_directory)
        assert latest is not None
        write_stage(
            run_directory,
            stage="SUPERVISION_FROZEN",
            sequence=sequence + 1,
            parent_stage_sha256=latest.content_sha256,
            status="COMPLETED",
            payload={"supervision": result.model_dump(mode="json")},
        )
        return result
    if plan.schema_version == "inheritbench.succession-plan.v0.3":
        return _supervision_v03_anchored(
            run_directory=run_directory,
            plan=plan,
            pack=pack,
            source_config=source_config,
            source_adapter=source_adapter,
            profile=profile,
            sequence=sequence,
            parent=parent,
            stages=stages,
        )
    teacher_stage = stages.get("SUPERVISION_PREPARING")
    if teacher_stage is None:
        broker = StageDataBroker(pack, "SUPERVISION_PREPARING")
        inputs = broker.inputs("transfer_pool")
        if profile.teacher_outputs_artifact is not None:
            teacher_path = (pack.root / profile.teacher_outputs_artifact).resolve()
            if (
                profile.teacher_outputs_sha256 is None
                or sha256_file(teacher_path) != profile.teacher_outputs_sha256
            ):
                raise ValueError("frozen teacher-output artifact hash mismatch")
            outputs = _load_generation_outputs(teacher_path)
            identity_payload: dict[str, Any] | None = None
            source_mode = "frozen-output-artifact"
        else:
            identity, outputs = source_adapter.generate(
                source_config,
                inputs,
                device=plan.device,
                maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
                seed=plan.seed,
                adapter_directory=_source_adapter_directory(plan),
            )
            identity_payload = identity.model_dump(mode="json")
            source_mode = "live-source-generation"
        _, teacher_stage = write_stage(
            run_directory,
            stage="SUPERVISION_PREPARING",
            sequence=sequence,
            parent_stage_sha256=parent,
            status="COMPLETED",
            payload={
                "teacher_mode": source_mode,
                "teacher_model": identity_payload,
                "teacher_artifact": profile.teacher_outputs_artifact,
                "teacher_artifact_sha256": profile.teacher_outputs_sha256,
                "outputs": [item.model_dump(mode="json") for item in outputs],
            },
        )
        sequence += 1
        parent = teacher_stage.content_sha256
    outputs = [
        GenerationOutput.model_validate(item, strict=True)
        for item in teacher_stage.payload["outputs"]
    ]
    anchors = _run_anchors(run_directory)
    result = prepare_anchored_supervision(
        pack,
        outputs,
        minimum_examples_per_group=profile.minimum_examples_per_group,
        teacher_selection_namespace=(
            profile.teacher_selection_namespace or profile.selection_namespace
        ),
        anchor_selection_namespace=(
            profile.anchor_selection_namespace or profile.selection_namespace
        ),
        teacher_stage_sha256=teacher_stage.content_sha256,
        anchors=anchors,
    )
    if result.status == "ANCHORS_REQUIRED":
        prior = stages.get("ANCHORS_REQUIRED")
        if prior is None:
            write_stage(
                run_directory,
                stage="ANCHORS_REQUIRED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="INTERVENTION",
                payload={"supervision": result.model_dump(mode="json")},
            )
        return result
    write_stage(
        run_directory,
        stage="SUPERVISION_FROZEN",
        sequence=sequence,
        parent_stage_sha256=parent,
        status="COMPLETED",
        payload={"supervision": result.model_dump(mode="json")},
    )
    return result


def _supervision_v03_anchored(
    *,
    run_directory: Path,
    plan: SuccessionPlan,
    pack: Any,
    source_config: Any,
    source_adapter: Any,
    profile: StrategyProfile,
    sequence: int,
    parent: str | None,
    stages: dict[str, StageManifest],
) -> SupervisionResult:
    teacher_stage = stages.get("SUPERVISION_PREPARING")
    if teacher_stage is None:
        broker = StageDataBroker(pack, "SUPERVISION_PREPARING")
        inputs = broker.inputs("transfer_pool")
        if profile.teacher_outputs_artifact is not None:
            teacher_path = (pack.root / profile.teacher_outputs_artifact).resolve()
            if (
                profile.teacher_outputs_sha256 is None
                or sha256_file(teacher_path) != profile.teacher_outputs_sha256
            ):
                raise ValueError("frozen teacher-output artifact hash mismatch")
            outputs = _load_generation_outputs(teacher_path)
            identity_payload: dict[str, Any] | None = None
            source_mode = "frozen-output-artifact"
        else:
            identity, outputs = source_adapter.generate(
                source_config,
                inputs,
                device=plan.device,
                maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
                seed=plan.seed,
                adapter_directory=_source_adapter_directory(plan),
            )
            identity_payload = identity.model_dump(mode="json")
            source_mode = "live-source-generation"
        _, teacher_stage = write_stage(
            run_directory,
            stage="SUPERVISION_PREPARING",
            sequence=sequence,
            parent_stage_sha256=parent,
            status="COMPLETED",
            payload={
                "teacher_mode": source_mode,
                "teacher_model": identity_payload,
                "teacher_artifact": profile.teacher_outputs_artifact,
                "teacher_artifact_sha256": profile.teacher_outputs_sha256,
                "outputs": [item.model_dump(mode="json") for item in outputs],
            },
        )
        sequence += 1
        parent = teacher_stage.content_sha256
    evaluation_stage = stages.get("TEACHER_OUTPUTS_EVALUATED")
    if evaluation_stage is None:
        outputs = [
            GenerationOutput.model_validate(item, strict=True)
            for item in teacher_stage.payload["outputs"]
        ]
        evaluation = evaluate_teacher_outputs(
            pack,
            outputs,
            teacher_stage_sha256=teacher_stage.content_sha256,
        )
        _, evaluation_stage = write_stage(
            run_directory,
            stage="TEACHER_OUTPUTS_EVALUATED",
            sequence=sequence,
            parent_stage_sha256=parent,
            status="COMPLETED",
            payload={"evaluation": evaluation.model_dump(mode="json")},
        )
        sequence += 1
        parent = evaluation_stage.content_sha256
    else:
        evaluation = TeacherEvaluationResult.model_validate(
            evaluation_stage.payload["evaluation"], strict=True
        )
    requested = stages.get("ANCHORS_REQUIRED")
    if requested is None:
        selected_teacher = select_teacher_supervision(
            pack,
            evaluation,
            minimum_examples_per_group=profile.minimum_examples_per_group,
            teacher_selection_namespace=(
                profile.teacher_selection_namespace or profile.selection_namespace
            ),
        )
        if selected_teacher.status == "ANCHORS_REQUIRED":
            request_payload = _anchor_request_payload(plan, selected_teacher)
            write_stage(
                run_directory,
                stage="ANCHORS_REQUIRED",
                sequence=sequence,
                parent_stage_sha256=parent,
                status="INTERVENTION",
                payload={
                    "supervision": selected_teacher.model_dump(mode="json"),
                    "intervention_request": request_payload,
                },
            )
            return selected_teacher
    else:
        selected_teacher = SupervisionResult.model_validate(
            requested.payload["supervision"], strict=True
        )
    anchors_added = stages.get("ANCHORS_ADDED")
    if selected_teacher.status == "ANCHORS_REQUIRED" and anchors_added is None:
        return selected_teacher
    anchors = _run_anchors(run_directory)
    result = finalize_anchored_supervision(
        selected_teacher,
        anchors=anchors,
        anchor_selection_namespace=(
            profile.anchor_selection_namespace or profile.selection_namespace
        ),
    )
    if result.status != "FROZEN":
        raise ValueError("frozen anchor intervention did not satisfy every deficit")
    latest = latest_stage(run_directory)
    assert latest is not None
    write_stage(
        run_directory,
        stage="SUPERVISION_FROZEN",
        sequence=latest.sequence + 1,
        parent_stage_sha256=latest.content_sha256,
        status="COMPLETED",
        payload={"supervision": result.model_dump(mode="json")},
    )
    return result


def _anchor_request_payload(
    plan: SuccessionPlan,
    supervision: SupervisionResult,
) -> dict[str, Any]:
    binding = plan.authorized_anchor_pool
    if binding is None:
        raise ValueError("anchored plan lacks an authorized anchor pool")
    records = _load_labeled(Path(binding.relative_path))
    deficit_groups = {item.group: item.deficit for item in supervision.deficits}
    eligible_by_group: dict[str, list[str]] = {}
    ranks: dict[str, str] = {}
    for record in records:
        if record.input_record.group not in deficit_groups:
            continue
        rank = sha256_text(f"{binding.ranking_namespace}:{record.record_id}")
        ranks[record.record_id] = rank
        eligible_by_group.setdefault(record.input_record.group, []).append(record.record_id)
    for group, ids in eligible_by_group.items():
        ids.sort(key=lambda record_id: ranks[record_id])
        if len(ids) < deficit_groups[group]:
            raise ValueError(f"authorized anchor pool cannot satisfy deficit for {group}")
    return {
        "schema_version": "inheritbench.anchor-intervention-request.v0.1",
        "authorized_pool_byte_sha256": binding.byte_sha256,
        "authorized_pool_records_sha256": binding.records_sha256,
        "ranking_namespace": binding.ranking_namespace,
        "deficits": [item.model_dump(mode="json") for item in supervision.deficits],
        "eligible_by_group": dict(sorted(eligible_by_group.items())),
        "selection_ranks": dict(sorted(ranks.items())),
        "required_command": (
            "uv run inheritbench succession add-anchors "
            f"--run {plan.execution_id} --records {binding.relative_path}"
        ),
    }


def _load_generation_outputs(path: Path) -> list[GenerationOutput]:
    values = [
        GenerationOutput.model_validate_json(line, strict=True)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not values:
        raise ValueError("frozen teacher-output artifact is empty")
    if len({item.record_id for item in values}) != len(values):
        raise ValueError("frozen teacher-output artifact contains duplicate record IDs")
    return values


def _training(
    *,
    run_directory: Path,
    plan: SuccessionPlan,
    target_config: Any,
    target_adapter: Any,
    profile: StrategyProfile,
    supervision: SupervisionResult,
    maximum_new_tokens: int,
    sequence: int,
    parent: str | None,
    existing: StageManifest | None,
) -> TrainingResult:
    if existing is not None:
        return TrainingResult.model_validate(existing.payload["training"], strict=True)
    encoding_manifest = target_adapter.training_encoding_manifest(
        target_config, supervision.records
    )
    lengths = {str(item["record_id"]): int(item["sequence_tokens"]) for item in encoding_manifest}
    schedule = resolve_schedule(
        records=supervision.records,
        sequence_lengths=lengths,
        profile=profile,
        pack_root=Path(plan.pack_root),
        seed=plan.seed,
    )
    initialization = target_adapter.training_initialization(
        target_config,
        profile.training,
        device=plan.device,
        seed=plan.seed,
    )
    preflight_payload = {
        "schema_version": "inheritbench.parity-preflight.v0.1",
        "status": (
            "SEEDED_DIRECT_REPLICATION_PREFLIGHT_PASS"
            if plan.schema_version == "inheritbench.succession-plan.v0.3"
            and plan.strategy_id == "direct-target-lora-v0.1"
            else (
                "ANCHORED_PRODUCT_REFERENCE_PREFLIGHT_PASS"
                if plan.schema_version == "inheritbench.succession-plan.v0.3"
                else "PARITY_PREFLIGHT_PASS"
            )
        ),
        "run_id": plan.run_id,
        "canonical_plan_id": plan.canonical_plan_id,
        "canonical_plan_sha256": plan.canonical_plan_sha256,
        "execution_id": plan.execution_id,
        "replication_group_id": plan.replication_group_id,
        "replication_index": plan.replication_index,
        "protocol_amendment_sha256": (
            plan.protocol_amendment.amendment_sha256
            if plan.protocol_amendment is not None
            else None
        ),
        "plan_sha256": plan.plan_sha256,
        "pack_validation_sha256": plan.pack_validation_sha256,
        "supervision_sha256": content_sha256(
            [item.model_dump(mode="json") for item in supervision.records]
        ),
        "schedule_sha256": schedule.content_sha256,
        "sequence_lengths_sha256": content_sha256(dict(sorted(lengths.items()))),
        "training_encodings": encoding_manifest,
        "training_encodings_sha256": content_sha256(encoding_manifest),
        "training_profile_sha256": content_sha256(profile.training.model_dump(mode="json")),
        "strategy_profile_sha256": content_sha256(profile.model_dump(mode="json")),
        "optimizer": {
            "name": "AdamW",
            "learning_rate": profile.training.learning_rate,
            "betas": profile.training.betas,
            "epsilon": profile.training.epsilon,
            "weight_decay": profile.training.weight_decay,
            "gradient_accumulation_steps": profile.training.gradient_accumulation_steps,
            "gradient_clip_norm": profile.training.gradient_clip_norm,
            "warmup_steps": schedule.warmup_steps,
            "optimizer_steps": schedule.optimizer_steps,
            "checkpoint_steps": schedule.checkpoint_steps,
        },
        "inference": {
            "maximum_new_tokens": maximum_new_tokens,
            "do_sample": False,
            "num_beams": 1,
            "batch_size": 1,
            "seed": plan.seed,
        },
        "initialization": initialization.model_dump(mode="json"),
    }
    preflight_payload["content_sha256"] = content_sha256(preflight_payload)
    preflight_bytes = canonical_json_bytes(preflight_payload) + b"\n"
    preflight_path = run_directory / "parity_preflight.json"
    if preflight_path.exists():
        if preflight_path.read_bytes() != preflight_bytes:
            raise ValueError(
                "persisted parity preflight differs from the current training contract"
            )
    else:
        write_atomic_file(preflight_path, preflight_bytes)
    _write_or_verify_json(
        run_directory / "initialization_manifest.json",
        {
            "schema_version": "inheritbench.initialization-manifest.v0.1",
            "canonical_plan_sha256": plan.canonical_plan_sha256,
            "execution_id": plan.execution_id or plan.run_id,
            "initialization": initialization.model_dump(mode="json"),
        },
    )
    _write_or_verify_json(
        run_directory / "rng_manifest.json",
        {
            "schema_version": "inheritbench.rng-manifest.v0.1",
            "seed": plan.seed,
            "before_model_load_sha256": initialization.rng_before_model_load_sha256,
            "before_lora_sha256": initialization.rng_before_lora_sha256,
            "after_lora_sha256": initialization.rng_after_lora_sha256,
        },
    )
    _write_or_verify_json(
        run_directory / "schedule_manifest.json",
        schedule.model_dump(mode="json"),
    )
    _write_or_verify_json(
        run_directory / "encoding_manifest.json",
        {
            "schema_version": "inheritbench.encoding-manifest.v0.1",
            "records": encoding_manifest,
            "content_sha256": content_sha256(encoding_manifest),
        },
    )
    training = TrainingResult.model_validate(
        target_adapter.train(
            target_config,
            supervision.records,
            schedule,
            profile.training,
            device=plan.device,
            run_id=plan.run_id,
            output_root=run_directory / "checkpoints",
            seed=plan.seed,
            resume_checkpoint=_latest_training_checkpoint(run_directory),
        ),
        strict=True,
    )
    if not _training_initialization_matches(initialization, training):
        raise RuntimeError("training initialization differs from parity preflight")
    _write_or_verify_json(
        run_directory / "training_trajectory.json",
        {
            "schema_version": "inheritbench.training-trajectory.v0.1",
            "execution_id": plan.execution_id or plan.run_id,
            "initial_adapter_sha256": training.initial_adapter_sha256,
            "optimizer_step_one_sha256": training.optimizer_step_one_sha256,
            "losses": training.losses,
            "telemetry": [item.model_dump(mode="json") for item in training.telemetry],
        },
    )
    _write_or_verify_json(
        run_directory / "checkpoint_manifest.json",
        {
            "schema_version": "inheritbench.checkpoint-manifest.v0.1",
            "execution_id": plan.execution_id or plan.run_id,
            "checkpoints": [item.model_dump(mode="json") for item in training.checkpoints],
        },
    )
    write_stage(
        run_directory,
        stage="TRAINING",
        sequence=sequence,
        parent_stage_sha256=parent,
        status="COMPLETED" if training.status == "COMPLETED" else "FAILED",
        payload={
            "schedule": schedule.model_dump(mode="json"),
            "training": training.model_dump(mode="json"),
        },
        errors=[] if training.error is None else [training.error],
    )
    return training


def _training_initialization_matches(
    initialization: TrainingInitialization,
    training: TrainingResult,
) -> bool:
    return (
        training.initial_adapter_sha256 == initialization.initial_adapter_sha256
        and training.trainable_parameter_names == initialization.trainable_parameter_names
        and training.trainable_parameter_shapes == initialization.trainable_parameter_shapes
        and training.trainable_parameters == initialization.trainable_parameters
        and training.seed == initialization.seed
    )


def _select_checkpoint(
    *,
    run_directory: Path,
    plan: SuccessionPlan,
    pack: Any,
    target_config: Any,
    target_adapter: Any,
    training: TrainingResult,
    profile: StrategyProfile,
    sequence: int,
    parent: str | None,
    existing: StageManifest | None,
) -> CheckpointDecision:
    if existing is not None:
        return CheckpointDecision.model_validate(existing.payload["decision"], strict=True)
    broker = StageDataBroker(pack, "CHECKPOINT_SELECTED")
    surface = profile.checkpoint_validation_surface
    inputs = broker.inputs(surface)
    oracles = broker.oracles(surface)
    decision, evaluations = checkpoint_decision(
        pack=pack,
        adapter=target_adapter,
        model_config=target_config,
        checkpoints=training.checkpoints,
        validation_inputs=inputs,
        validation_oracles=oracles,
        device=plan.device,
        maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
        seed=plan.seed,
        policy=profile.checkpoint_policy,
    )
    write_stage(
        run_directory,
        stage="CHECKPOINT_SELECTED",
        sequence=sequence,
        parent_stage_sha256=parent,
        status="COMPLETED" if decision.status == "SELECTED" else "FAILED",
        payload={
            "decision": decision.model_dump(mode="json"),
            "evaluations": {
                key: [item.model_dump(mode="json") for item in value]
                for key, value in evaluations.items()
            },
        },
    )
    return decision


def _export_adapter(
    run_directory: Path,
    plan: SuccessionPlan,
    adapter: Any,
    config: Any,
    decision: CheckpointDecision,
) -> dict[str, Any]:
    assert decision.selected_adapter_directory is not None
    assert decision.selected_adapter_sha256 is not None
    destination = run_directory / "successor"
    if not destination.exists():
        source = Path(decision.selected_adapter_directory)

        def build(staging: Path) -> None:
            for name in (
                "adapter_config.json",
                "adapter_model.safetensors",
                "adapter_model.fake",
            ):
                candidate = source / name
                if candidate.is_file():
                    shutil.copy2(candidate, staging / name)
            (staging / "lineage.json").write_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": "inheritbench.successor-lineage.v0.2",
                        "run_id": plan.run_id,
                        "plan_sha256": plan.plan_sha256,
                        "checkpoint_id": decision.selected_checkpoint_id,
                        "adapter_sha256": decision.selected_adapter_sha256,
                    }
                )
                + b"\n"
            )

        from inheritbench.artifacts.store import write_atomic_directory

        write_atomic_directory(destination, build)
    identity = adapter.verify_adapter(config, destination, device=plan.device)
    return {
        "adapter_directory": str(destination),
        "adapter_sha256": identity.adapter_sha256,
        "checkpoint_id": decision.selected_checkpoint_id,
        "model": identity.model_dump(mode="json"),
    }


def _write_final_outputs(
    *,
    run_directory: Path,
    plan: SuccessionPlan,
    source_records: list[EvaluationRecord],
    target_base_records: list[EvaluationRecord],
    confirmatory_records: list[EvaluationRecord],
    adversarial_records: list[EvaluationRecord],
    source_summary: SurfaceSummary,
    target_base_summary: SurfaceSummary,
    confirmatory_summary: SurfaceSummary,
    adversarial_summary: SurfaceSummary,
    supervision: SupervisionResult,
    training: TrainingResult,
    decision: CheckpointDecision,
    readiness: Any,
    successor: dict[str, Any],
    include_derived_bundle: bool,
) -> None:
    evaluation_summary = {
        "source_gate": source_summary,
        "target_baseline": target_base_summary,
        "confirmatory": confirmatory_summary,
        "adversarial": adversarial_summary,
    }
    residuals = [
        item.model_dump(mode="json")
        for item in confirmatory_records + adversarial_records
        if not bool(item.evaluation["semantic_match"])
        or item.evaluation["safety_findings"]
        or item.generation.status != "COMPLETED"
    ]
    compute = {
        "training_processed_tokens": training.processed_tokens,
        "optimizer_steps": training.optimizer_steps_completed,
        "duration_seconds": training.duration_seconds,
        "trainable_parameters": training.trainable_parameters,
        "total_parameters": training.total_parameters,
    }
    values = {
        "run.json": {
            "schema_version": "inheritbench.succession-run.v0.2",
            "run_id": plan.run_id,
            "status": "COMPLETED",
            "plan_sha256": plan.plan_sha256,
            "readiness_sha256": readiness.content_sha256,
        },
        "evaluation_summary.json": evaluation_summary,
        "readiness_report.json": readiness,
        "residual_failures.json": {"records": residuals},
        "label_accounting.json": supervision.accounting,
        "compute_accounting.json": compute,
        "adapter_reference.json": successor,
    }
    if include_derived_bundle:
        values["execution_log.jsonl"] = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((run_directory / "stages").glob("*/stage.json"))
        ]
    for name, value in values.items():
        path = run_directory / name
        if path.exists():
            continue
        if name.endswith(".jsonl"):
            payload = b"".join(canonical_json_bytes(item) + b"\n" for item in value)
            write_atomic_file(path, payload)
        else:
            write_final_file(run_directory, name, value)
    if not include_derived_bundle:
        return
    evidence = {
        name: {
            "bytes": (run_directory / name).stat().st_size,
            "sha256": sha256_file(run_directory / name),
        }
        for name in sorted(values)
    }
    evidence["plan.json"] = {
        "bytes": (run_directory / "plan.json").stat().st_size,
        "sha256": sha256_file(run_directory / "plan.json"),
    }
    if not (run_directory / "evidence_manifest.json").exists():
        write_final_file(
            run_directory,
            "evidence_manifest.json",
            {"run_id": plan.run_id, "files": evidence},
        )
    web_bundle = {
        "schema_version": "inheritbench.web-bundle.v0.2",
        "run_id": plan.run_id,
        "capability": {
            "id": plan.capability_id,
            "version": plan.capability_version,
        },
        "strategy": plan.strategy_id,
        "readiness": readiness,
        "summaries": evaluation_summary,
        "residuals": residuals,
        "label_accounting": supervision.accounting,
        "compute_accounting": compute,
        "adapter": successor,
        "stages": [
            json.loads(path.read_text(encoding="utf-8"))["stage"]
            for path in sorted((run_directory / "stages").glob("*/stage.json"))
        ],
    }
    web_bundle["content_sha256"] = content_sha256(web_bundle)
    if not (run_directory / "web_bundle.json").exists():
        write_final_file(
            run_directory,
            "web_bundle.json",
            FinalizedWebBundle.model_validate(web_bundle, strict=True),
        )


def _ensure_replay(run_directory: Path) -> Path:
    existing = sorted(
        path
        for path in (run_directory / "replays").glob("replay-*")
        if (path / "replay_receipt.json").is_file()
    )
    if len(existing) > 1:
        raise ValueError("more than one replay exists for the execution")
    if existing:
        return existing[0]
    return replay_run(run_directory, output_root=run_directory / "replays")


def _write_v03_execution_evidence(run_directory: Path, plan: SuccessionPlan) -> None:
    stages = [_json_file(path) for path in sorted((run_directory / "stages").glob("*/stage.json"))]
    _write_or_verify_jsonl(run_directory / "execution_log.jsonl", stages)
    names = sorted(
        path.name
        for path in run_directory.iterdir()
        if path.is_file() and path.name not in {"evidence_manifest.json", "web_bundle.json"}
    )
    evidence = {
        name: {
            "bytes": (run_directory / name).stat().st_size,
            "sha256": sha256_file(run_directory / name),
        }
        for name in names
    }
    _write_or_verify_json(
        run_directory / "evidence_manifest.json",
        {
            "schema_version": "inheritbench.evidence-manifest.v0.3",
            "run_id": plan.run_id,
            "canonical_plan_id": plan.canonical_plan_id,
            "execution_id": plan.execution_id,
            "files": evidence,
        },
    )


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_or_verify_jsonl(path: Path, values: list[Any]) -> None:
    payload = b"".join(canonical_json_bytes(value) + b"\n" for value in values)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"persisted deterministic artifact differs: {path}")
        return
    write_atomic_file(path, payload)


def _stage_map(run_directory: Path) -> dict[str, StageManifest]:
    stages: dict[str, StageManifest] = {}
    for path in sorted((run_directory / "stages").glob("*/stage.json")):
        stage = StageManifest.model_validate_json(path.read_text(encoding="utf-8"), strict=True)
        stages[stage.stage] = stage
    return stages


def _surface_passes(summary: SurfaceSummary, rules: dict[str, object]) -> bool:
    if summary.expected == 0 or summary.terminal != summary.expected:
        return False
    return (
        summary.semantic_correct / summary.expected >= _float_rule(rules, "minimum_semantic_rate")
        and summary.strict_valid / summary.expected >= _float_rule(rules, "minimum_strict_rate")
        and summary.minimum_group_semantic_rate >= _float_rule(rules, "minimum_group_semantic_rate")
        and summary.blocker_safety_findings <= _int_rule(rules, "maximum_blocker_safety_findings")
        and summary.unknown_safety == 0
    )


def _rules(
    document: dict[str, Any],
    key: str,
    *,
    fallback: str | None = None,
) -> dict[str, object]:
    value = document.get(key)
    if value is None and fallback is not None:
        value = document.get(fallback)
    if not isinstance(value, dict):
        raise ValueError(f"readiness rules lack {key}")
    return value


def _float_rule(rules: dict[str, object], key: str) -> float:
    value = rules.get(key, 0.0)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"readiness rule {key} must be numeric")
    return float(value)


def _int_rule(rules: dict[str, object], key: str) -> int:
    value = rules.get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"readiness rule {key} must be an integer")
    return value


def _source_adapter_directory(plan: SuccessionPlan) -> Path | None:
    return Path(plan.source_adapter.relative_path) if plan.source_adapter is not None else None


def _latest_training_checkpoint(run_directory: Path) -> Path | None:
    checkpoints = sorted(
        path
        for path in (run_directory / "checkpoints").glob("*")
        if path.is_dir() and (path / "trainer_state.pt").is_file()
    )
    return checkpoints[-1] if checkpoints else None


def _run_anchors(run_directory: Path) -> list[CapabilityLabeledRecord]:
    manifests = sorted((run_directory / "interventions").glob("*/anchors.jsonl"))
    if not manifests:
        return []
    if len(manifests) > 1:
        raise ValueError("more than one anchor intervention exists")
    return _load_labeled(manifests[0])


def _load_labeled(path: Path) -> list[CapabilityLabeledRecord]:
    return [
        CapabilityLabeledRecord.model_validate_json(line, strict=True)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_or_verify_json(path: Path, value: Any) -> None:
    payload = canonical_json_bytes(value) + b"\n"
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"persisted deterministic artifact differs: {path}")
        return
    write_atomic_file(path, payload)


def _terminal(
    run_directory: Path,
    state: str,
    sequence: int,
    parent: str | None,
    payload: dict[str, Any],
) -> Path:
    write_stage(
        run_directory,
        stage=state,
        sequence=sequence,
        parent_stage_sha256=parent,
        status="FAILED",
        payload=payload,
        errors=[state],
    )
    finalize_active(run_directory)
    return run_directory


def _failure_state(exc: BaseException) -> str:
    message = str(exc)
    if "UNSUPPORTED_MODEL_ARCHITECTURE" in message:
        return "UNSUPPORTED_MODEL_ARCHITECTURE"
    if isinstance(exc, (ValueError, FileNotFoundError, PermissionError)):
        return "INTEGRITY_FAILURE"
    return "EXECUTION_FAILED"
