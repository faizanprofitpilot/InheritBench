"""Seeded execution comparison with separate behavioral and bitwise gates."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import content_sha256, sha256_file
from inheritbench.orchestration.executor import _write_or_verify_json
from inheritbench.orchestration.planner import canonical_training_plan_sha256
from inheritbench.orchestration.schemas import StageManifest
from inheritbench.orchestration.storage import load_plan


def verify_seeded_replication(reference_run: Path, candidate_run: Path) -> Path:
    reference_run = reference_run.resolve()
    candidate_run = candidate_run.resolve()
    reference_plan = load_plan(reference_run)
    candidate_plan = load_plan(candidate_run)
    if candidate_plan.schema_version != "inheritbench.succession-plan.v0.3":
        raise ValueError("candidate is not an independent v0.3 execution")
    if candidate_plan.protocol_amendment is None:
        raise ValueError("candidate lacks a protocol amendment")
    amendment = _json(Path(candidate_plan.protocol_amendment.relative_path))
    tolerances = amendment["telemetry_tolerance"]
    reference_canonical_sha = canonical_training_plan_sha256(
        reference_plan.model_dump(mode="json"),
        authorized_anchor_pool=None,
    )
    canonical_match = candidate_plan.canonical_plan_sha256 == reference_canonical_sha
    reference_stages = _stages(reference_run)
    candidate_stages = _stages(candidate_run)
    required = {
        "SUPERVISION_FROZEN",
        "TRAINING",
        "CHECKPOINT_SELECTED",
        "CONFIRMATORY_COMPLETED",
        "ADVERSARIAL_COMPLETED",
        "READINESS_FINALIZED",
        "ADAPTER_EXPORTED",
        "COMPLETED",
    }
    if not required.issubset(candidate_stages):
        raise ValueError("candidate execution is incomplete")
    reference_preflight = _json(reference_run / "parity_preflight.json")
    candidate_preflight = _json(candidate_run / "parity_preflight.json")
    reference_shapes = _reference_tensor_shapes(reference_stages)
    preflight_checks = {
        "canonical_plan": canonical_match,
        "initial_adapter": (
            reference_preflight["initialization"]["initial_adapter_sha256"]
            == candidate_preflight["initialization"]["initial_adapter_sha256"]
        ),
        "trainable_tensor_names": (
            reference_preflight["initialization"]["trainable_parameter_names"]
            == candidate_preflight["initialization"]["trainable_parameter_names"]
        ),
        "trainable_tensor_shapes": (
            reference_shapes == candidate_preflight["initialization"]["trainable_parameter_shapes"]
        ),
        "trainable_parameters": (
            reference_preflight["initialization"]["trainable_parameters"]
            == candidate_preflight["initialization"]["trainable_parameters"]
        ),
        "supervision": (
            reference_preflight["supervision_sha256"] == candidate_preflight["supervision_sha256"]
        ),
        "schedule": (
            reference_preflight["schedule_sha256"] == candidate_preflight["schedule_sha256"]
        ),
        "sequence_lengths": (
            reference_preflight["sequence_lengths_sha256"]
            == candidate_preflight["sequence_lengths_sha256"]
        ),
        "encodings": (
            reference_preflight["training_encodings_sha256"]
            == candidate_preflight["training_encodings_sha256"]
        ),
        "training_profile": (
            reference_preflight["training_profile_sha256"]
            == candidate_preflight["training_profile_sha256"]
        ),
        "strategy_profile": (
            reference_preflight["strategy_profile_sha256"]
            == candidate_preflight["strategy_profile_sha256"]
        ),
        "optimizer": reference_preflight["optimizer"] == candidate_preflight["optimizer"],
        "inference": reference_preflight["inference"] == candidate_preflight["inference"],
        "candidate_preflight_status": (
            candidate_preflight["status"] == "SEEDED_DIRECT_REPLICATION_PREFLIGHT_PASS"
        ),
    }
    reference_training = reference_stages["TRAINING"].payload["training"]
    candidate_training = candidate_stages["TRAINING"].payload["training"]
    trajectory = _trajectory_comparison(
        reference_training,
        candidate_training,
        loss_absolute=float(tolerances["loss_absolute"]),
        loss_relative=float(tolerances["loss_relative"]),
        gradient_absolute=float(tolerances["gradient_norm_absolute"]),
        gradient_relative=float(tolerances["gradient_norm_relative"]),
    )
    checkpoint = _checkpoint_comparison(
        reference_stages,
        candidate_stages,
        loss_absolute=float(tolerances["loss_absolute"]),
        loss_relative=float(tolerances["loss_relative"]),
    )
    predictions = {
        surface: _surface_comparison(reference_stages, candidate_stages, surface)
        for surface in (
            "SOURCE_GATE_COMPLETED",
            "TARGET_BASELINE_COMPLETED",
            "CHECKPOINT_SELECTED",
            "CONFIRMATORY_COMPLETED",
            "ADVERSARIAL_COMPLETED",
        )
    }
    readiness = _readiness_comparison(reference_run, candidate_run)
    reference_adapter = _adapter_sha(reference_run)
    candidate_adapter = _adapter_sha(candidate_run)
    exported_adapter_exact = reference_adapter == candidate_adapter
    exact_prediction_behavior = all(
        comparison["exact_behavior"] for comparison in predictions.values()
    )
    preflight_passed = all(preflight_checks.values())
    behavioral = (
        preflight_passed
        and trajectory["within_frozen_tolerance"]
        and checkpoint["selection_behavior_exact"]
        and exact_prediction_behavior
        and readiness["normalized_readiness_exact"]
    )
    bitwise = (
        behavioral
        and trajectory["bitwise_telemetry"]
        and checkpoint["checkpoint_adapter_hashes_exact"]
        and exported_adapter_exact
    )
    report: dict[str, Any] = {
        "schema_version": "inheritbench.seeded-reproducibility.v0.1",
        "reference_run_id": reference_plan.run_id,
        "candidate_execution_id": candidate_plan.execution_id,
        "canonical_plan_id": candidate_plan.canonical_plan_id,
        "canonical_plan_sha256": candidate_plan.canonical_plan_sha256,
        "protocol_amendment_sha256": candidate_plan.protocol_amendment.amendment_sha256,
        "preflight_checks": preflight_checks,
        "trajectory": trajectory,
        "checkpoint": checkpoint,
        "predictions": predictions,
        "readiness": readiness,
        "exported_adapter": {
            "reference_sha256": reference_adapter,
            "candidate_sha256": candidate_adapter,
            "exact": exported_adapter_exact,
        },
        "bitwise_classification": (
            "BITWISE_REPRODUCIBILITY_CONFIRMED"
            if bitwise
            else "BITWISE_REPRODUCIBILITY_NOT_CONFIRMED"
        ),
        "behavioral_classification": (
            "BEHAVIORAL_REPRODUCIBILITY_CONFIRMED"
            if behavioral
            else "BEHAVIORAL_REPRODUCIBILITY_FAILED"
        ),
        "classification": (
            "SEEDED_PROTOCOL_REPRODUCIBILITY_CONFIRMED"
            if behavioral
            else "SEEDED_PROTOCOL_REPRODUCIBILITY_FAILED"
        ),
        "anchored_execution_status": ("PERMITTED" if behavioral else "BLOCKED_BEFORE_ANCHORED_RUN"),
        "historical_direct_comparison": ("HISTORICAL_DIRECT_RESULT_NOT_EXACTLY_RECONSTRUCTIBLE"),
    }
    report["content_sha256"] = content_sha256(report)
    _write_or_verify_json(candidate_run / "seeded_reproducibility_report.json", report)
    prediction_report = {
        "schema_version": "inheritbench.replication-prediction-comparison.v0.1",
        "surfaces": predictions,
    }
    prediction_report["content_sha256"] = content_sha256(prediction_report)
    _write_or_verify_json(candidate_run / "prediction_comparison.json", prediction_report)
    trajectory_report = {
        "schema_version": "inheritbench.replication-trajectory-comparison.v0.1",
        **trajectory,
    }
    trajectory_report["content_sha256"] = content_sha256(trajectory_report)
    _write_or_verify_json(candidate_run / "trajectory_comparison.json", trajectory_report)
    return candidate_run / "seeded_reproducibility_report.json"


def _trajectory_comparison(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    loss_absolute: float,
    loss_relative: float,
    gradient_absolute: float,
    gradient_relative: float,
) -> dict[str, Any]:
    reference_telemetry = reference["telemetry"]
    candidate_telemetry = candidate["telemetry"]
    ordered = len(reference_telemetry) == len(candidate_telemetry)
    losses_within = ordered
    gradients_within = ordered
    learning_rates_exact = ordered
    telemetry_bitwise = ordered
    maximum_loss_delta = 0.0
    maximum_gradient_delta = 0.0
    if ordered:
        for left, right in zip(reference_telemetry, candidate_telemetry, strict=True):
            if (
                left["optimizer_step"] != right["optimizer_step"]
                or left["schedule_cursor"] != right["schedule_cursor"]
                or left["processed_tokens"] != right["processed_tokens"]
            ):
                ordered = False
                losses_within = False
                gradients_within = False
                learning_rates_exact = False
                telemetry_bitwise = False
                break
            loss_delta = abs(float(left["loss"]) - float(right["loss"]))
            gradient_delta = abs(float(left["gradient_norm"]) - float(right["gradient_norm"]))
            maximum_loss_delta = max(maximum_loss_delta, loss_delta)
            maximum_gradient_delta = max(maximum_gradient_delta, gradient_delta)
            losses_within = losses_within and math.isclose(
                float(left["loss"]),
                float(right["loss"]),
                abs_tol=loss_absolute,
                rel_tol=loss_relative,
            )
            gradients_within = gradients_within and math.isclose(
                float(left["gradient_norm"]),
                float(right["gradient_norm"]),
                abs_tol=gradient_absolute,
                rel_tol=gradient_relative,
            )
            learning_rates_exact = learning_rates_exact and (
                left["learning_rate"] == right["learning_rate"]
            )
            telemetry_bitwise = telemetry_bitwise and all(
                left[key] == right[key] for key in ("loss", "gradient_norm", "learning_rate")
            )
    finite = all(
        math.isfinite(float(point[key]))
        for point in candidate_telemetry
        for key in ("loss", "gradient_norm", "learning_rate")
    )
    return {
        "ordered_steps": ordered,
        "step_count": len(candidate_telemetry),
        "losses_within_tolerance": losses_within,
        "gradient_norms_within_tolerance": gradients_within,
        "learning_rates_exact": learning_rates_exact,
        "finite": finite,
        "maximum_loss_delta": maximum_loss_delta,
        "maximum_gradient_norm_delta": maximum_gradient_delta,
        "bitwise_telemetry": telemetry_bitwise,
        "within_frozen_tolerance": (
            ordered
            and len(candidate_telemetry) == 168
            and losses_within
            and gradients_within
            and learning_rates_exact
            and finite
        ),
    }


def _checkpoint_comparison(
    reference: dict[str, StageManifest],
    candidate: dict[str, StageManifest],
    *,
    loss_absolute: float,
    loss_relative: float,
) -> dict[str, Any]:
    left_training = reference["TRAINING"].payload["training"]
    right_training = candidate["TRAINING"].payload["training"]
    left_hashes = {
        int(item["optimizer_step"]): item["adapter_sha256"] for item in left_training["checkpoints"]
    }
    right_hashes = {
        int(item["optimizer_step"]): item["adapter_sha256"]
        for item in right_training["checkpoints"]
    }
    left_decision = reference["CHECKPOINT_SELECTED"].payload["decision"]
    right_decision = candidate["CHECKPOINT_SELECTED"].payload["decision"]
    left_selected = _selected_step(left_decision)
    right_selected = _selected_step(right_decision)
    score_behavior = _checkpoint_scores(left_decision) == _checkpoint_scores(right_decision)
    validation_losses_within_tolerance = _checkpoint_losses_within_tolerance(
        left_decision,
        right_decision,
        absolute=loss_absolute,
        relative=loss_relative,
    )
    return {
        "configured_steps_exact": sorted(left_hashes) == sorted(right_hashes),
        "reference_adapter_hashes": left_hashes,
        "candidate_adapter_hashes": right_hashes,
        "checkpoint_adapter_hashes_exact": left_hashes == right_hashes,
        "reference_selected_step": left_selected,
        "candidate_selected_step": right_selected,
        "score_behavior_exact": score_behavior,
        "validation_losses_within_tolerance": validation_losses_within_tolerance,
        "selection_behavior_exact": (
            left_selected == right_selected
            and score_behavior
            and validation_losses_within_tolerance
        ),
    }


def _checkpoint_scores(decision: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in score.items()
            if key
            not in {
                "adapter_directory",
                "adapter_sha256",
                "checkpoint_id",
                "validation_loss",
            }
        }
        for score in decision["scores"]
    ]


def _checkpoint_losses_within_tolerance(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    absolute: float,
    relative: float,
) -> bool:
    reference_scores = {
        int(score["optimizer_step"]): float(score["validation_loss"])
        for score in reference["scores"]
    }
    candidate_scores = {
        int(score["optimizer_step"]): float(score["validation_loss"])
        for score in candidate["scores"]
    }
    if reference_scores.keys() != candidate_scores.keys():
        return False
    return all(
        math.isfinite(candidate_scores[step])
        and math.isclose(
            reference_scores[step],
            candidate_scores[step],
            abs_tol=absolute,
            rel_tol=relative,
        )
        for step in reference_scores
    )


def _reference_tensor_shapes(stages: dict[str, StageManifest]) -> dict[str, list[int]]:
    from safetensors import safe_open

    checkpoints = stages["TRAINING"].payload["training"]["checkpoints"]
    if not checkpoints:
        raise ValueError("reference training has no checkpoints")
    adapter_path = Path(checkpoints[0]["adapter_directory"]) / "adapter_model.safetensors"
    if not adapter_path.is_file():
        raise FileNotFoundError(adapter_path)
    shapes: dict[str, list[int]] = {}
    with safe_open(adapter_path, framework="pt", device="cpu") as tensors:
        for stored_name in list(tensors.keys()):
            parameter_name = stored_name.replace(".lora_A.weight", ".lora_A.default.weight")
            parameter_name = parameter_name.replace(".lora_B.weight", ".lora_B.default.weight")
            shapes[parameter_name] = list(tensors.get_slice(stored_name).get_shape())
    return shapes


def _selected_step(decision: dict[str, Any]) -> int | None:
    selected = decision.get("selected_checkpoint_id")
    if not isinstance(selected, str):
        return None
    return int(selected.rsplit("-step-", 1)[1])


def _surface_comparison(
    reference: dict[str, StageManifest],
    candidate: dict[str, StageManifest],
    stage: str,
) -> dict[str, Any]:
    if stage == "CHECKPOINT_SELECTED":
        left = _validation_records(reference[stage])
        right = _validation_records(candidate[stage])
    else:
        left = _evaluation_records(reference[stage])
        right = _evaluation_records(candidate[stage])
    return {
        "records": len(right),
        "record_keys_exact": set(left) == set(right),
        "raw_outputs_exact": set(left) == set(right)
        and all(left[key]["raw_output"] == right[key]["raw_output"] for key in left),
        "generation_inputs_exact": set(left) == set(right)
        and all(left[key]["generation"] == right[key]["generation"] for key in left),
        "evaluator_facts_exact": set(left) == set(right)
        and all(left[key]["evaluation"] == right[key]["evaluation"] for key in left),
        "exact_behavior": left == right,
    }


def _evaluation_records(stage: StageManifest) -> dict[str, dict[str, Any]]:
    return {
        item["generation"]["record_id"]: _normalized_record(item)
        for item in stage.payload["records"]
    }


def _validation_records(stage: StageManifest) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for checkpoint_id, values in stage.payload["evaluations"].items():
        step = checkpoint_id.rsplit("-step-", 1)[1]
        for item in values:
            record_id = item["generation"]["record_id"]
            records[f"{step}:{record_id}"] = _normalized_record(item)
    return records


def _normalized_record(item: dict[str, Any]) -> dict[str, Any]:
    generation = dict(item["generation"])
    generation.pop("latency_ms", None)
    evaluation = _without_content_hashes(item["evaluation"])
    model = dict(item["model"])
    model.pop("adapter_sha256", None)
    return {
        "raw_output": generation["raw_output"],
        "generation": generation,
        "evaluation": evaluation,
        "model": model,
        "surface": item["surface"],
        "system_role": item["system_role"],
    }


def _without_content_hashes(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_content_hashes(item)
            for key, item in value.items()
            if key != "content_sha256"
        }
    if isinstance(value, list):
        return [_without_content_hashes(item) for item in value]
    return value


def _readiness_comparison(reference_run: Path, candidate_run: Path) -> dict[str, Any]:
    reference = _json(reference_run / "readiness_report.json")
    candidate = _json(candidate_run / "readiness_report.json")
    for value in (reference, candidate):
        value.pop("content_sha256", None)
        value.pop("run_id", None)
        value.pop("selected_checkpoint_id", None)
        value.pop("adapter_sha256", None)
    return {
        "reference_status": reference["status"],
        "candidate_status": candidate["status"],
        "normalized_readiness_exact": reference == candidate,
    }


def _adapter_sha(run_directory: Path) -> str:
    reference = _json(run_directory / "adapter_reference.json")
    path = Path(reference["adapter_directory"])
    for name in ("adapter_model.safetensors", "adapter_model.fake"):
        candidate = path / name
        if candidate.is_file():
            return sha256_file(candidate)
    raise FileNotFoundError("exported adapter payload is missing")


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
