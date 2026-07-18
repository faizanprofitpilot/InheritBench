"""Model-free exact succession replay."""

from __future__ import annotations

import json
from pathlib import Path

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_file
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.capability.loader import load_capability_pack
from inheritbench.orchestration.evaluation import summarize
from inheritbench.orchestration.planner import verify_plan_inputs
from inheritbench.orchestration.readiness import derive_readiness
from inheritbench.orchestration.schemas import (
    EvaluationRecord,
    ReadinessReport,
    ReplayReceipt,
    StageManifest,
)
from inheritbench.orchestration.storage import load_plan
from inheritbench.strategies.schemas import SupervisionAccounting


def replay_run(run_directory: Path, *, output_root: Path) -> Path:
    run_directory = run_directory.resolve()
    plan = load_plan(run_directory)
    verify_plan_inputs(plan)
    pack = load_capability_pack(
        Path(plan.pack_root),
        allow_fixture=True,
        require_executable=True,
    )
    stages = _stages(
        run_directory,
        require_completed=(plan.schema_version == "inheritbench.succession-plan.v0.2"),
    )
    source_records = _records(stages["SOURCE_GATE_COMPLETED"])
    target_base_records = _records(stages["TARGET_BASELINE_COMPLETED"])
    confirmatory_records = _records(stages["CONFIRMATORY_COMPLETED"])
    adversarial_records = _records(stages["ADVERSARIAL_COMPLETED"])
    source = summarize("source_gate", source_records)
    target_base = summarize("source_gate", target_base_records)
    confirmatory = summarize("confirmatory", confirmatory_records)
    adversarial = summarize("adversarial", adversarial_records)
    supervision = SupervisionAccounting.model_validate(
        stages["SUPERVISION_FROZEN"].payload["supervision"]["accounting"],
        strict=True,
    )
    decision = stages["CHECKPOINT_SELECTED"].payload["decision"]
    adapter_reference = json.loads(
        (run_directory / "adapter_reference.json").read_text(encoding="utf-8")
    )
    adapter_path = Path(adapter_reference["adapter_directory"])
    adapter_file = _adapter_file(adapter_path)
    if sha256_file(adapter_file) != adapter_reference["adapter_sha256"]:
        raise ValueError("exported adapter hash mismatch")
    readiness = derive_readiness(
        run_id=plan.run_id,
        rules=pack.readiness_rules,
        source_gate=source,
        target_baseline=target_base,
        confirmatory=confirmatory,
        adversarial=adversarial,
        supervision=supervision,
        selected_checkpoint_id=str(decision["selected_checkpoint_id"]),
        adapter_sha256=str(adapter_reference["adapter_sha256"]),
    )
    stored_payload = json.loads(
        (run_directory / "readiness_report.json").read_text(encoding="utf-8")
    )
    stored = ReadinessReport.model_validate(stored_payload, strict=True)
    legacy = "vocabulary_conformant" not in stored_payload["confirmatory"]
    if legacy:
        replayed_payload = readiness.model_dump(mode="json")
        for key in ("source_gate", "target_baseline", "confirmatory", "adversarial"):
            replayed_payload[key].pop("vocabulary_conformant")
            replayed_payload[key].pop("cross_field_conformant")
        replayed_payload.pop("content_sha256")
        replayed_payload["content_sha256"] = content_sha256(replayed_payload)
        if replayed_payload != stored_payload:
            raise ValueError("legacy replayed readiness differs from stored readiness")
        readiness_sha256 = str(stored_payload["content_sha256"])
    else:
        if readiness != stored:
            raise ValueError("replayed readiness differs from stored readiness")
        readiness_sha256 = readiness.content_sha256
    verified_names = [
        "plan.json",
        "evaluation_summary.json",
        "readiness_report.json",
        "residual_failures.json",
        "label_accounting.json",
        "compute_accounting.json",
        "adapter_reference.json",
        "evidence_manifest.json",
        "web_bundle.json",
    ]
    verified = {
        name: sha256_file(run_directory / name)
        for name in verified_names
        if (run_directory / name).is_file()
    }
    payload = {
        "schema_version": "inheritbench.succession-replay.v0.2",
        "run_id": plan.run_id,
        "status": "PASSED",
        "verified_files": verified,
        "readiness_sha256": readiness_sha256,
        "adapter_sha256": str(adapter_reference["adapter_sha256"]),
    }
    payload["content_sha256"] = content_sha256(payload)
    receipt = ReplayReceipt.model_validate(payload, strict=True)
    replay_id = f"replay-{plan.run_id}-{receipt.content_sha256[:12]}"
    return write_atomic_bundle(
        output_root,
        replay_id,
        {
            "replay_manifest.json": canonical_json_bytes(
                {
                    "schema_version": "inheritbench.replay-manifest.v0.2",
                    "run_id": plan.run_id,
                    "source_run": str(run_directory),
                    "operation": "model-free exact aggregate and readiness replay",
                }
            )
            + b"\n",
            "replay_receipt.json": canonical_json_bytes(receipt) + b"\n",
        },
    )


def _stages(
    run_directory: Path,
    *,
    require_completed: bool,
) -> dict[str, StageManifest]:
    result: dict[str, StageManifest] = {}
    for path in sorted((run_directory / "stages").glob("*/stage.json")):
        stage = StageManifest.model_validate_json(path.read_text(encoding="utf-8"), strict=True)
        result[stage.stage] = stage
    required = {
        "SOURCE_GATE_COMPLETED",
        "TARGET_BASELINE_COMPLETED",
        "SUPERVISION_FROZEN",
        "CHECKPOINT_SELECTED",
        "CONFIRMATORY_COMPLETED",
        "ADVERSARIAL_COMPLETED",
        "READINESS_FINALIZED",
        "ADAPTER_EXPORTED",
    }
    if require_completed:
        required.add("COMPLETED")
    if not required.issubset(result):
        raise ValueError(f"run is not replayable; missing {sorted(required - set(result))}")
    return result


def _records(stage: StageManifest) -> list[EvaluationRecord]:
    return [EvaluationRecord.model_validate(item, strict=True) for item in stage.payload["records"]]


def _adapter_file(directory: Path) -> Path:
    for name in ("adapter_model.safetensors", "adapter_model.fake"):
        path = directory / name
        if path.is_file():
            return path
    raise FileNotFoundError("exported adapter payload is missing")
