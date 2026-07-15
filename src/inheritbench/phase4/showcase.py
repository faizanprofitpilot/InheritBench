"""Deterministic Phase 4 showcase bundle, replay, and final decision."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_bytes
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.phase4.config import load_experiment_config, resolve
from inheritbench.phase4.memo import render_markdown, validate_memo_value
from inheritbench.phase4.protocol import find_protocol, runtime_lineage
from inheritbench.phase4.schemas import (
    Phase4AnalysisV0_1,
    Phase4CaseSelectionV0_1,
    Phase4DecisionV0_1,
    Phase4EvidencePackV0_1,
    Phase4MemoAttemptV0_1,
    Phase4MemoV0_1,
    Phase4MemoValidationV0_1,
    Phase4MigrationAnalysisV0_1,
    Phase4ShowcaseManifestV0_1,
    Phase4ShowcaseReplayV0_1,
    ShowcaseFileV0_1,
)

_DECISION_EXCLUSIONS = {"decision_id", "created_at", "content_sha256"}
_MANIFEST_EXCLUSIONS = {"created_at", "content_sha256"}
_REPLAY_EXCLUSIONS = {"replay_id", "created_at", "content_sha256"}
_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


def build_showcase(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    showcase_root = resolve(experiment_path, experiment.showcase_root)
    if showcase_root.exists():
        raise FileExistsError(f"showcase already exists: {showcase_root}")
    protocol_path, protocol = find_protocol(experiment_path)
    analysis_path, analysis = _single(
        artifact_root / "analysis", "analysis.json", Phase4AnalysisV0_1
    )
    profiles_path, profiles = _single(
        artifact_root / "migration-profiles", "profiles.json", Phase4MigrationAnalysisV0_1
    )
    cases_path, cases = _single(
        artifact_root / "representative-cases", "cases.json", Phase4CaseSelectionV0_1
    )
    evidence_path, evidence = _single(
        artifact_root / "evidence-packs", "evidence.json", Phase4EvidencePackV0_1
    )
    memo_path, memo, validation_path, validation = _selected_validated_memo(artifact_root)
    decision = _decision_candidate(experiment_path, memo, validation, evidence)
    provenance = {
        "schema_version": "phase4-showcase-provenance-v0.1",
        "source_repository": "faizanprofitpilot/InheritBench",
        "phase4_protocol_commit": decision.lineage.phase4_protocol_commit,
        "protocol_sha256": protocol.content_sha256,
        "analysis_sha256": analysis.content_sha256,
        "migration_profiles_sha256": profiles.content_sha256,
        "case_selection_sha256": cases.content_sha256,
        "evidence_pack_sha256": evidence.content_sha256,
        "memo_sha256": memo.content_sha256,
        "memo_validation_sha256": validation.content_sha256,
        "automatic_phase5": False,
    }
    files = {
        "provenance.json": canonical_json_bytes(provenance) + b"\n",
        "protocol.json": protocol_path.read_bytes(),
        "system-summaries.json": canonical_json_bytes(
            [item.model_dump(mode="json") for item in profiles.rows]
        )
        + b"\n",
        "analysis.json": analysis_path.read_bytes(),
        "failure-matrix.jsonl": (analysis_path.parent / "failure_matrix.jsonl").read_bytes(),
        "archetype-matrix.jsonl": (analysis_path.parent / "archetype_matrix.jsonl").read_bytes(),
        "migration-profiles.json": profiles_path.read_bytes(),
        "representative-cases.json": cases_path.read_bytes(),
        "evidence.json": evidence_path.read_bytes(),
        "memo.json": memo_path.read_bytes(),
        "memo.md": (memo_path.parent / "memo.md").read_bytes(),
        "memo-validation.json": validation_path.read_bytes(),
        "phase4-decision.json": canonical_json_bytes(decision) + b"\n",
    }
    entries = [
        ShowcaseFileV0_1(relative_path=name, byte_sha256=sha256_bytes(payload), bytes=len(payload))
        for name, payload in sorted(files.items())
    ]
    manifest_payload = {
        "schema_version": "phase4-showcase-manifest-v0.1",
        "showcase_id": "inheritbench-v0.1",
        "status": "BUILT",
        "files": [item.model_dump(mode="json") for item in entries],
        "decision_content_sha256": decision.content_sha256,
        "created_at": memo.generated_at,
    }
    manifest = Phase4ShowcaseManifestV0_1.model_validate(
        {
            **manifest_payload,
            "content_sha256": content_sha256(manifest_payload, excluded_keys=_MANIFEST_EXCLUSIONS),
        },
        strict=True,
    )
    files["manifest.json"] = canonical_json_bytes(manifest) + b"\n"
    return write_atomic_bundle(showcase_root.parent, showcase_root.name, files)


def replay_showcase(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    showcase_root = resolve(experiment_path, experiment.showcase_root)
    manifest = Phase4ShowcaseManifestV0_1.model_validate_json(
        (showcase_root / "manifest.json").read_bytes(), strict=True
    )
    for item in manifest.files:
        path = showcase_root / item.relative_path
        if not path.is_file() or path.stat().st_size != item.bytes:
            raise ValueError(f"showcase file is missing or resized: {item.relative_path}")
        if sha256_bytes(path.read_bytes()) != item.byte_sha256:
            raise ValueError(f"showcase file hash mismatch: {item.relative_path}")
    memo = Phase4MemoV0_1.model_validate_json(
        (showcase_root / "memo.json").read_bytes(), strict=True
    )
    evidence = Phase4EvidencePackV0_1.model_validate_json(
        (showcase_root / "evidence.json").read_bytes(), strict=True
    )
    profiles = Phase4MigrationAnalysisV0_1.model_validate_json(
        (showcase_root / "migration-profiles.json").read_bytes(), strict=True
    )
    markdown = render_markdown(memo, evidence)
    if markdown != (showcase_root / "memo.md").read_text(encoding="utf-8"):
        raise ValueError("showcase memo Markdown replay mismatch")
    if any(validate_memo_value(memo, evidence, profiles, markdown).values()):
        raise ValueError("showcase memo no longer validates against its evidence")
    decision = Phase4DecisionV0_1.model_validate_json(
        (showcase_root / "phase4-decision.json").read_bytes(), strict=True
    )
    if decision.content_sha256 != manifest.decision_content_sha256:
        raise ValueError("showcase decision differs from its manifest")
    actual_manifest = content_sha256(
        manifest.model_dump(mode="json"), excluded_keys=_MANIFEST_EXCLUSIONS
    )
    if actual_manifest != manifest.content_sha256:
        raise ValueError("showcase manifest content hash mismatch")
    created_at = datetime.now(UTC)
    replay_id = f"phase4-showcase-replay-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "phase4-showcase-replay-v0.1",
        "replay_id": replay_id,
        "status": "PASSED",
        "manifest_sha256": manifest.content_sha256,
        "file_hashes_verified": True,
        "derived_content_verified": True,
        "network_required": False,
        "model_required": False,
        "accelerator_required": False,
        "created_at": created_at,
    }
    replay = Phase4ShowcaseReplayV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_REPLAY_EXCLUSIONS)},
        strict=True,
    )
    return write_atomic_bundle(
        artifact_root / "showcase-replays",
        replay_id,
        {"verification.json": canonical_json_bytes(replay) + b"\n"},
    )


def finalize(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    showcase_root = resolve(experiment_path, experiment.showcase_root)
    if list((artifact_root / "decisions").glob("*/decision.json")):
        raise ValueError("Phase 4 final decision already exists")
    replays = sorted((artifact_root / "showcase-replays").glob("*/verification.json"))
    if len(replays) != 1:
        raise ValueError("Phase 4 finalization requires one showcase replay")
    replay = Phase4ShowcaseReplayV0_1.model_validate_json(replays[0].read_bytes(), strict=True)
    if replay.status != "PASSED":
        raise ValueError("Phase 4 showcase replay did not pass")
    decision = Phase4DecisionV0_1.model_validate_json(
        (showcase_root / "phase4-decision.json").read_bytes(), strict=True
    )
    _, evidence = _single(artifact_root / "evidence-packs", "evidence.json", Phase4EvidencePackV0_1)
    memo_path, memo, _, validation = _selected_validated_memo(artifact_root)
    del memo_path
    expected = _decision_candidate(experiment_path, memo, validation, evidence)
    if expected != decision:
        raise ValueError("Phase 4 final decision differs from the replayed showcase")
    return write_atomic_bundle(
        artifact_root / "decisions",
        decision.decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def _decision_candidate(
    experiment_path: Path,
    memo: Phase4MemoV0_1,
    validation: Phase4MemoValidationV0_1,
    evidence: Phase4EvidencePackV0_1,
) -> Phase4DecisionV0_1:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    attempts = [
        Phase4MemoAttemptV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "memo-attempts").glob("*/attempt.json"))
    ]
    if validation.status != "PASSED":
        status = "PHASE4_BLOCKED"
        gate = "DAY5_BLOCKED"
        reason = "MEMO_VALIDATION_FAILED"
    elif memo.memo_kind == "GPT_5_6_SOL":
        status = "PHASE4_COMPLETED_WITH_VALIDATED_GPT_MEMO"
        gate = "DAY5_UNBLOCKED"
        reason = "VALIDATED_GPT_5_6_SOL_MEMO"
    elif any(
        item.attempt_number == 2 and item.status in {"PROVIDER_FAILURE", "INVALID_RESPONSE"}
        for item in attempts
    ):
        status = "PHASE4_COMPLETED_WITH_DETERMINISTIC_FALLBACK"
        gate = "DAY5_UNBLOCKED_WITH_API_FAILURE"
        reason = "BOUNDED_GPT_API_FAILURE"
    else:
        status = "READY_FOR_GPT_MEMO"
        gate = "DAY5_BLOCKED_PENDING_GPT_MEMO"
        reason = "OPENAI_CREDENTIALS_REQUIRED"
    created_at = validation.created_at
    payload = {
        "schema_version": "phase4-decision-v0.1",
        "decision_id": "pending",
        "phase4_status": status,
        "day5_gate": gate,
        "reason_code": reason,
        "memo_kind": memo.memo_kind,
        "memo_validation_sha256": validation.content_sha256,
        "evidence_pack_sha256": evidence.content_sha256,
        "showcase_manifest_sha256": None,
        "automatic_phase5": False,
        "repeated_seeds": False,
        "phase4_release": False,
        "lineage": runtime_lineage(experiment_path),
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_DECISION_EXCLUSIONS)
    return Phase4DecisionV0_1.model_validate(
        {
            **payload,
            "decision_id": f"phase4-decision-{identity[:16]}",
            "content_sha256": identity,
        },
        strict=True,
    )


def _selected_validated_memo(
    root: Path,
) -> tuple[Path, Phase4MemoV0_1, Path, Phase4MemoValidationV0_1]:
    memo_paths = sorted((root / "memos/gpt").glob("*/memo.json"))
    if not memo_paths:
        memo_paths = sorted((root / "memos/fallback").glob("*/memo.json"))
    if len(memo_paths) != 1:
        raise ValueError("expected one selected Phase 4 memo")
    memo = Phase4MemoV0_1.model_validate_json(memo_paths[0].read_bytes(), strict=True)
    validations = []
    for path in sorted((root / "memo-validations").glob("*/validation.json")):
        value = Phase4MemoValidationV0_1.model_validate_json(path.read_bytes(), strict=True)
        if value.memo_sha256 == memo.content_sha256 and value.status == "PASSED":
            validations.append((path, value))
    if len(validations) != 1:
        raise ValueError("selected Phase 4 memo requires exactly one passing validation")
    return memo_paths[0], memo, validations[0][0], validations[0][1]


def _single(root: Path, filename: str, schema: type[_SchemaT]) -> tuple[Path, _SchemaT]:
    matches = sorted(root.glob(f"*/{filename}"))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {filename}")
    return matches[0], schema.model_validate_json(matches[0].read_bytes(), strict=True)
