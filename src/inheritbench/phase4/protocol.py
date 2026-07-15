"""Phase 4 protocol freeze, Git-tree attestation, and runtime lineage."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_file,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2.evaluation import adapter_reference, verify_adapter
from inheritbench.phase4.config import (
    config_sha256,
    load_adversarial_config,
    load_experiment_config,
    load_memo_config,
    repository_root,
    resolve,
)
from inheritbench.phase4.schemas import (
    Phase4LineageV0_1,
    Phase4ProtocolAttestationV0_1,
    Phase4ProtocolV0_1,
)

_PROTOCOL_EXCLUSIONS = {"protocol_id", "created_at", "content_sha256"}
_ATTESTATION_EXCLUSIONS = {"attestation_id", "created_at", "content_sha256"}


def freeze_protocol(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = repository_root(experiment_path)
    output = resolve(experiment_path, experiment.artifact_root) / "protocols"
    if list(output.glob("*/protocol.json")):
        raise ValueError("Phase 4 protocol is already frozen")
    for expectation in experiment.historical_artifacts:
        path = root / expectation.relative_path
        if not path.is_file() or sha256_file(path) != expectation.byte_sha256:
            raise ValueError(f"historical artifact hash mismatch: {path}")
        if expectation.content_sha256 is not None:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("content_sha256") != expectation.content_sha256:
                raise ValueError(f"historical content hash mismatch: {path}")
    adversarial = load_adversarial_config(
        resolve(experiment_path, experiment.adversarial_config_path)
    )
    memo = load_memo_config(resolve(experiment_path, experiment.memo_config_path))
    rows = _adversarial_rows(resolve(experiment_path, experiment.dataset_directory))
    _verify_adversarial(rows, resolve(experiment_path, experiment.dataset_directory), adversarial)
    systems = []
    for system in experiment.systems:
        model = load_model_config(resolve(experiment_path, system.model_config_path))
        adapter = None
        if system.adapter_path is not None:
            adapter_path = resolve(experiment_path, system.adapter_path)
            adapter_model_sha256 = sha256_file(adapter_path / "adapter_model.safetensors")
            if adapter_model_sha256 != system.adapter_model_sha256:
                raise ValueError(f"adapter model hash mismatch: {system.system_id}")
            adapter = adapter_reference(adapter_path, adapter_path.parent)
            verify_adapter(adapter, root)
            adapter = adapter.model_copy(
                update={"verified": True, "verified_at": datetime.now(UTC)}
            )
        systems.append(
            {
                "system_id": system.system_id,
                "model_id": model.model_id,
                "model_revision": model.revision,
                "adapter": adapter,
                "comparison_role": system.comparison_role,
                "direct_original_labels": system.direct_original_labels,
                "upstream_original_labels": system.upstream_original_labels,
                "complexity": system.complexity,
                "source_teacher_required": system.source_teacher_required,
            }
        )
    comparison = _json(resolve(experiment_path, experiment.phase3b_comparison_path))
    science = _json(resolve(experiment_path, experiment.phase3b_science_path))
    publication = _json(resolve(experiment_path, experiment.phase3b_publication_verification_path))
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase4-protocol-v0.1",
        "protocol_id": "pending",
        "status": "FROZEN",
        "historical_reference_commit": experiment.historical_reference_commit,
        "experiment_config_sha256": config_sha256(experiment),
        "adversarial_config_sha256": config_sha256(adversarial),
        "memo_config_sha256": config_sha256(memo),
        "adversarial_byte_sha256": adversarial.adversarial_byte_sha256,
        "adversarial_split_sha256": adversarial.adversarial_split_sha256,
        "adversarial_oracle_sha256": adversarial.adversarial_oracle_sha256,
        "adversarial_ids_sha256": adversarial.adversarial_ids_sha256,
        "phase3b_confirmatory_comparison_sha256": comparison["content_sha256"],
        "phase3b_science_sha256": science["content_sha256"],
        "phase3b_publication_verification_sha256": publication["content_sha256"],
        "systems": systems,
        "failure_precedence": adversarial.failure_precedence,
        "migration_profiles": adversarial.migration_profiles,
        "case_slots": adversarial.case_slots,
        "memo_model": memo.model,
        "repeated_seeds": False,
        "automatic_phase5": False,
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_PROTOCOL_EXCLUSIONS)
    protocol_id = f"phase4-protocol-{identity[:16]}"
    protocol = Phase4ProtocolV0_1.model_validate(
        {**payload, "protocol_id": protocol_id, "content_sha256": identity}, strict=True
    )
    return write_atomic_bundle(
        output,
        protocol_id,
        {"protocol.json": canonical_json_bytes(protocol) + b"\n"},
    )


def attest_protocol(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = repository_root(experiment_path)
    if _git(root, "status", "--porcelain"):
        raise ValueError("Phase 4 protocol attestation requires a clean worktree")
    commit = _git(root, "rev-parse", "HEAD")
    if commit == experiment.historical_reference_commit:
        raise ValueError("Phase 4 protocol commit must follow the historical reference commit")
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    if list((artifact_root / "evaluations").glob("*/manifest.json")):
        raise ValueError("Phase 4 protocol must be attested before adversarial inference")
    protocol_path, protocol = find_protocol(experiment_path)
    required = _required_protocol_paths(experiment_path, protocol_path)
    for path in required:
        relative = path.resolve().relative_to(root).as_posix()
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}:{relative}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if exists.returncode != 0:
            raise ValueError(f"required protocol path is not committed: {relative}")
        committed = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"working-tree bytes differ from protocol commit: {relative}")
    adversarial = load_adversarial_config(
        resolve(experiment_path, experiment.adversarial_config_path)
    )
    memo = load_memo_config(resolve(experiment_path, experiment.memo_config_path))
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase4-protocol-attestation-v0.1",
        "attestation_id": "pending",
        "phase4_protocol_commit": commit,
        "worktree_clean": True,
        "tracked_diff_sha256": None,
        "protocol_sha256": protocol.content_sha256,
        "experiment_config_sha256": config_sha256(experiment),
        "adversarial_config_sha256": config_sha256(adversarial),
        "memo_config_sha256": config_sha256(memo),
        "required_paths_in_commit": [
            path.resolve().relative_to(root).as_posix() for path in required
        ],
        "git_object_verification_passed": True,
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_ATTESTATION_EXCLUSIONS)
    attestation_id = f"phase4-attestation-{identity[:16]}"
    attestation = Phase4ProtocolAttestationV0_1.model_validate(
        {**payload, "attestation_id": attestation_id, "content_sha256": identity}, strict=True
    )
    return write_atomic_bundle(
        artifact_root / "attestations",
        attestation_id,
        {"attestation.json": canonical_json_bytes(attestation) + b"\n"},
    )


def find_protocol(experiment_path: Path) -> tuple[Path, Phase4ProtocolV0_1]:
    experiment = load_experiment_config(experiment_path)
    matches = sorted(
        (resolve(experiment_path, experiment.artifact_root) / "protocols").glob("*/protocol.json")
    )
    if len(matches) != 1:
        raise ValueError("expected exactly one frozen Phase 4 protocol")
    protocol = Phase4ProtocolV0_1.model_validate_json(matches[0].read_bytes(), strict=True)
    actual = content_sha256(protocol.model_dump(mode="json"), excluded_keys=_PROTOCOL_EXCLUSIONS)
    if actual != protocol.content_sha256:
        raise ValueError("Phase 4 protocol content hash mismatch")
    return matches[0], protocol


def load_attestation(
    experiment_path: Path,
) -> tuple[Path, Phase4ProtocolAttestationV0_1]:
    experiment = load_experiment_config(experiment_path)
    matches = sorted(
        (resolve(experiment_path, experiment.artifact_root) / "attestations").glob(
            "*/attestation.json"
        )
    )
    if len(matches) != 1:
        raise ValueError("expected exactly one Phase 4 protocol attestation")
    attestation = Phase4ProtocolAttestationV0_1.model_validate_json(
        matches[0].read_bytes(), strict=True
    )
    actual = content_sha256(
        attestation.model_dump(mode="json"), excluded_keys=_ATTESTATION_EXCLUSIONS
    )
    if actual != attestation.content_sha256:
        raise ValueError("Phase 4 protocol attestation content hash mismatch")
    _, protocol = find_protocol(experiment_path)
    if protocol.content_sha256 != attestation.protocol_sha256:
        raise ValueError("Phase 4 protocol differs from its attestation")
    return matches[0], attestation


def runtime_lineage(experiment_path: Path) -> Phase4LineageV0_1:
    experiment = load_experiment_config(experiment_path)
    _, protocol = find_protocol(experiment_path)
    _, attestation = load_attestation(experiment_path)
    return Phase4LineageV0_1(
        historical_reference_commit=experiment.historical_reference_commit,
        phase4_protocol_commit=attestation.phase4_protocol_commit,
        protocol_attestation_sha256=attestation.content_sha256,
        protocol_sha256=protocol.content_sha256,
        adversarial_split_sha256=protocol.adversarial_split_sha256,
        adversarial_oracle_sha256=protocol.adversarial_oracle_sha256,
        phase3b_confirmatory_comparison_sha256=(protocol.phase3b_confirmatory_comparison_sha256),
        phase3b_science_sha256=protocol.phase3b_science_sha256,
        phase3b_publication_verification_sha256=(protocol.phase3b_publication_verification_sha256),
        prompt_version="0.1.0",
        parser_version="0.1.0",
        evaluator_version="v0",
    )


def _verify_adversarial(rows: list[OpsRouteExample], dataset_root: Path, config: Any) -> None:
    path = dataset_root / "adversarial.jsonl"
    ordered = sorted(rows, key=lambda item: item.example_id)
    if len(ordered) != 32:
        raise ValueError("Phase 4 requires exactly 32 frozen adversarial records")
    if Counter(item.scenario_family for item in ordered) != {
        "refund_policy_routing": 16,
        "subscription_cancellation_retention": 16,
    }:
        raise ValueError("Phase 4 adversarial family balance mismatch")
    groups = Counter((item.scenario_family, item.archetype) for item in ordered)
    if len(groups) != 16 or set(groups.values()) != {2}:
        raise ValueError("Phase 4 requires two adversarial records per family/archetype")
    actual = {
        "byte": sha256_file(path),
        "split": content_sha256([item.record_sha256 for item in ordered]),
        "oracle": content_sha256([content_sha256(item.expected) for item in ordered]),
        "ids": content_sha256([item.example_id for item in ordered]),
    }
    expected = {
        "byte": config.adversarial_byte_sha256,
        "split": config.adversarial_split_sha256,
        "oracle": config.adversarial_oracle_sha256,
        "ids": config.adversarial_ids_sha256,
    }
    if actual != expected:
        raise ValueError(f"frozen adversarial identity mismatch: {actual}")


def _adversarial_rows(dataset_root: Path) -> list[OpsRouteExample]:
    with (dataset_root / "adversarial.jsonl").open(encoding="utf-8") as handle:
        return [OpsRouteExample.model_validate_json(line, strict=True) for line in handle]


def _required_protocol_paths(experiment_path: Path, protocol_path: Path) -> list[Path]:
    root = repository_root(experiment_path)
    experiment = load_experiment_config(experiment_path)
    paths = [
        experiment_path,
        resolve(experiment_path, experiment.adversarial_config_path),
        resolve(experiment_path, experiment.memo_config_path),
        protocol_path,
    ]
    paths.extend(sorted((root / "src/inheritbench/phase4").glob("*.py")))
    return paths


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
