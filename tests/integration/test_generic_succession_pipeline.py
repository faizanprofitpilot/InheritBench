from __future__ import annotations

import json
from pathlib import Path

import pytest

from inheritbench.capability.loader import load_capability_pack
from inheritbench.model_adapters.schemas import GenerationOutput
from inheritbench.orchestration.executor import add_anchors, execute_run, resume_run
from inheritbench.orchestration.inspection import build_intervention_web_bundle, inspect_run
from inheritbench.orchestration.planner import create_plan
from inheritbench.orchestration.replay import replay_run
from inheritbench.reference_packs.purchase_approval import build_purchase_approval_pack
from inheritbench.strategies.anchored import prepare_anchored_supervision

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_direct_fake_run_completes_and_replays(tmp_path: Path) -> None:
    pack_root = build_purchase_approval_pack(tmp_path / "pack")
    run = create_plan(
        pack_root=pack_root,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="direct-target-lora-v0.1",
        output_root=tmp_path / "runs",
        device="cpu",
        allow_fixture=True,
    )
    with pytest.raises(FileExistsError):
        create_plan(
            pack_root=pack_root,
            source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
            target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
            strategy_id="direct-target-lora-v0.1",
            output_root=tmp_path / "runs",
            device="cpu",
            allow_fixture=True,
        )
    frozen_plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    assert frozen_plan["seed"] == 20260714
    assert frozen_plan["execution_engine_version"] == "inheritbench-generic-succession-v0.2.2"
    execute_run(run)
    inspection = inspect_run(run)
    assert inspection.current_state == "COMPLETED"
    assert inspection.readiness is not None
    assert inspection.readiness["status"] == "PASS"
    replay = replay_run(run, output_root=tmp_path / "replays")
    assert json.loads((replay / "replay_receipt.json").read_text())["status"] == "PASSED"


def test_anchored_run_persists_deficit_adds_anchors_and_resumes(tmp_path: Path) -> None:
    pack_root = build_purchase_approval_pack(tmp_path / "pack")
    run = create_plan(
        pack_root=pack_root,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="anchored-behavioral-transfer-v0.1",
        output_root=tmp_path / "runs",
        device="cpu",
        allow_fixture=True,
    )
    execute_run(run)
    waiting = inspect_run(run)
    assert waiting.current_state == "ANCHORS_REQUIRED"
    assert waiting.intervention is not None
    assert waiting.intervention["deficits"] == [
        {
            "group": "manager_approval",
            "required": 2,
            "accepted_teacher": 0,
            "accepted_anchors": 0,
            "deficit": 2,
        }
    ]
    intervention_bundle = build_intervention_web_bundle(run)
    assert intervention_bundle.state == "ANCHORS_REQUIRED"
    assert intervention_bundle.content_sha256
    available = (pack_root / "anchors/available.jsonl").read_text().splitlines()
    selected = tmp_path / "anchors.jsonl"
    selected.write_text("\n".join(available[:2]) + "\n", encoding="utf-8")
    add_anchors(run, selected)
    resume_run(run)
    completed = inspect_run(run)
    assert completed.current_state == "COMPLETED"
    assert completed.readiness is not None
    assert completed.readiness["status"] == "PASS"
    teacher_stages = list((run / "stages").glob("*-supervision_preparing/stage.json"))
    assert len(teacher_stages) == 1
    execute_run(run)
    assert len(list((run / "stages").glob("*-confirmatory_completed/stage.json"))) == 1


def test_historical_matched_teacher_evidence_reproduces_exact_deficit() -> None:
    pack = load_capability_pack(
        REPOSITORY_ROOT / "capabilities/opsroute/v0.2.0",
        require_executable=True,
    )
    outputs: list[GenerationOutput] = []
    for path in sorted(
        (REPOSITORY_ROOT / "artifacts/day3-matched/teacher-runs").glob("*/predictions.jsonl")
    ):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            outputs.append(
                GenerationOutput(
                    record_id=record["candidate_id"],
                    status=record["status"],
                    raw_output=record["raw_output"],
                    prompt_sha256=record["prompt_sha256"],
                    input_ids_sha256=record["input_ids_sha256"],
                    prompt_tokens=record["prompt_token_count"],
                    completion_tokens=record["generated_token_count"],
                    error=None,
                    latency_ms=record["latency_ms"],
                )
            )
    result = prepare_anchored_supervision(
        pack,
        outputs,
        minimum_examples_per_group=14,
        teacher_selection_namespace="phase3b-synthetic-selection-v0.1",
        anchor_selection_namespace="phase3b-anchor-selection-v0.1",
        teacher_stage_sha256="0" * 64,
        anchors=[],
    )
    assert len(outputs) == 768
    assert result.accounting.accepted_teacher_outputs == 719
    assert result.accounting.selected_training_records == 214
    assert result.deficits[0].group == "refund_policy_routing:duplicate_auto_refund"
    assert result.deficits[0].accepted_teacher == 4
    assert result.deficits[0].deficit == 10


def test_planned_input_mutation_finalizes_integrity_failure(tmp_path: Path) -> None:
    pack_root = build_purchase_approval_pack(tmp_path / "pack")
    run = create_plan(
        pack_root=pack_root,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="direct-target-lora-v0.1",
        output_root=tmp_path / "runs",
        device="cpu",
        allow_fixture=True,
    )
    source_gate = pack_root / "data/source_gate.inputs.jsonl"
    source_gate.write_bytes(source_gate.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="planned input changed"):
        execute_run(run)
    assert inspect_run(run).current_state == "INTEGRITY_FAILURE"
