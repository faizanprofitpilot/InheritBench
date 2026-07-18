"""Prospectively frozen bounded multi-start recovery protocol."""

from __future__ import annotations

import hashlib
import json
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
from inheritbench.reference_packs.integrity import REPOSITORY_ROOT

AMENDMENT_ID = "bounded-multistart-recovery-v0.1"
SEED_MANIFEST_ID = "bounded-multistart-seeds-v0.1"
CANONICAL_ANCHORED_PLAN_SHA256 = "2daa24b506b5ae8ff31bb9356498f2ab32626aabaffefe63edc1eea18fcc5111"
BASELINE_PATH = REPOSITORY_ROOT / "runs/audits/bounded-multistart-baseline/baseline.json"
CROSSWALK_PATH = (
    REPOSITORY_ROOT / "runs/audits/metric-identity-crosswalk/metric_identity_crosswalk.json"
)
DOCUMENT_PATH = REPOSITORY_ROOT / "docs/PROTOCOL_AMENDMENT_BOUNDED_MULTISTART_RECOVERY.md"
PARENT_AMENDMENT_PATH = (
    REPOSITORY_ROOT / "artifacts/protocol-amendments/"
    "seeded-reference-succession-v0.1-implementation-correction.json"
)
DEFAULT_AMENDMENT_PATH = (
    REPOSITORY_ROOT / "artifacts/protocol-amendments/bounded-multistart-recovery-v0.1.json"
)
DEFAULT_SEED_PATH = (
    REPOSITORY_ROOT / "artifacts/protocol-amendments/bounded-multistart-seeds-v0.1.json"
)

PROSPECTIVE_STATEMENT = (
    "Full supervision and executable training-stream parity has been confirmed "
    "between the historical and generic anchored workflows. The remaining "
    "behavioral difference is attributable to initialization and optimization "
    "trajectory. This amendment prospectively evaluates a bounded set of four "
    "deterministic LoRA initialization seeds. All candidates use identical "
    "supervision, schedule, token budget, optimizer, checkpoints, and validation "
    "rules. Candidate selection occurs only on the authorized recovery-validation "
    "surface. A newly frozen final confirmatory and adversarial surface is evaluated "
    "only after one candidate has been selected and frozen."
)

CANDIDATE_RANKING = [
    "validation_safety_eligibility",
    "validation_operational_semantic_correctness",
    "validation_minimum_group_operational_semantic_rate",
    "validation_historical_strict_validity_count",
    "validation_mean_declared_field_correctness",
    "validation_loss_ascending",
    "selected_optimizer_step_ascending",
    "candidate_index_ascending",
]


def freeze_bounded_multistart_amendment(
    output: Path = DEFAULT_AMENDMENT_PATH,
) -> Path:
    if output.exists():
        verify_bounded_multistart_amendment(output)
        return output
    baseline = _json(BASELINE_PATH)
    crosswalk = _json(CROSSWALK_PATH)
    parent = _json(PARENT_AMENDMENT_PATH)
    if crosswalk.get("status") != "METRIC_IDENTITY_RESOLVED":
        raise ValueError("metric identity must be resolved before protocol freeze")
    references = baseline["references"]
    payload: dict[str, Any] = {
        "schema_version": "inheritbench.bounded-multistart-amendment.v0.1",
        "amendment_id": AMENDMENT_ID,
        "status": "PROSPECTIVE_CONTENT_FROZEN",
        "git_preregistered": False,
        "reason": "INITIALIZATION_SENSITIVITY_AFTER_FULL_TRAINING_STREAM_PARITY",
        "prospective_statement": PROSPECTIVE_STATEMENT,
        "candidate_count": 4,
        "candidate_indices": [0, 1, 2, 3],
        "only_varied_dimension": "lora_initialization_seed",
        "candidate_selection_surface": "recovery_validation_only",
        "candidate_ranking": CANDIDATE_RANKING,
        "operational_semantic_definition": [
            "decision",
            "tool",
            "arguments",
            "approval_required",
            "reason_code",
        ],
        "policy_code_excluded_from_operational_semantic": True,
        "new_final_surfaces_required": True,
        "old_confirmatory_used_for_selection": False,
        "old_adversarial_used_for_selection": False,
        "readiness_thresholds_changed": False,
        "supervision_changed": False,
        "schedule_changed": False,
        "training_budget_changed": False,
        "target_processed_tokens": 272568,
        "optimizer_steps": 168,
        "checkpoint_steps": [56, 112, 168],
        "canonical_anchored_plan_sha256": CANONICAL_ANCHORED_PLAN_SHA256,
        "repository_head": baseline["repository"]["head"],
        "repository_branch": baseline["repository"]["branch"],
        "baseline_dirty_worktree_sha256": baseline["repository"]["dirty_worktree_sha256"],
        "baseline_sha256": baseline["content_sha256"],
        "parent_seeded_amendment_sha256": parent["amendment_sha256"],
        "parent_seeded_amendment_byte_sha256": sha256_file(PARENT_AMENDMENT_PATH),
        "metric_crosswalk_sha256": crosswalk["content_sha256"],
        "metric_crosswalk_byte_sha256": sha256_file(CROSSWALK_PATH),
        "capability_pack_root_sha256": references["capability_pack"]["root_sha256"],
        "supervision_manifest_sha256": references["supervision_manifest"]["sha256"],
        "anchored_schedule_sha256": references["anchored_schedule"]["sha256"],
        "recovery_validation_inputs_sha256": references["recovery_validation"]["inputs_sha256"],
        "recovery_validation_oracles_sha256": references["recovery_validation"]["oracles_sha256"],
        "readiness_contract_sha256": references["readiness_contract"]["sha256"],
        "historical_evidence_sha256": references["historical_evidence_manifest"]["content_sha256"],
        "supervision_identity_audit_sha256": references["supervision_identity_audit"][
            "root_sha256"
        ],
        "document_sha256": sha256_file(DOCUMENT_PATH),
        "seed_derivation": {
            "algorithm": "SHA-256",
            "canonical_bytes": [
                "bytes.fromhex(amendment_sha256)",
                "bytes.fromhex(canonical_anchored_plan_sha256)",
                'UTF8("anchored-multistart-candidate")',
                "uint32_big_endian(candidate_index)",
            ],
            "result": "unsigned_big_endian(first_4_digest_bytes)",
        },
        "created_at": datetime.now(UTC).isoformat(),
    }
    payload["content_sha256"] = content_sha256(payload)
    write_atomic_file(output, canonical_json_bytes(payload) + b"\n")
    verify_bounded_multistart_amendment(output)
    return output


