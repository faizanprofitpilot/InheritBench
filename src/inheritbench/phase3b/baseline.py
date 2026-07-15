"""Historical baseline replay and preregistration attestation."""

from __future__ import annotations

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
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.day3_matched.schemas import (
    MatchedCandidateInputV0_1,
    MatchedFilterDecisionV0_1,
    MatchedOracleRecordV0_1,
    MatchedTeacherPredictionV0_1,
)
from inheritbench.phase3b.config import (
    config_sha256,
    load_confirmatory_config,
    load_experiment_config,
    load_method_config,
    resolve,
)
from inheritbench.phase3b.schemas import (
    Phase3BHistoricalBaselineV0_1,
    Phase3BPreregistrationAttestationV0_1,
)

_BASELINE_EXCLUSIONS = {"baseline_id", "created_at", "content_sha256"}
_ATTESTATION_EXCLUSIONS = {"attestation_id", "created_at", "content_sha256"}


def freeze_baseline(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    for expectation in experiment.historical_artifacts:
        path = resolve(experiment_path, expectation.relative_path)
        if not path.is_file() or sha256_file(path) != expectation.byte_sha256:
            raise ValueError(f"historical artifact hash mismatch: {path}")
        if expectation.content_sha256 is not None:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("content_sha256") != expectation.content_sha256:
                raise ValueError(f"historical content hash mismatch: {path}")
    diagnosis = _diagnose_duplicate_auto(experiment_path)
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase3b-historical-baseline-v0.1",
        "baseline_id": "pending",
        "status": "PASS",
        "historical_reference_commit": experiment.historical_reference_commit,
        "files": [item.model_dump(mode="json") for item in experiment.historical_artifacts],
        "matched_candidate_count": 768,
        "matched_accepted_count": 719,
        "matched_rejected_count": 49,
        **diagnosis,
        "diagnosis_verdict": "SOURCE_TEACHER_CAPABILITY_BLIND_SPOT_CONFIRMED",
        "generator_policy_verdict": "GENERATOR_POLICY_CONSISTENCY_CONFIRMED",
        "original_validation_previously_inspected": True,
        "original_test_previously_inspected": True,
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_BASELINE_EXCLUSIONS)
    baseline_id = f"phase3b-baseline-{identity[:16]}"
    baseline = Phase3BHistoricalBaselineV0_1.model_validate(
        {**payload, "baseline_id": baseline_id, "content_sha256": identity}, strict=True
    )
    root = resolve(experiment_path, experiment.artifact_root) / "historical-baselines"
    return write_atomic_bundle(
        root,
        baseline_id,
        {"baseline.json": canonical_json_bytes(baseline) + b"\n"},
    )


def attest_preregistration(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    if _git(["status", "--porcelain"]):
        raise ValueError("preregistration attestation requires a clean worktree")
    commit = _git(["rev-parse", "HEAD"])
    if commit == experiment.historical_reference_commit:
        raise ValueError("preregistration commit must follow the historical reference commit")
    root = resolve(experiment_path, experiment.artifact_root)
    if (root / "training").exists() or (root / "active").exists():
        raise ValueError("preregistration must be attested before real training begins")
    paths = _required_preregistration_paths(experiment_path)
    for path in paths:
        relative = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        tracked = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}:{relative}"],
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
        )
        if tracked.returncode != 0:
            raise ValueError(f"required preregistration path is not committed: {relative}")
        committed = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=Path.cwd(),
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"working-tree bytes differ from preregistration commit: {relative}")
    experiment_config = load_experiment_config(experiment_path)
    method = load_method_config(resolve(experiment_path, experiment.method_config_path))
    confirmatory = load_confirmatory_config(
        resolve(experiment_path, experiment.confirmatory_config_path)
    )
    artifacts = _preregistration_artifacts(root)
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase3b-preregistration-attestation-v0.1",
        "attestation_id": "pending",
        "preregistration_commit": commit,
        "worktree_clean": True,
        "tracked_diff_sha256": None,
        "experiment_config_sha256": config_sha256(experiment_config),
        "method_config_sha256": config_sha256(method),
        "confirmatory_config_sha256": config_sha256(confirmatory),
        "baseline_sha256": artifacts["baseline"]["content_sha256"],
        "synthetic_selection_sha256": artifacts["synthetic"]["content_sha256"],
        "anchor_selection_sha256": artifacts["anchors"]["content_sha256"],
        "hybrid_dataset_sha256": artifacts["hybrid"]["content_sha256"],
        "confirmatory_validation_sha256": artifacts["validation"]["content_sha256"],
        "confirmatory_test_sha256": artifacts["test"]["content_sha256"],
        "confirmatory_leakage_audit_sha256": artifacts["leakage"]["content_sha256"],
        "training_schedule_sha256": artifacts["schedule"]["content_sha256"],
        "required_paths_in_commit": [
            path.resolve().relative_to(Path.cwd().resolve()).as_posix() for path in paths
        ],
        "git_object_verification_passed": True,
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_ATTESTATION_EXCLUSIONS)
    attestation_id = f"phase3b-preregistration-{identity[:16]}"
    attestation = Phase3BPreregistrationAttestationV0_1.model_validate(
        {**payload, "attestation_id": attestation_id, "content_sha256": identity}, strict=True
    )
    return write_atomic_bundle(
        root / "preregistrations",
        attestation_id,
        {"attestation.json": canonical_json_bytes(attestation) + b"\n"},
    )


