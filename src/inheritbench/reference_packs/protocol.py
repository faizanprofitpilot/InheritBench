"""Prospective protocol amendment for seeded reference succession runs."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_file,
)
from inheritbench.artifacts.store import write_atomic_file
from inheritbench.capability.loader import load_capability_pack
from inheritbench.reference_packs.integrity import (
    REPOSITORY_ROOT,
    verify_frozen_root_manifest,
)

AMENDMENT_ID = "seeded-reference-succession-v0.1"
REFERENCE_RUN_ID = "succession-opsroute-direct-target-lora-v0.1-200d8ad795f4bb0f"
REFERENCE_RUN = REPOSITORY_ROOT / "runs/parity" / REFERENCE_RUN_ID
PACK_ROOT = REPOSITORY_ROOT / "capabilities/opsroute/v0.2.0"
DOCUMENT_PATH = REPOSITORY_ROOT / "docs/PROTOCOL_AMENDMENT_SEEDED_REFERENCE_SUCCESSION.md"
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT / "artifacts/protocol-amendments/seeded-reference-succession-v0.1.json"
)
CORRECTION_ID = "seeded-reference-succession-v0.1-implementation-correction"
CORRECTION_DOCUMENT_PATH = (
    REPOSITORY_ROOT / "docs/PROTOCOL_IMPLEMENTATION_CORRECTION_SEEDED_REFERENCE.md"
)
DEFAULT_CORRECTION_OUTPUT = REPOSITORY_ROOT / (
    "artifacts/protocol-amendments/seeded-reference-succession-v0.1-implementation-correction.json"
)


def freeze_seeded_reference_amendment(output: Path = DEFAULT_OUTPUT) -> Path:
    if output.exists():
        verify_seeded_reference_amendment(output)
        return output
    historical = verify_frozen_root_manifest()
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    direct_schedule = PACK_ROOT / "schedules/direct-reference.json"
    anchored_schedule = PACK_ROOT / "schedules/anchored-reference.json"
    teacher = PACK_ROOT / "supervision/frozen_teacher_outputs.jsonl"
    anchors = PACK_ROOT / "anchors/available.jsonl"
    readiness = PACK_ROOT / "rules/readiness.yaml"
    diagnosis = _json(REFERENCE_RUN / "direct_parity_diagnosis.json")
    payload: dict[str, Any] = {
        "schema_version": "inheritbench.seeded-reference-amendment.v0.1",
        "amendment_id": AMENDMENT_ID,
        "status": "PROSPECTIVE_FROZEN",
        "reason": "HISTORICAL_UNSEEDED_ADAPTER_INITIALIZATION_NOT_RECONSTRUCTIBLE",
        "preserved_failed_gate": True,
        "historical_result_mutated": False,
        "readiness_thresholds_changed": False,
        "evaluation_surfaces_changed": False,
        "supervision_changed": False,
        "training_budget_changed": False,
        "new_direct_gate": "SEEDED_PROTOCOL_SELF_REPRODUCTION",
        "anchored_primary_gate": "FROZEN_READINESS_CONTRACT",
        "historical_behavioral_parity": "SECONDARY_COMPARISON",
        "telemetry_tolerance": {
            "loss_absolute": 1e-6,
            "loss_relative": 1e-5,
            "gradient_norm_absolute": 1e-6,
            "gradient_norm_relative": 1e-5,
            "learning_rate": "EXACT",
        },
        "previous_failed_run_id": REFERENCE_RUN_ID,
        "previous_failed_plan_byte_sha256": sha256_file(REFERENCE_RUN / "plan.json"),
        "previous_failed_decision_byte_sha256": sha256_file(
            REFERENCE_RUN / "direct_parity_report.json"
        ),
        "diagnosis_artifact_sha256": diagnosis["content_sha256"],
        "direct_schedule_sha256": sha256_file(direct_schedule),
        "anchored_schedule_sha256": sha256_file(anchored_schedule),
        "pack_validation_sha256": pack.validation.content_sha256,
        "readiness_contract_sha256": sha256_file(readiness),
        "confirmatory_surface_sha256": _surface_sha256("confirmatory"),
        "adversarial_surface_sha256": _surface_sha256("adversarial"),
        "teacher_artifact_sha256": sha256_file(teacher),
        "authorized_anchor_pool_sha256": sha256_file(anchors),
        "authorized_anchor_pool_records": _line_count(anchors),
        "document_sha256": sha256_file(DOCUMENT_PATH),
        "historical_evidence_sha256": historical["content_sha256"],
        "opsroute_regeneration_sha256": (
            "9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b"
        ),
        "repository_head": _git("rev-parse", "HEAD"),
        "repository_branch": _git("branch", "--show-current"),
        "dirty_worktree_sha256": _dirty_worktree_sha256(output),
        "git_preregistered": False,
        "platform": platform.platform(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    payload["amendment_sha256"] = content_sha256(payload)
    write_atomic_file(output, canonical_json_bytes(payload) + b"\n")
    verify_seeded_reference_amendment(output)
    return output


def verify_seeded_reference_amendment(path: Path) -> dict[str, Any]:
    payload = _json(path)
    stored = payload.get("amendment_sha256")
    if not isinstance(stored, str):
        raise ValueError("protocol amendment lacks amendment_sha256")
    unsigned = dict(payload)
    unsigned.pop("amendment_sha256")
    if content_sha256(unsigned) != stored:
        raise ValueError("protocol amendment content hash mismatch")
    if payload.get("amendment_id") != AMENDMENT_ID:
        raise ValueError("unexpected seeded-reference amendment ID")
    if payload.get("status") != "PROSPECTIVE_FROZEN":
        raise ValueError("seeded-reference amendment is not frozen")
    if payload.get("git_preregistered") is not False:
        raise ValueError("uncommitted amendment cannot claim Git preregistration")
    return payload


def freeze_seeded_reference_implementation_correction(
    output: Path = DEFAULT_CORRECTION_OUTPUT,
    *,
    parent_amendment: Path = DEFAULT_OUTPUT,
) -> Path:
    if output.exists():
        verify_seeded_reference_implementation_correction(output)
        return output
    parent = verify_seeded_reference_amendment(parent_amendment)
    failed_stage = REPOSITORY_ROOT / (
        "runs/reproducibility/"
        "succession-opsroute-direct-target-lora-v0.1-01-ce164572f906c70e/"
        "stages/07-execution_failed/stage.json"
    )
    payload: dict[str, Any] = {
        "schema_version": ("inheritbench.seeded-reference-implementation-correction.v0.1"),
        "amendment_id": CORRECTION_ID,
        "status": "PROSPECTIVE_FROZEN",
        "parent_amendment_sha256": parent["amendment_sha256"],
        "parent_amendment_byte_sha256": sha256_file(parent_amendment),
        "preserved_failed_execution_id": (
            "succession-opsroute-direct-target-lora-v0.1-01-ce164572f906c70e"
        ),
        "preserved_failed_stage_sha256": sha256_file(failed_stage),
        "correction_code": "UNSTABLE_PICKLE_RNG_HASH_FALSE_EQUALITY_GATE_REMOVED",
        "training_semantics_changed": False,
        "supervision_changed": False,
        "schedule_changed": False,
        "optimizer_changed": False,
        "evaluation_changed": False,
        "readiness_changed": False,
        "exact_initialization_fields": [
            "seed",
            "initial_adapter_sha256",
            "trainable_parameter_names",
            "trainable_parameter_shapes",
            "trainable_parameters",
        ],
        "observational_rng_fields": [
            "rng_before_model_load_sha256",
            "rng_before_lora_sha256",
            "rng_after_lora_sha256",
        ],
        "telemetry_tolerance": parent["telemetry_tolerance"],
        "direct_schedule_sha256": parent["direct_schedule_sha256"],
        "anchored_schedule_sha256": parent["anchored_schedule_sha256"],
        "teacher_artifact_sha256": parent["teacher_artifact_sha256"],
        "authorized_anchor_pool_sha256": parent["authorized_anchor_pool_sha256"],
        "readiness_contract_sha256": parent["readiness_contract_sha256"],
        "confirmatory_surface_sha256": parent["confirmatory_surface_sha256"],
        "adversarial_surface_sha256": parent["adversarial_surface_sha256"],
        "document_sha256": sha256_file(CORRECTION_DOCUMENT_PATH),
        "repository_head": _git("rev-parse", "HEAD"),
        "dirty_worktree_sha256": _dirty_worktree_sha256(output),
        "git_preregistered": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    payload["amendment_sha256"] = content_sha256(payload)
    write_atomic_file(output, canonical_json_bytes(payload) + b"\n")
    verify_seeded_reference_implementation_correction(output)
    return output


def verify_seeded_reference_implementation_correction(path: Path) -> dict[str, Any]:
    payload = _json(path)
    stored = payload.get("amendment_sha256")
    unsigned = dict(payload)
    unsigned.pop("amendment_sha256", None)
    if not isinstance(stored, str) or content_sha256(unsigned) != stored:
        raise ValueError("implementation correction content hash mismatch")
    if payload.get("amendment_id") != CORRECTION_ID:
        raise ValueError("unexpected seeded-reference correction ID")
    if payload.get("status") != "PROSPECTIVE_FROZEN":
        raise ValueError("seeded-reference correction is not frozen")
    if payload.get("training_semantics_changed") is not False:
        raise ValueError("implementation correction changed training semantics")
    if payload.get("git_preregistered") is not False:
        raise ValueError("uncommitted correction cannot claim Git preregistration")
    return payload


def _surface_sha256(surface: str) -> str:
    return content_sha256(
        {
            "inputs": sha256_file(PACK_ROOT / f"data/{surface}.inputs.jsonl"),
            "oracles": sha256_file(PACK_ROOT / f"oracles/{surface}.jsonl"),
        }
    )


def _dirty_worktree_sha256(output: Path) -> str:
    result = subprocess.run(
        ["git", "ls-files", "-m", "-o", "--exclude-standard"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[dict[str, Any]] = []
    for relative in sorted(line for line in result.stdout.splitlines() if line):
        path = REPOSITORY_ROOT / relative
        if path.resolve() == output.resolve() or not path.is_file():
            continue
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return content_sha256(files)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _line_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value
