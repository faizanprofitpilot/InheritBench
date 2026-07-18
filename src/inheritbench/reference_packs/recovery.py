"""Primary anchored recovery decision and local product bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import content_sha256, sha256_file
from inheritbench.orchestration.executor import _write_or_verify_json
from inheritbench.orchestration.schemas import FinalizedWebBundle, StageManifest
from inheritbench.orchestration.storage import load_plan
from inheritbench.reference_packs.parity import write_secondary_anchored_comparison


def finalize_anchored_recovery(
    anchored_run: Path,
    *,
    direct_baseline_run: Path,
    seeded_replication_run: Path,
) -> Path:
    anchored_run = anchored_run.resolve()
    direct_baseline_run = direct_baseline_run.resolve()
    seeded_replication_run = seeded_replication_run.resolve()
    plan = load_plan(anchored_run)
    if plan.product_run_kind != "PRODUCT_REFERENCE_SUCCESSION":
        raise ValueError("anchored recovery requires a product-reference execution")
    seeded = _json(seeded_replication_run / "seeded_reproducibility_report.json")
    if seeded["classification"] != "SEEDED_PROTOCOL_REPRODUCIBILITY_CONFIRMED":
        raise ValueError("seeded direct reproduction did not permit anchored execution")
    stages = _stages(anchored_run)
    required = {
        "ANCHORS_REQUIRED",
        "ANCHORS_ADDED",
        "SUPERVISION_FROZEN",
        "TRAINING",
        "CHECKPOINT_SELECTED",
        "CONFIRMATORY_COMPLETED",
        "ADVERSARIAL_COMPLETED",
        "RELOAD_VERIFIED",
        "REPLAY_VERIFIED",
        "COMPLETED",
    }
    if not required.issubset(stages):
        raise ValueError(f"anchored recovery is incomplete: {sorted(required - set(stages))}")
    readiness = _json(anchored_run / "readiness_report.json")
    direct_readiness = _json(direct_baseline_run / "readiness_report.json")
    evaluation = _json(anchored_run / "evaluation_summary.json")
    direct_evaluation = _json(direct_baseline_run / "evaluation_summary.json")
    accounting = _json(anchored_run / "label_accounting.json")
    replay = _json(anchored_run / "replay_receipt.json")
    adapter = _json(anchored_run / "adapter_reference.json")
    transition = direct_readiness["status"] == "MIGRATION_BLOCKED" and readiness["status"] in {
        "PASS",
        "CONDITIONAL_PASS",
    }
    integrity = (
        replay["status"] == "PASSED"
        and stages["RELOAD_VERIFIED"].payload["fresh_base_reload_verified"] is True
        and accounting["teacher_labels"] == 214
        and accounting["anchor_labels"] == 10
        and accounting["selected_training_records"] == 224
    )
    classification = (
        "GENERIC_ANCHORED_RECOVERY_CONFIRMED"
        if transition and integrity
        else "GENERIC_ANCHORED_RECOVERY_FAILED"
    )
    report: dict[str, Any] = {
        "schema_version": "inheritbench.anchored-recovery.v0.1",
        "run_id": plan.run_id,
        "canonical_plan_id": plan.canonical_plan_id,
        "execution_id": plan.execution_id,
        "protocol_amendment_sha256": (
            plan.protocol_amendment.amendment_sha256
            if plan.protocol_amendment is not None
            else None
        ),
        "classification": classification,
        "direct_seeded_gate": seeded["classification"],
        "material_improvement_definition": (
            "MIGRATION_BLOCKED_TO_PASS_OR_CONDITIONAL_PASS_UNDER_UNCHANGED_RULES"
        ),
        "material_improvement": transition,
        "readiness": readiness["status"],
        "readiness_reason_codes": readiness["reason_codes"],
        "direct_baseline_readiness": direct_readiness["status"],
        "direct_baseline_delta": {
            "confirmatory_semantic": (
                evaluation["confirmatory"]["semantic_correct"]
                - direct_evaluation["confirmatory"]["semantic_correct"]
            ),
            "adversarial_semantic": (
                evaluation["adversarial"]["semantic_correct"]
                - direct_evaluation["adversarial"]["semantic_correct"]
            ),
            "confirmatory_historical_strict": (
                evaluation["confirmatory"]["strict_valid"]
                - direct_evaluation["confirmatory"]["strict_valid"]
            ),
            "adversarial_historical_strict": (
                evaluation["adversarial"]["strict_valid"]
                - direct_evaluation["adversarial"]["strict_valid"]
            ),
        },
        "teacher_candidates": accounting["candidate_inputs"],
        "accepted_teacher_outputs": accounting["accepted_teacher_outputs"],
        "selected_teacher_outputs": accounting["teacher_labels"],
        "anchors_added": accounting["anchor_labels"],
        "selected_training_records": accounting["selected_training_records"],
        "confirmatory": evaluation["confirmatory"],
        "adversarial": evaluation["adversarial"],
        "selected_checkpoint_id": readiness["selected_checkpoint_id"],
        "adapter_sha256": adapter["adapter_sha256"],
        "fresh_base_reload_verified": stages["RELOAD_VERIFIED"].payload[
            "fresh_base_reload_verified"
        ],
        "replay_verified": replay["status"] == "PASSED",
        "frozen_teacher_outputs_used": True,
        "live_generic_teacher_generation_proven": False,
    }
    report["content_sha256"] = content_sha256(report)
    _write_or_verify_json(anchored_run / "anchored_recovery_report.json", report)
    historical_path = write_secondary_anchored_comparison(anchored_run)
    historical = _json(historical_path)
    _write_reference_web_bundle(
        anchored_run,
        direct_seeded=seeded,
        recovery=report,
        historical=historical,
    )
    _write_reference_evidence_manifest(anchored_run, seeded_replication_run)
    return anchored_run / "anchored_recovery_report.json"


def _write_reference_web_bundle(
    run_directory: Path,
    *,
    direct_seeded: dict[str, Any],
    recovery: dict[str, Any],
    historical: dict[str, Any],
) -> None:
    plan = load_plan(run_directory)
    readiness = _json(run_directory / "readiness_report.json")
    summaries = _json(run_directory / "evaluation_summary.json")
    residuals = _json(run_directory / "residual_failures.json")["records"]
    accounting = _json(run_directory / "label_accounting.json")
    compute = _json(run_directory / "compute_accounting.json")
    adapter = _json(run_directory / "adapter_reference.json")
    replay = _json(run_directory / "replay_receipt.json")
    stages = _stages(run_directory)
    intervention = stages["ANCHORS_ADDED"].payload["intervention"]
    reload_verification = stages["RELOAD_VERIFIED"].payload
    payload: dict[str, Any] = {
        "schema_version": "inheritbench.web-bundle.v0.3",
        "run_id": plan.run_id,
        "canonical_plan_id": plan.canonical_plan_id,
        "execution_id": plan.execution_id,
        "capability": {"id": plan.capability_id, "version": plan.capability_version},
        "strategy": plan.strategy_id,
        "protocol_amendment": (
            plan.protocol_amendment.model_dump(mode="json")
            if plan.protocol_amendment is not None
            else None
        ),
        "intervention": intervention,
        "reproduction": {
            "direct_seeded": direct_seeded["classification"],
            "direct_bitwise": direct_seeded["bitwise_classification"],
            "anchored_recovery": recovery["classification"],
            "historical_comparison": historical["classification"],
            "direct_baseline_delta": recovery["direct_baseline_delta"],
        },
        "readiness": readiness,
        "summaries": summaries,
        "residuals": residuals,
        "label_accounting": accounting,
        "compute_accounting": compute,
        "adapter": adapter,
        "reload_verification": reload_verification,
        "replay_verification": replay,
        "stages": [
            stage.stage for stage in sorted(stages.values(), key=lambda item: item.sequence)
        ],
    }
    payload["content_sha256"] = content_sha256(payload)
    _write_or_verify_json(
        run_directory / "web_bundle.json",
        FinalizedWebBundle.model_validate(payload, strict=True).model_dump(mode="json"),
    )


def _write_reference_evidence_manifest(
    run_directory: Path,
    seeded_replication_run: Path,
) -> None:
    names = (
        "anchored_recovery_report.json",
        "anchored_parity_report.json",
        "historical_comparison_report.json",
        "historical_prediction_comparison.json",
        "strict_metric_decomposition.json",
        "web_bundle.json",
    )
    intervention = next((run_directory / "interventions").glob("*/manifest.json"))
    files = {
        name: {
            "bytes": (run_directory / name).stat().st_size,
            "sha256": sha256_file(run_directory / name),
        }
        for name in names
    }
    files["anchor_intervention_manifest.json"] = {
        "bytes": intervention.stat().st_size,
        "sha256": sha256_file(intervention),
    }
    seeded_report = seeded_replication_run / "seeded_reproducibility_report.json"
    files["seeded_reproducibility_report.json"] = {
        "bytes": seeded_report.stat().st_size,
        "sha256": sha256_file(seeded_report),
    }
    _write_or_verify_json(
        run_directory / "reference_evidence_manifest.json",
        {
            "schema_version": "inheritbench.reference-evidence-manifest.v0.1",
            "files": files,
        },
    )


def _stages(run_directory: Path) -> dict[str, StageManifest]:
    return {
        stage.stage: stage
        for stage in (
            StageManifest.model_validate_json(path.read_bytes(), strict=True)
            for path in sorted((run_directory / "stages").glob("*/stage.json"))
        )
    }


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value
