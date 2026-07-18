from __future__ import annotations

import json
from pathlib import Path

import pytest

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.orchestration.executor import add_anchors, execute_run, resume_run
from inheritbench.orchestration.planner import create_plan
from inheritbench.orchestration.storage import load_plan
from inheritbench.reference_packs.purchase_approval import build_purchase_approval_pack

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_v03_plan_separates_canonical_and_execution_identity(tmp_path: Path) -> None:
    pack = build_purchase_approval_pack(tmp_path / "pack")
    amendment = _amendment(tmp_path / "amendment.json")
    first = create_plan(
        pack_root=pack,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="direct-target-lora-v0.1",
        output_root=tmp_path / "first",
        device="cpu",
        allow_fixture=True,
        protocol_amendment_path=amendment,
        replication_group_id="seeded-test",
        replication_index=1,
    )
    second = create_plan(
        pack_root=pack,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="direct-target-lora-v0.1",
        output_root=tmp_path / "second",
        device="cpu",
        allow_fixture=True,
        protocol_amendment_path=amendment,
        replication_group_id="seeded-test",
        replication_index=2,
    )
    first_plan = load_plan(first)
    second_plan = load_plan(second)
    assert first_plan.schema_version == "inheritbench.succession-plan.v0.3"
    assert first_plan.canonical_plan_sha256 == second_plan.canonical_plan_sha256
    assert first_plan.canonical_plan_id == second_plan.canonical_plan_id
    assert first_plan.execution_id != second_plan.execution_id
    assert first_plan.run_id == first_plan.execution_id


def test_protocol_governance_does_not_change_canonical_training_identity(
    tmp_path: Path,
) -> None:
    pack = build_purchase_approval_pack(tmp_path / "pack")
    first_amendment = _amendment(tmp_path / "first-amendment.json")
    second_amendment = _amendment(
        tmp_path / "second-amendment.json",
        note="independent governance note",
    )
    first = create_plan(
        pack_root=pack,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="direct-target-lora-v0.1",
        output_root=tmp_path / "first",
        device="cpu",
        allow_fixture=True,
        protocol_amendment_path=first_amendment,
        replication_group_id="seeded-test",
        replication_index=1,
    )
    second = create_plan(
        pack_root=pack,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="direct-target-lora-v0.1",
        output_root=tmp_path / "second",
        device="cpu",
        allow_fixture=True,
        protocol_amendment_path=second_amendment,
        replication_group_id="seeded-test",
        replication_index=1,
    )
    first_plan = load_plan(first)
    second_plan = load_plan(second)
    assert first_plan.canonical_plan_sha256 == second_plan.canonical_plan_sha256
    assert first_plan.execution_id != second_plan.execution_id


def test_v03_anchor_pool_is_selected_only_after_deficit(tmp_path: Path) -> None:
    pack = build_purchase_approval_pack(tmp_path / "pack")
    amendment = _amendment(tmp_path / "amendment.json")
    anchor_pool = pack / "anchors/available.jsonl"
    run = create_plan(
        pack_root=pack,
        source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
        target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
        strategy_id="anchored-behavioral-transfer-v0.1",
        output_root=tmp_path / "runs",
        device="cpu",
        allow_fixture=True,
        product_run_kind="PRODUCT_REFERENCE_SUCCESSION",
        protocol_amendment_path=amendment,
        authorized_anchor_pool_path=anchor_pool,
        replication_group_id="anchored-test",
        replication_index=0,
    )
    execute_run(run)
    requested = _stage(run, "ANCHORS_REQUIRED")
    assert requested["payload"]["supervision"]["accounting"]["anchor_labels"] == 0
    assert not (run / "interventions").exists()
    with pytest.raises(ValueError, match="differs from the immutable plan"):
        tampered = tmp_path / "tampered.jsonl"
        tampered.write_text(anchor_pool.read_text() + "\n", encoding="utf-8")
        add_anchors(run, tampered)
    intervention = add_anchors(run, anchor_pool)
    manifest = json.loads((intervention / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"] == 2
    assert len(manifest["selected_ids"]) == 2
    assert (
        manifest["authorized_pool_byte_sha256"] == load_plan(run).authorized_anchor_pool.byte_sha256
    )
    resume_run(run)
    assert _stage(run, "COMPLETED")["status"] == "COMPLETED"
    assert len(list((run / "stages").glob("*-teacher_outputs_evaluated/stage.json"))) == 1
    assert (
        _stage(run, "SUPERVISION_FROZEN")["payload"]["supervision"]["accounting"]["anchor_labels"]
        == 2
    )
    assert (run / "replay_receipt.json").is_file()
    execution_log = [
        json.loads(line)
        for line in (run / "execution_log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert execution_log[-1]["stage"] == "COMPLETED"


def test_v03_anchored_plan_requires_full_pool_binding(tmp_path: Path) -> None:
    pack = build_purchase_approval_pack(tmp_path / "pack")
    amendment = _amendment(tmp_path / "amendment.json")
    with pytest.raises(ValueError, match="require an anchor pool"):
        create_plan(
            pack_root=pack,
            source_config_path=REPOSITORY_ROOT / "configs/models/fake_source.yaml",
            target_config_path=REPOSITORY_ROOT / "configs/models/fake_target.yaml",
            strategy_id="anchored-behavioral-transfer-v0.1",
            output_root=tmp_path / "runs",
            device="cpu",
            allow_fixture=True,
            protocol_amendment_path=amendment,
        )


def _amendment(path: Path, *, note: str | None = None) -> Path:
    payload = {
        "schema_version": "inheritbench.seeded-reference-amendment.v0.1",
        "amendment_id": "seeded-reference-succession-v0.1",
        "status": "PROSPECTIVE_FROZEN",
        "telemetry_tolerance": {
            "loss_absolute": 1e-6,
            "loss_relative": 1e-5,
            "gradient_norm_absolute": 1e-6,
            "gradient_norm_relative": 1e-5,
            "learning_rate": "EXACT",
        },
        "git_preregistered": False,
    }
    if note is not None:
        payload["note"] = note
    payload["amendment_sha256"] = content_sha256(payload)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")
    return path


def _stage(run: Path, name: str) -> dict[str, object]:
    paths = list((run / "stages").glob(f"*-{name.lower()}/stage.json"))
    assert len(paths) == 1
    value = json.loads(paths[0].read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