def verify_bounded_multistart_amendment(path: Path = DEFAULT_AMENDMENT_PATH) -> dict[str, Any]:
    payload = _json(path)
    stored = payload.get("content_sha256")
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    if not isinstance(stored, str) or content_sha256(unsigned) != stored:
        raise ValueError("bounded multi-start amendment content hash mismatch")
    if payload.get("amendment_id") != AMENDMENT_ID:
        raise ValueError("unexpected bounded multi-start amendment ID")
    if payload.get("status") != "PROSPECTIVE_CONTENT_FROZEN":
        raise ValueError("bounded multi-start amendment is not content-frozen")
    if payload.get("git_preregistered") is not False:
        raise ValueError("dirty-worktree protocol cannot claim Git preregistration")
    if payload.get("candidate_ranking") != CANDIDATE_RANKING:
        raise ValueError("candidate-ranking policy drift")
    if payload.get("document_sha256") != sha256_file(DOCUMENT_PATH):
        raise ValueError("bounded multi-start protocol document changed after freeze")
    baseline = _json(BASELINE_PATH)
    if payload.get("baseline_sha256") != baseline.get("content_sha256"):
        raise ValueError("bounded multi-start baseline binding mismatch")
    return payload


def freeze_bounded_multistart_seeds(
    output: Path = DEFAULT_SEED_PATH,
    *,
    amendment_path: Path = DEFAULT_AMENDMENT_PATH,
) -> Path:
    if output.exists():
        verify_bounded_multistart_seeds(output, amendment_path=amendment_path)
        return output
    amendment = verify_bounded_multistart_amendment(amendment_path)
    seeds = [
        {
            "candidate_index": index,
            "initialization_seed": derive_candidate_seed(
                amendment["content_sha256"],
                CANONICAL_ANCHORED_PLAN_SHA256,
                index,
            ),
        }
        for index in range(4)
    ]
    if len({item["initialization_seed"] for item in seeds}) != 4:
        raise ValueError("bounded multi-start seed derivation produced a collision")
    payload: dict[str, Any] = {
        "schema_version": "inheritbench.bounded-multistart-seeds.v0.1",
        "seed_manifest_id": SEED_MANIFEST_ID,
        "status": "PROSPECTIVE_CONTENT_FROZEN",
        "amendment_sha256": amendment["content_sha256"],
        "amendment_byte_sha256": sha256_file(amendment_path),
        "canonical_anchored_plan_sha256": CANONICAL_ANCHORED_PLAN_SHA256,
        "derivation": amendment["seed_derivation"],
        "candidates": seeds,
        "created_before_candidate_training": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    payload["seed_list_sha256"] = content_sha256(seeds)
    payload["content_sha256"] = content_sha256(payload)
    write_atomic_file(output, canonical_json_bytes(payload) + b"\n")
    verify_bounded_multistart_seeds(output, amendment_path=amendment_path)
    return output


def verify_bounded_multistart_seeds(
    path: Path = DEFAULT_SEED_PATH,
    *,
    amendment_path: Path = DEFAULT_AMENDMENT_PATH,
) -> dict[str, Any]:
    amendment = verify_bounded_multistart_amendment(amendment_path)
    payload = _json(path)
    stored = payload.get("content_sha256")
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    if not isinstance(stored, str) or content_sha256(unsigned) != stored:
        raise ValueError("bounded multi-start seed manifest content hash mismatch")
    if payload.get("seed_manifest_id") != SEED_MANIFEST_ID:
        raise ValueError("unexpected bounded multi-start seed manifest ID")
    expected = [
        {
            "candidate_index": index,
            "initialization_seed": derive_candidate_seed(
                amendment["content_sha256"],
                CANONICAL_ANCHORED_PLAN_SHA256,
                index,
            ),
        }
        for index in range(4)
    ]
    if payload.get("candidates") != expected:
        raise ValueError("bounded multi-start candidate seeds do not replay")
    if payload.get("seed_list_sha256") != content_sha256(expected):
        raise ValueError("bounded multi-start seed-list hash mismatch")
    return payload


def derive_candidate_seed(
    amendment_sha256: str,
    canonical_plan_sha256: str,
    candidate_index: int,
) -> int:
    if candidate_index not in range(4):
        raise ValueError("candidate index must be 0, 1, 2, or 3")
    material = b"".join(
        [
            bytes.fromhex(amendment_sha256),
            bytes.fromhex(canonical_plan_sha256),
            b"anchored-multistart-candidate",
            candidate_index.to_bytes(4, byteorder="big", signed=False),
        ]
    )
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big", signed=False)


def current_git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value
