from __future__ import annotations

import json
from pathlib import Path

import pytest

from inheritbench.orchestration.inspection import inspect_run
from inheritbench.orchestration.replay import replay_run
from inheritbench.orchestration.schemas import FinalizedWebBundle

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.product_smoke
def test_real_generic_product_integration_run_replays(tmp_path: Path) -> None:
    candidates = []
    for run in (REPOSITORY_ROOT / "runs/parity").glob("succession-opsroute-*"):
        plan_path = run / "plan.json"
        if not plan_path.is_file():
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if (
            plan.get("execution_engine_version") == "inheritbench-generic-succession-v0.2.2"
            and plan.get("product_run_kind") == "PRODUCT_PARITY_RUN"
            and (run / "direct_parity_report.json").is_file()
        ):
            candidates.append(run)
    if not candidates:
        pytest.fail("repaired real generic direct parity run is missing")
    run = max(candidates, key=lambda path: path.stat().st_mtime_ns)
    inspection = inspect_run(run)
    assert inspection.current_state in {"COMPLETED", "MIGRATION_BLOCKED"}
    replay = replay_run(run, output_root=tmp_path / "replays")
    assert (replay / "replay_receipt.json").is_file()
    parity = json.loads((run / "direct_parity_report.json").read_text(encoding="utf-8"))
    assert parity["training_inference_gate_passed"] is False
    assert parity["anchored_execution_status"] == "BLOCKED_BEFORE_ANCHORED_RUN"
    diagnosis = json.loads((run / "direct_parity_diagnosis.json").read_text(encoding="utf-8"))
    assert diagnosis["status"] == "CONFIRMED"
    assert diagnosis["verdict"] == "HISTORICAL_UNSEEDED_ADAPTER_INITIALIZATION_NOT_RECONSTRUCTIBLE"
    bundle = FinalizedWebBundle.model_validate_json(
        (run / "web_bundle.json").read_text(encoding="utf-8"),
        strict=True,
    )
    assert bundle.readiness.status == "MIGRATION_BLOCKED"


@pytest.mark.product_smoke
def test_seeded_direct_and_anchored_reference_runs_are_complete() -> None:
    seeded = _latest_report(
        REPOSITORY_ROOT / "runs/reproducibility",
        "seeded_reproducibility_report.json",
    )
    seeded_report = json.loads(
        (seeded / "seeded_reproducibility_report.json").read_text(encoding="utf-8")
    )
    assert seeded_report["classification"] == "SEEDED_PROTOCOL_REPRODUCIBILITY_CONFIRMED"
    assert seeded_report["behavioral_classification"] == ("BEHAVIORAL_REPRODUCIBILITY_CONFIRMED")
    anchored = _latest_report(
        REPOSITORY_ROOT / "runs/reference",
        "anchored_recovery_report.json",
    )
    recovery = json.loads((anchored / "anchored_recovery_report.json").read_text(encoding="utf-8"))
    assert recovery["classification"] == "GENERIC_ANCHORED_RECOVERY_FAILED"
    assert recovery["teacher_candidates"] == 768
    assert recovery["accepted_teacher_outputs"] == 719
    assert recovery["selected_teacher_outputs"] == 214
    assert recovery["anchors_added"] == 10
    assert recovery["selected_training_records"] == 224
    assert recovery["readiness"] == "MIGRATION_BLOCKED"
    assert recovery["confirmatory"]["semantic_correct"] == 53
    assert recovery["confirmatory"]["strict_valid"] == 64
    assert recovery["adversarial"]["semantic_correct"] == 19
    assert recovery["replay_verified"] is True
    bundle = FinalizedWebBundle.model_validate_json(
        (anchored / "web_bundle.json").read_text(encoding="utf-8"),
        strict=True,
    )
    assert bundle.schema_version == "inheritbench.web-bundle.v0.3"
    assert bundle.reload_verification is not None
    assert bundle.replay_verification is not None


def _latest_report(root: Path, report_name: str) -> Path:
    candidates = [path.parent for path in root.glob(f"*/{report_name}")]
    if not candidates:
        pytest.fail(f"required local product evidence is missing: {report_name}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)
