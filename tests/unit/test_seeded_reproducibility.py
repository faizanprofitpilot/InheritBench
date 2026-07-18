from __future__ import annotations

import json
from pathlib import Path

import pytest

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.model_adapters.schemas import (
    ModelRuntimeIdentity,
    TrainingInitialization,
    TrainingResult,
)
from inheritbench.orchestration.executor import _training_initialization_matches
from inheritbench.orchestration.reproducibility import _trajectory_comparison
from inheritbench.reference_packs.protocol import verify_seeded_reference_amendment


def test_frozen_telemetry_tolerance_accepts_tiny_mps_drift() -> None:
    reference = {"telemetry": _telemetry()}
    candidate = {"telemetry": _telemetry(loss_delta=5e-7, gradient_delta=5e-7)}
    comparison = _trajectory_comparison(
        reference,
        candidate,
        loss_absolute=1e-6,
        loss_relative=1e-5,
        gradient_absolute=1e-6,
        gradient_relative=1e-5,
    )
    assert comparison["within_frozen_tolerance"] is True
    assert comparison["bitwise_telemetry"] is False


def test_frozen_telemetry_tolerance_rejects_drift_and_nonfinite_values() -> None:
    reference = {"telemetry": _telemetry()}
    outside = {"telemetry": _telemetry(loss_delta=1e-2)}
    comparison = _trajectory_comparison(
        reference,
        outside,
        loss_absolute=1e-6,
        loss_relative=1e-5,
        gradient_absolute=1e-6,
        gradient_relative=1e-5,
    )
    assert comparison["within_frozen_tolerance"] is False
    nonfinite = _telemetry()
    nonfinite[0]["gradient_norm"] = float("nan")
    comparison = _trajectory_comparison(
        reference,
        {"telemetry": nonfinite},
        loss_absolute=1e-6,
        loss_relative=1e-5,
        gradient_absolute=1e-6,
        gradient_relative=1e-5,
    )
    assert comparison["finite"] is False
    assert comparison["within_frozen_tolerance"] is False


def test_protocol_amendment_hash_is_immutable(tmp_path: Path) -> None:
    path = tmp_path / "amendment.json"
    payload = {
        "schema_version": "inheritbench.seeded-reference-amendment.v0.1",
        "amendment_id": "seeded-reference-succession-v0.1",
        "status": "PROSPECTIVE_FROZEN",
        "git_preregistered": False,
    }
    payload["amendment_sha256"] = content_sha256(payload)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")
    assert verify_seeded_reference_amendment(path)["git_preregistered"] is False
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["status"] = "CHANGED"
    path.write_bytes(canonical_json_bytes(tampered) + b"\n")
    with pytest.raises(ValueError, match="content hash mismatch"):
        verify_seeded_reference_amendment(path)


def test_rng_observability_hashes_are_not_tensor_identity_gates() -> None:
    initialization = TrainingInitialization(
        seed=7,
        initial_adapter_sha256="1" * 64,
        trainable_parameter_names=["layer.weight"],
        trainable_parameter_shapes={"layer.weight": [2, 2]},
        trainable_parameters=4,
        total_parameters=8,
        rng_before_model_load_sha256="2" * 64,
        rng_before_lora_sha256="3" * 64,
        rng_after_lora_sha256="4" * 64,
    )
    training = TrainingResult(
        status="COMPLETED",
        run_id="run",
        model=ModelRuntimeIdentity(
            registry_id="fake",
            model_id="fake",
            revision="revision",
            architecture_class="Fake",
            tokenizer_id="fake",
            tokenizer_revision="revision",
            device="cpu",
            dtype="float32",
            adapter_sha256=None,
        ),
        trainable_parameters=4,
        total_parameters=8,
        seed=7,
        initial_adapter_sha256="1" * 64,
        trainable_parameter_names=["layer.weight"],
        trainable_parameter_shapes={"layer.weight": [2, 2]},
        rng_before_model_load_sha256="5" * 64,
        rng_before_lora_sha256="6" * 64,
        rng_after_lora_sha256="7" * 64,
        processed_tokens=1,
        optimizer_steps_completed=1,
        duration_seconds=0,
        losses=[],
        telemetry=[],
        checkpoints=[],
        error=None,
    )
    assert _training_initialization_matches(initialization, training) is True
    changed = training.model_copy(update={"initial_adapter_sha256": "8" * 64})
    assert _training_initialization_matches(initialization, changed) is False


def _telemetry(
    *, loss_delta: float = 0.0, gradient_delta: float = 0.0
) -> list[dict[str, int | float | None]]:
    return [
        {
            "optimizer_step": step,
            "schedule_cursor": step * 4,
            "processed_tokens": step * 100,
            "loss": 1.0 / step + loss_delta,
            "learning_rate": step / 1_000_000,
            "gradient_norm": 0.5 + gradient_delta,
            "mps_current_allocated_bytes": None,
            "mps_driver_allocated_bytes": None,
        }
        for step in range(1, 169)
    ]