def _diagnose_duplicate_auto(experiment_path: Path) -> dict[str, int]:
    root = Path.cwd()
    pool_paths = [
        root / "artifacts/day3-matched/pools/day3-matched-pool-initial-e272e8a7b827bb01",
        root / "artifacts/day3-matched/pools/day3-matched-pool-expansion-dc0b0c265b3c3ed1",
    ]
    candidates: dict[str, MatchedCandidateInputV0_1] = {}
    oracles: dict[str, MatchedOracleRecordV0_1] = {}
    for pool in pool_paths:
        candidates.update(
            (item.candidate_id, item)
            for item in _read_jsonl(pool / "candidate_inputs.jsonl", MatchedCandidateInputV0_1)
        )
        oracles.update(
            (item.candidate_id, item)
            for item in _read_jsonl(pool / "candidate_oracle.jsonl", MatchedOracleRecordV0_1)
        )
    filter_path = (
        root
        / "artifacts/day3-matched/filtering"
        / "day3-matched-filter-36eea02e066b021a/filter_records.jsonl"
    )
    filters = _read_jsonl(filter_path, MatchedFilterDecisionV0_1)
    predictions: dict[str, MatchedTeacherPredictionV0_1] = {}
    for path in [
        root
        / "artifacts/day3-matched/teacher-runs"
        / "day3-matched-teacher-initial-20260715T123651-195bede8/predictions.jsonl",
        root
        / "artifacts/day3-matched/teacher-runs"
        / "day3-matched-teacher-expansion-20260715T125036-8f3c1dc8/predictions.jsonl",
    ]:
        predictions.update(
            (item.candidate_id, item) for item in _read_jsonl(path, MatchedTeacherPredictionV0_1)
        )
    relevant = [
        item
        for item in filters
        if candidates[item.candidate_id].scenario_family == "refund_policy_routing"
        and candidates[item.candidate_id].archetype == "duplicate_auto_refund"
    ]
    if len(relevant) != 48:
        raise ValueError("expected exactly 48 matched duplicate-auto candidates")
    accepted = sum(item.accepted for item in relevant)
    mismatched = [
        item for item in relevant if item.primary_rejection_reason == "POLICY_CONTRACT_MISMATCH"
    ]
    uniform_wrong = 0
    for item in relevant:
        candidate = candidates[item.candidate_id]
        context = candidate.input.context
        oracle = oracles[item.candidate_id].expected_contract
        if (
            context.get("payment_status") != "settled"
            or context.get("duplicate_evidence") != "confirmed"
            or oracle.decision != "execute"
            or oracle.tool != "refund_payment"
        ):
            raise ValueError("duplicate-auto candidate or oracle violates the frozen policy")
        if item in mismatched:
            prediction = predictions[item.candidate_id]
            contract = (
                prediction.parser_result.validated_contract if prediction.parser_result else None
            )
            if contract is not None and (
                contract.decision == "no_action"
                and contract.tool is None
                and contract.arguments == {}
                and contract.policy_code == "FIN-REFUND-05"
            ):
                uniform_wrong += 1
    if accepted != 4 or len(mismatched) != 44 or uniform_wrong != 44:
        raise ValueError("blind-spot diagnosis does not match the immutable evidence")
    return {
        "duplicate_auto_candidate_count": 48,
        "duplicate_auto_accepted_count": accepted,
        "duplicate_auto_policy_mismatch_count": len(mismatched),
        "duplicate_auto_uniform_wrong_contract_count": uniform_wrong,
    }


def _required_preregistration_paths(experiment_path: Path) -> list[Path]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    paths = [
        experiment_path,
        resolve(experiment_path, experiment.method_config_path),
        resolve(experiment_path, experiment.confirmatory_config_path),
    ]
    for directory, filename in [
        ("historical-baselines", "baseline.json"),
        ("synthetic-selections", "selection.json"),
        ("anchor-selections", "selection.json"),
        ("hybrid-data", "manifest.json"),
        ("confirmatory-data", "manifest.json"),
        ("leakage-audits", "audit.json"),
        ("schedules", "schedule.json"),
    ]:
        paths.append(_single_file(root / directory, filename))
    return paths


def _preregistration_artifacts(root: Path) -> dict[str, dict[str, Any]]:
    specs = {
        "baseline": ("historical-baselines", "baseline.json"),
        "synthetic": ("synthetic-selections", "selection.json"),
        "anchors": ("anchor-selections", "selection.json"),
        "hybrid": ("hybrid-data", "manifest.json"),
        "validation": ("confirmatory-data", "validation/manifest.json"),
        "test": ("confirmatory-data", "test/manifest.json"),
        "leakage": ("leakage-audits", "audit.json"),
        "schedule": ("schedules", "schedule.json"),
    }
    values: dict[str, dict[str, Any]] = {}
    for key, (directory, filename) in specs.items():
        path = _single_file(root / directory, filename)
        values[key] = json.loads(path.read_text(encoding="utf-8"))
    return values


def _single_file(root: Path, relative_name: str) -> Path:
    matches = sorted(root.glob(f"*/{relative_name}"))
    if len(matches) != 1:
        raise ValueError(f"expected one preregistration artifact {root}/*/{relative_name}")
    return matches[0]


def _git(arguments: list[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=Path.cwd(), check=True, capture_output=True, text=True
    ).stdout.strip()


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    return [schema.model_validate_json(line, strict=True) for line in path.read_text().splitlines()]
