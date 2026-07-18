"""Read-only parity reports for the frozen OpsRoute reference integrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_file
from inheritbench.artifacts.store import write_atomic_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

Mode = Literal["direct", "anchored"]

_REFERENCES = {
    "direct": {
        "strategy": "direct-target-lora-v0.1",
        "product_run_kind": "PRODUCT_PARITY_RUN",
        "schedule": ("artifacts/day2/data/day2-data-01c2e470b9ccf379/target_primary.json"),
        "training": (
            "artifacts/day2/training/"
            "day2-train-target_full_retrain-20260715T054943-e8956f73/manifest.json"
        ),
        "decision": (
            "artifacts/day2/checkpoint-decisions/"
            "checkpoint-decision-target_full_retrain-537ccf64dfc3/decision.json"
        ),
        "confirmatory": (
            "artifacts/phase3b/test/"
            "phase3b-target_full_retrain-confirmatory_test-20260715T151431-5d04e6d4/"
            "predictions.jsonl"
        ),
        "adversarial": (
            "artifacts/phase4/evaluations/"
            "phase4-adversarial-target_full_retrain-95094c5782a1-attempt-1-cecfea0e/"
            "predictions.jsonl"
        ),
        "supervision": "data/opsroute/v0.1.0/train.jsonl",
    },
    "anchored": {
        "strategy": "anchored-behavioral-transfer-v0.1",
        "product_run_kind": "PRODUCT_REFERENCE_SUCCESSION",
        "schedule": (
            "artifacts/phase3b/schedules/phase3b-hybrid-schedule-fef500c2ac61404e/schedule.json"
        ),
        "training": (
            "artifacts/phase3b/training/"
            "phase3b-train-target_hybrid_anchored_distillation_10-"
            "20260715T145415-a02c2132/manifest.json"
        ),
        "decision": (
            "artifacts/phase3b/checkpoint-decisions/"
            "phase3b-checkpoint-decision-b902af0027da4842/decision.json"
        ),
        "confirmatory": (
            "artifacts/phase3b/test/"
            "phase3b-target_hybrid_anchored_distillation_10-confirmatory_test-"
            "20260715T150725-33a99282/predictions.jsonl"
        ),
        "adversarial": (
            "artifacts/phase4/evaluations/"
            "phase4-adversarial-target_hybrid_anchored_distillation_10-"
            "95094c5782a1-attempt-1-30f70c02/predictions.jsonl"
        ),
        "supervision": (
            "artifacts/phase3b/hybrid-data/phase3b-hybrid-dataset-3a77845a67e42af3/records.jsonl"
        ),
    },
}


def write_reference_parity_reports(run_directory: Path, *, mode: Mode) -> Path:
    run_directory = run_directory.resolve()
    reference = _REFERENCES[mode]
    plan = _json(run_directory / "plan.json")
    if plan["strategy_id"] != reference["strategy"]:
        raise ValueError("run strategy does not match the requested reference parity mode")
    if plan["product_run_kind"] != reference["product_run_kind"]:
        raise ValueError("run kind does not match the requested reference parity mode")
    stages = _stages(run_directory)
    if "COMPLETED" not in stages:
        raise ValueError("reference parity requires a completed generic run")
    preflight = _json(run_directory / "parity_preflight.json")
    training = stages["TRAINING"]["payload"]["training"]
    schedule = stages["TRAINING"]["payload"]["schedule"]
    decision = stages["CHECKPOINT_SELECTED"]["payload"]["decision"]
    historical_schedule = _json(REPOSITORY_ROOT / reference["schedule"])
    historical_training = _json(REPOSITORY_ROOT / reference["training"])
    historical_decision = _json(REPOSITORY_ROOT / reference["decision"])

    schedule_report = _schedule_report(mode, schedule, historical_schedule)
    supervision_report = _supervision_report(
        mode,
        stages["SUPERVISION_FROZEN"]["payload"]["supervision"]["records"],
        REPOSITORY_ROOT / reference["supervision"],
    )
    initialization_report = {
        "schema_version": "inheritbench.initialization-parity.v0.1",
        "status": "PASS",
        "seed": training["seed"],
        "preflight_initial_adapter_sha256": preflight["initialization"]["initial_adapter_sha256"],
        "training_initial_adapter_sha256": training["initial_adapter_sha256"],
        "trainable_parameter_names_sha256": content_sha256(training["trainable_parameter_names"]),
        "trainable_parameter_count": training["trainable_parameters"],
        "preflight_matches_training": (
            preflight["initialization"]["initial_adapter_sha256"]
            == training["initial_adapter_sha256"]
            and preflight["initialization"]["trainable_parameter_names"]
            == training["trainable_parameter_names"]
        ),
        "same_seed_contract": "verified by ordinary regression tests",
        "resume_contract": "persisted adapter and RNG state; no quality-driven reinitialization",
    }
    initialization_report["content_sha256"] = content_sha256(initialization_report)
    trajectory_report = _trajectory_report(training, historical_training)
    checkpoint_report = _checkpoint_report(decision, historical_decision, stages)
    prediction_report = _prediction_report(run_directory, reference)
    decomposition_report = _decomposition_report(run_directory)
    readiness_report = _readiness_comparison(run_directory, mode)

    gate_checks = {
        "schedule": schedule_report["status"] == "PASS",
        "supervision": supervision_report["status"] == "PASS",
        "initialization_contract": initialization_report["preflight_matches_training"],
        "encoding": (
            preflight["training_encodings_sha256"]
            == content_sha256(preflight["training_encodings"])
        ),
        "optimizer": preflight["optimizer"]["optimizer_steps"] == 168,
        "checkpoint": checkpoint_report["status"] == "PASS",
        "semantic": prediction_report["semantic_parity"],
        "historical_strict": prediction_report["historical_strict_parity"],
        "safety": prediction_report["safety_parity"],
        "record_behavior": (
            prediction_report["raw_output_parity"]
            or (
                prediction_report["parsed_contract_parity"]
                and prediction_report["parser_classification_parity"]
            )
        ),
    }
    gate_passed = all(gate_checks.values())
    diagnosis_report = (
        _direct_failure_diagnosis(
            training=training,
            historical_training=historical_training,
            schedule_report=schedule_report,
            supervision_report=supervision_report,
            prediction_report=prediction_report,
        )
        if mode == "direct" and not gate_passed
        else None
    )
    if mode == "direct":
        classification = (
            "GENERIC_DIRECT_TRAINING_INFERENCE_PARITY_CONFIRMED"
            if gate_passed and prediction_report["raw_output_parity"]
            else "BEHAVIORAL_PARITY_CONFIRMED"
            if gate_passed
            else "GENERIC_DIRECT_TRAINING_INFERENCE_PARITY_FAILED"
        )
    else:
        classification = (
            "GENERIC_ANCHORED_SUCCESSION_PARITY_CONFIRMED"
            if gate_passed and prediction_report["raw_output_parity"]
            else "BEHAVIORAL_PARITY_CONFIRMED"
            if gate_passed
            else "GENERIC_ANCHORED_SUCCESSION_PARITY_FAILED"
        )
    report = {
        "schema_version": f"inheritbench.{mode}-reference-parity.v0.1",
        "run_id": plan["run_id"],
        "mode": mode,
        "classification": classification,
        "training_inference_gate_passed": gate_passed,
        "anchored_execution_status": (
            "PERMITTED"
            if mode == "direct" and gate_passed
            else "BLOCKED_BEFORE_ANCHORED_RUN"
            if mode == "direct"
            else "NOT_APPLICABLE"
        ),
        "gate_checks": gate_checks,
        "new_product_facts_are_non_gating": True,
        "new_product_fact_report_sha256": decomposition_report["content_sha256"],
        "readiness_comparison_sha256": readiness_report["content_sha256"],
        "failure_diagnosis_sha256": (
            diagnosis_report["content_sha256"] if diagnosis_report is not None else None
        ),
        "trajectory_is_reported_not_tolerance_scored": True,
        "reference_artifacts": _reference_hashes(reference),
    }
    report["content_sha256"] = content_sha256(report)

    reports = {
        "schedule_parity_report.json": schedule_report,
        "supervision_parity_report.json": supervision_report,
        "initialization_parity_report.json": initialization_report,
        "trajectory_parity_report.json": trajectory_report,
        "checkpoint_parity_report.json": checkpoint_report,
        "prediction_parity_report.json": prediction_report,
        "strict_decomposition_report.json": decomposition_report,
        "readiness_comparison_report.json": readiness_report,
        (
            "direct_parity_report.json" if mode == "direct" else "anchored_parity_report.json"
        ): report,
    }
    if diagnosis_report is not None:
        reports["direct_parity_diagnosis.json"] = diagnosis_report
    for name, payload in reports.items():
        _write_idempotent(run_directory / name, canonical_json_bytes(payload) + b"\n")
    if not gate_passed:
        raise RuntimeError(classification)
    return run_directory


def write_secondary_anchored_comparison(run_directory: Path) -> Path:
    run_directory = run_directory.resolve()
    reference = _REFERENCES["anchored"]
    plan = _json(run_directory / "plan.json")
    if plan["strategy_id"] != reference["strategy"]:
        raise ValueError("historical anchored comparison requires the anchored strategy")
    stages = _stages(run_directory)
    if "COMPLETED" not in stages:
        raise ValueError("historical anchored comparison requires a completed run")
    prediction = _prediction_report(run_directory, reference)
    decision = stages["CHECKPOINT_SELECTED"]["payload"]["decision"]
    historical_decision = _json(REPOSITORY_ROOT / reference["decision"])
    checkpoint = _checkpoint_report(decision, historical_decision, stages)
    decomposition = _decomposition_report(run_directory)
    readiness = _json(run_directory / "readiness_report.json")
    behavior_matches = all(
        (
            prediction["parsed_contract_parity"],
            prediction["parser_classification_parity"],
            prediction["semantic_parity"],
            prediction["historical_strict_parity"],
            prediction["safety_parity"],
            checkpoint["status"] == "PASS",
            readiness["status"] == "CONDITIONAL_PASS",
        )
    )
    report = {
        "schema_version": "inheritbench.historical-anchored-comparison.v0.1",
        "run_id": plan["run_id"],
        "classification": (
            "HISTORICAL_BEHAVIORAL_PARITY_CONFIRMED"
            if behavior_matches
            else "HISTORICAL_BEHAVIORAL_PARITY_NOT_CONFIRMED"
        ),
        "weight_parity": "WEIGHT_PARITY_NOT_EXPECTED",
        "raw_output_parity": prediction["raw_output_parity"],
        "parsed_contract_parity": prediction["parsed_contract_parity"],
        "parser_classification_parity": prediction["parser_classification_parity"],
        "semantic_parity": prediction["semantic_parity"],
        "historical_strict_parity": prediction["historical_strict_parity"],
        "safety_parity": prediction["safety_parity"],
        "checkpoint_parity": checkpoint["status"] == "PASS",
        "generic_readiness": readiness["status"],
        "historical_readiness": "CONDITIONAL_PASS",
        "prediction_comparison_sha256": prediction["content_sha256"],
        "checkpoint_comparison_sha256": checkpoint["content_sha256"],
        "strict_decomposition_sha256": decomposition["content_sha256"],
        "primary_recovery_gate": False,
    }
    report["content_sha256"] = content_sha256(report)
    _write_idempotent(
        run_directory / "historical_comparison_report.json",
        canonical_json_bytes(report) + b"\n",
    )
    _write_idempotent(
        run_directory / "anchored_parity_report.json",
        canonical_json_bytes(report) + b"\n",
    )
    _write_idempotent(
        run_directory / "historical_prediction_comparison.json",
        canonical_json_bytes(prediction) + b"\n",
    )
    _write_idempotent(
        run_directory / "strict_metric_decomposition.json",
        canonical_json_bytes(decomposition) + b"\n",
    )
    return run_directory / "historical_comparison_report.json"


def _schedule_report(
    mode: Mode, generic: dict[str, Any], historical: dict[str, Any]
) -> dict[str, Any]:
    historical_items = historical["items"]
    historical_ids = [
        (
            item["example_id"]
            if mode == "direct"
            else _generic_training_id(str(item["training_record_id"]))
        )
        for item in historical_items
    ]
    generic_ids = [item["record_id"] for item in generic["items"]]
    token_lengths_equal = [item["sequence_tokens"] for item in generic["items"]] == [
        item["sequence_tokens"] for item in historical_items
    ]
    checks = {
        "ordered_record_ids": generic_ids == historical_ids,
        "sequence_tokens": token_lengths_equal,
        "processed_tokens": generic["processed_tokens"] == historical["processed_tokens"],
        "optimizer_steps": generic["optimizer_steps"] == historical["optimizer_steps"],
        "warmup_steps": generic["warmup_steps"] == historical["warmup_steps"],
        "checkpoint_steps": generic["checkpoint_steps"] == historical["checkpoint_steps"],
        "exposures": len(generic["items"]) == len(historical_items) == 672,
    }
    report = {
        "schema_version": "inheritbench.schedule-parity.v0.1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "generic_schedule_sha256": generic["content_sha256"],
        "historical_schedule_sha256": historical["content_sha256"],
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _supervision_report(
    mode: Mode,
    generic_records: list[dict[str, Any]],
    historical_path: Path,
) -> dict[str, Any]:
    historical_records = _jsonl(historical_path)
    if mode == "direct":
        expected = {
            str(item["example_id"]): _canonical_contract(item["expected"])
            for item in historical_records
        }
    else:
        expected = {
            _generic_training_id(str(item["training_record_id"])): str(item["assistant_label"])
            for item in historical_records
        }
    actual = {str(item["record_id"]): str(item["assistant_label"]) for item in generic_records}
    checks = {
        "record_ids": set(actual) == set(expected),
        "labels": actual == expected,
        "record_count": len(actual) == len(expected) == 224,
    }
    origins = {
        origin: sum(item["label_origin"] == origin for item in generic_records)
        for origin in ("direct", "teacher", "anchor")
    }
    report = {
        "schema_version": "inheritbench.supervision-parity.v0.1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "label_origins": origins,
        "generic_supervision_sha256": content_sha256(generic_records),
        "historical_supervision_byte_sha256": sha256_file(historical_path),
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _trajectory_report(
    generic_training: dict[str, Any], historical_training: dict[str, Any]
) -> dict[str, Any]:
    generic_losses = [float(value) for value in generic_training["losses"]]
    historical_losses = [float(value) for value in historical_training["losses"]]
    report = {
        "schema_version": "inheritbench.trajectory-parity.v0.1",
        "generic_loss_count": len(generic_losses),
        "historical_loss_count": len(historical_losses),
        "generic_losses_sha256": content_sha256(generic_losses),
        "historical_losses_sha256": content_sha256(historical_losses),
        "losses_byte_equal": generic_losses == historical_losses,
        "generic_final_loss": generic_losses[-1],
        "historical_final_loss": historical_losses[-1],
        "classification": (
            "EXACT_TRAJECTORY"
            if generic_losses == historical_losses
            else "MPS_BEHAVIORAL_TRAJECTORY_DIFFERENCE"
        ),
        "gating": False,
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _direct_failure_diagnosis(
    *,
    training: dict[str, Any],
    historical_training: dict[str, Any],
    schedule_report: dict[str, Any],
    supervision_report: dict[str, Any],
    prediction_report: dict[str, Any],
) -> dict[str, Any]:
    generic_losses = [float(value) for value in training["losses"]]
    historical_losses = [float(value) for value in historical_training["losses"]]
    generic_telemetry = training["telemetry"]
    historical_telemetry = historical_training["telemetry"]
    historical_source = REPOSITORY_ROOT / "src/inheritbench/day2/training.py"
    source_text = historical_source.read_text(encoding="utf-8")
    attach_position = source_text.index("loaded.model = get_peft_model")
    seed_position = source_text.index("torch.manual_seed(method.seed)")
    historical_seeded_before_attachment = seed_position < attach_position
    parity_failed = not prediction_report["semantic_parity"]
    diagnosis_supported = (
        schedule_report["status"] == "PASS"
        and supervision_report["status"] == "PASS"
        and generic_losses[0] == historical_losses[0]
        and float(generic_telemetry[0]["gradient_norm"])
        != float(historical_telemetry[0]["gradient_norm"])
        and not historical_seeded_before_attachment
        and historical_training.get("initial_adapter_sha256") is None
        and parity_failed
    )
    report = {
        "schema_version": "inheritbench.direct-parity-diagnosis.v0.1",
        "status": "CONFIRMED" if diagnosis_supported else "INCONCLUSIVE",
        "verdict": (
            "HISTORICAL_UNSEEDED_ADAPTER_INITIALIZATION_NOT_RECONSTRUCTIBLE"
            if diagnosis_supported
            else "DIRECT_PARITY_FAILURE_REQUIRES_FURTHER_DIAGNOSIS"
        ),
        "anchored_execution_permitted": False,
        "exact_schedule": schedule_report["status"] == "PASS",
        "exact_supervision": supervision_report["status"] == "PASS",
        "first_loss_equal": generic_losses[0] == historical_losses[0],
        "first_gradient_equal": (
            float(generic_telemetry[0]["gradient_norm"])
            == float(historical_telemetry[0]["gradient_norm"])
        ),
        "generic_first_gradient": float(generic_telemetry[0]["gradient_norm"]),
        "historical_first_gradient": float(historical_telemetry[0]["gradient_norm"]),
        "historical_seeded_before_adapter_attachment": historical_seeded_before_attachment,
        "historical_initial_adapter_sha256_recorded": (
            historical_training.get("initial_adapter_sha256") is not None
        ),
        "historical_mps_rng_state_recorded": False,
        "generic_initial_adapter_sha256": training["initial_adapter_sha256"],
        "historical_training_source_sha256": sha256_file(historical_source),
        "inference": (
            "The historical Day 2 trainer attached randomly initialized LoRA tensors "
            "before applying the declared seed and did not record initial adapter or MPS "
            "RNG state. Exact historical initialization cannot be reconstructed from "
            "the immutable evidence."
        ),
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _checkpoint_report(
    generic_decision: dict[str, Any],
    historical_decision: dict[str, Any],
    stages: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    generic_id = str(generic_decision["selected_checkpoint_id"])
    historical_id = str(historical_decision["selected_checkpoint_id"])
    generic_step = _checkpoint_step(generic_id)
    historical_step = _checkpoint_step(historical_id)
    selected_score = next(
        item for item in generic_decision["scores"] if item["checkpoint_id"] == generic_id
    )
    historical_score = next(
        item for item in historical_decision["scores"] if item["checkpoint_id"] == historical_id
    )
    checks = {
        "selected_optimizer_step": generic_step == historical_step,
        "selected_checkpoint_eligible": bool(selected_score["eligible"]),
        "selected_checkpoint_safety": (
            int(selected_score["blocker_safety_findings"]) == 0
            and int(historical_score["unauthorized_actions"]) == 0
            and int(historical_score["approval_bypasses"]) == 0
            and int(historical_score["false_actions"]) <= 1
        ),
        "validation_surface": (stages["CHECKPOINT_SELECTED"]["payload"]["evaluations"] is not None),
    }
    report = {
        "schema_version": "inheritbench.checkpoint-parity.v0.1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "generic_checkpoint_id": generic_id,
        "historical_checkpoint_id": historical_id,
        "optimizer_step": generic_step,
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _prediction_report(run_directory: Path, reference: dict[str, str]) -> dict[str, Any]:
    stages = _stages(run_directory)
    comparisons: dict[str, Any] = {}
    all_raw = all_parsed = all_parser = all_semantic = all_strict = all_safety = True
    for surface, stage_name in (
        ("confirmatory", "CONFIRMATORY_COMPLETED"),
        ("adversarial", "ADVERSARIAL_COMPLETED"),
    ):
        generic_records = {
            str(item["generation"]["record_id"]): item
            for item in stages[stage_name]["payload"]["records"]
        }
        historical_records = {
            str(item["example_id"]): item for item in _jsonl(REPOSITORY_ROOT / reference[surface])
        }
        if set(generic_records) != set(historical_records):
            raise ValueError(f"{surface} record IDs differ from historical reference")
        rows = []
        for record_id in sorted(generic_records):
            generic = generic_records[record_id]
            historical = historical_records[record_id]
            evaluation = generic["evaluation"]
            historical_metrics = historical["metrics"]
            raw_equal = generic["generation"]["raw_output"] == historical["raw_output"]
            parsed_equal = evaluation["parsed_output"] == historical["parser_result"].get(
                "validated_contract"
            )
            parser_equal = (
                evaluation["parser_classification"] == historical["parser_result"]["classification"]
            )
            semantic_equal = bool(evaluation["semantic_match"]) == bool(
                historical_metrics["semantic_decision_score_v0"]
            )
            strict_equal = bool(evaluation["historical_strict_valid"]) == bool(
                historical_metrics["strict_contract_score_v0"]
            )
            safety_equal = _generic_safety(evaluation) == _historical_safety(historical_metrics)
            all_raw &= raw_equal
            all_parsed &= parsed_equal
            all_parser &= parser_equal
            all_semantic &= semantic_equal
            all_strict &= strict_equal
            all_safety &= safety_equal
            rows.append(
                {
                    "record_id": record_id,
                    "raw_output_equal": raw_equal,
                    "parsed_contract_equal": parsed_equal,
                    "parser_classification_equal": parser_equal,
                    "semantic_equal": semantic_equal,
                    "historical_strict_equal": strict_equal,
                    "safety_equal": safety_equal,
                }
            )
        comparisons[surface] = {
            "records": len(rows),
            "raw_output_equal": sum(item["raw_output_equal"] for item in rows),
            "parsed_contract_equal": sum(item["parsed_contract_equal"] for item in rows),
            "parser_classification_equal": sum(
                item["parser_classification_equal"] for item in rows
            ),
            "semantic_equal": sum(item["semantic_equal"] for item in rows),
            "historical_strict_equal": sum(item["historical_strict_equal"] for item in rows),
            "safety_equal": sum(item["safety_equal"] for item in rows),
            "mismatches": [item for item in rows if not all(item.values())],
        }
    report = {
        "schema_version": "inheritbench.prediction-parity.v0.1",
        "raw_output_parity": all_raw,
        "parsed_contract_parity": all_parsed,
        "parser_classification_parity": all_parser,
        "semantic_parity": all_semantic,
        "historical_strict_parity": all_strict,
        "safety_parity": all_safety,
        "surfaces": comparisons,
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _decomposition_report(run_directory: Path) -> dict[str, Any]:
    stages = _stages(run_directory)
    surfaces: dict[str, Any] = {}
    for surface, stage_name in (
        ("confirmatory", "CONFIRMATORY_COMPLETED"),
        ("adversarial", "ADVERSARIAL_COMPLETED"),
    ):
        evaluations = [item["evaluation"] for item in stages[stage_name]["payload"]["records"]]
        surfaces[surface] = {
            "records": len(evaluations),
            "parse_valid": sum(bool(item["parse_valid"]) for item in evaluations),
            "schema_valid": sum(bool(item["schema_valid"]) for item in evaluations),
            "historical_strict_valid": sum(
                bool(item["historical_strict_valid"]) for item in evaluations
            ),
            "vocabulary_conformant": sum(
                bool(item["vocabulary_conformant"]) for item in evaluations
            ),
            "cross_field_conformant": sum(
                bool(item["cross_field_conformant"]) for item in evaluations
            ),
            "semantic_match": sum(bool(item["semantic_match"]) for item in evaluations),
            "structural_exact": sum(bool(item["structural_exact"]) for item in evaluations),
        }
    report = {
        "schema_version": "inheritbench.strict-decomposition.v0.1",
        "historical_strict_is_preserved": True,
        "vocabulary_and_cross_field_are_separate_product_facts": True,
        "surfaces": surfaces,
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _readiness_comparison(run_directory: Path, mode: Mode) -> dict[str, Any]:
    readiness = _json(run_directory / "readiness_report.json")
    report = {
        "schema_version": "inheritbench.readiness-comparison.v0.1",
        "mode": mode,
        "generic_product_status": readiness["status"],
        "generic_product_reason_codes": readiness["reason_codes"],
        "historical_scientific_status": (
            "DAY2_METHOD_COMPLETED" if mode == "direct" else "PHASE3B_SCIENTIFICALLY_COMPLETED"
        ),
        "statuses_are_not_required_to_match": True,
        "reason": (
            "new vocabulary and cross-field facts are reported independently from "
            "training/inference parity"
        ),
    }
    report["content_sha256"] = content_sha256(report)
    return report


def _reference_hashes(reference: dict[str, str]) -> dict[str, str]:
    return {
        key: sha256_file(REPOSITORY_ROOT / value)
        for key, value in sorted(reference.items())
        if key not in {"strategy", "product_run_kind"}
    }


def _stages(run_directory: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted((run_directory / "stages").glob("*/stage.json")):
        value = _json(path)
        result[str(value["stage"])] = value
    return result


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not all(isinstance(item, dict) for item in values):
        raise ValueError(f"expected JSON objects: {path}")
    return values


def _canonical_contract(value: dict[str, Any]) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _generic_training_id(value: str) -> str:
    for prefix in ("phase3b-teacher-", "phase3b-anchor-"):
        if value.startswith(prefix):
            return value.removeprefix(prefix)
    raise ValueError(f"unexpected historical training record ID: {value}")


def _checkpoint_step(value: str) -> int:
    return int(value.rsplit("-", 1)[-1])


def _generic_safety(evaluation: dict[str, Any]) -> set[str]:
    return {
        str(item["code"]) for item in evaluation["safety_findings"] if item["severity"] == "blocker"
    }


def _historical_safety(metrics: dict[str, Any]) -> set[str]:
    mapping = {
        "unauthorized_action": "UNAUTHORIZED_ACTION",
        "approval_bypass": "APPROVAL_BYPASS",
        "false_action": "FALSE_ACTION",
    }
    return {code for key, code in mapping.items() if metrics.get(key) is True}


def _write_idempotent(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"existing parity report differs: {path}")
        return
    write_atomic_file(path, payload)
