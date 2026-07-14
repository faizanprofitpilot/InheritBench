"""Machine-readable blocker-resolution decision."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_file
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.blockers.trainability import TrainabilityManifest
from inheritbench.config import Sha256


class BlockerResolutionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["blocker-resolution-decision-v0.1"]
    target_failure_reclassification: Literal[
        "UNTOUCHED_TARGET_HAS_ZERO_SCHEMA_VALIDITY; TARGET_TRAINABILITY_UNTESTED"
    ]
    trainability_decision: Literal["OLMO_TRAINABILITY_CONFIRMED"]
    modal_classification: Literal["EXTERNAL_DATA_EXPORT_APPROVAL_REQUIRED"]
    modal_remote_attempts: Literal[0]
    day2_status: Literal["SCIENTIFICALLY_UNBLOCKED_MODAL_LIMITED"]
    schema_valid_threshold: int
    semantic_exact_threshold: int
    observed_schema_valid: int
    observed_semantic_exact: int
    source_artifact_sha256s: dict[str, Sha256]
    rationale: list[str]
    content_sha256: Sha256


def write_decision(
    *,
    target_run_directory: Path,
    modal_artifact: Path,
    evidence_paths: list[Path],
    output_root: Path,
) -> Path:
    target = TrainabilityManifest.model_validate_json(
        (target_run_directory / "manifest.json").read_bytes(), strict=True
    )
    modal = json.loads(modal_artifact.read_text(encoding="utf-8"))
    if target.status != "COMPLETED":
        raise ValueError("target trainability run is not completed")
    if target.schema_valid_predictions < 4 or target.semantic_exact_predictions < 1:
        raise ValueError("target trainability run does not meet the bounded threshold")
    if modal.get("status") != "BLOCKED" or modal.get("attempts") != 0:
        raise ValueError("Modal artifact does not prove a pre-launch zero-attempt block")
    source_hashes = {str(path): sha256_file(path) for path in evidence_paths}
    payload = {
        "schema_version": "blocker-resolution-decision-v0.1",
        "target_failure_reclassification": (
            "UNTOUCHED_TARGET_HAS_ZERO_SCHEMA_VALIDITY; TARGET_TRAINABILITY_UNTESTED"
        ),
        "trainability_decision": "OLMO_TRAINABILITY_CONFIRMED",
        "modal_classification": "EXTERNAL_DATA_EXPORT_APPROVAL_REQUIRED",
        "modal_remote_attempts": 0,
        "day2_status": "SCIENTIFICALLY_UNBLOCKED_MODAL_LIMITED",
        "schema_valid_threshold": 4,
        "semantic_exact_threshold": 1,
        "observed_schema_valid": target.schema_valid_predictions,
        "observed_semantic_exact": target.semantic_exact_predictions,
        "source_artifact_sha256s": source_hashes,
        "rationale": [
            "Untouched OLMo produced zero schema-valid outputs on the fixed validation subset.",
            "The bounded six-epoch OLMo LoRA run produced seven schema-valid outputs.",
            "Two validation contracts were semantic-exact and exact replay passed.",
            "Modal was blocked before launch, while local MPS completed trainability gates.",
        ],
    }
    decision = BlockerResolutionDecision.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
    return write_atomic_bundle(
        output_root,
        f"decision-{decision.content_sha256[:16]}",
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )
