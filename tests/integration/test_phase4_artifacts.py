from __future__ import annotations

from pathlib import Path

from inheritbench.artifacts.hashing import sha256_file
from inheritbench.phase4.config import load_experiment_config
from inheritbench.phase4.schemas import (
    Phase4AnalysisV0_1,
    Phase4CaseSelectionV0_1,
    Phase4DecisionV0_1,
    Phase4EvaluationManifestV0_1,
    Phase4EvidencePackV0_1,
    Phase4MemoAttemptV0_1,
    Phase4MemoValidationV0_1,
    Phase4MigrationAnalysisV0_1,
    Phase4ProtocolAttestationV0_1,
    Phase4ReplayVerificationV0_1,
    Phase4ShowcaseReplayV0_1,
)

EXPERIMENT = Path("configs/experiments/phase4.yaml")
ROOT = Path("artifacts/phase4")


def test_phase4_historical_bytes_and_protocol_attestation() -> None:
    experiment = load_experiment_config(EXPERIMENT)
    for expected in experiment.historical_artifacts:
        assert sha256_file(Path(expected.relative_path)) == expected.byte_sha256

    attestation_path = _single(ROOT, "attestations/*/attestation.json")
    attestation = Phase4ProtocolAttestationV0_1.model_validate_json(
        attestation_path.read_bytes(), strict=True
    )
    assert attestation.phase4_protocol_commit == ("26acce08bb5cf74e842306b09bfee12d074a8b8b")
    assert attestation.worktree_clean is True
    assert attestation.git_object_verification_passed is True


def test_phase4_six_adversarial_runs_and_replays_are_complete() -> None:
    manifests = [
        Phase4EvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(ROOT.glob("evaluations/*/manifest.json"))
    ]
    assert len(manifests) == 6
    assert len({item.system_id for item in manifests}) == 6
    assert {item.status for item in manifests} == {"COMPLETED"}
    assert {item.terminal_predictions for item in manifests} == {32}
    assert len({item.split_sha256 for item in manifests}) == 1
    assert len({item.oracle_sha256 for item in manifests}) == 1

    replays = [
        Phase4ReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(ROOT.glob("replays/*/verification.json"))
    ]
    evaluation_replays = [item for item in replays if item.kind == "evaluation"]
    assert len(evaluation_replays) == 6
    assert {item.status for item in evaluation_replays} == {"PASSED"}
    assert {item.original_artifact_id for item in evaluation_replays} == {
        item.run_id for item in manifests
    }


def test_phase4_derived_evidence_and_readiness_status() -> None:
    analysis = Phase4AnalysisV0_1.model_validate_json(
        _single(ROOT, "analysis/*/analysis.json").read_bytes(), strict=True
    )
    profiles = Phase4MigrationAnalysisV0_1.model_validate_json(
        _single(ROOT, "migration-profiles/*/profiles.json").read_bytes(), strict=True
    )
    cases = Phase4CaseSelectionV0_1.model_validate_json(
        _single(ROOT, "representative-cases/*/cases.json").read_bytes(), strict=True
    )
    evidence = Phase4EvidencePackV0_1.model_validate_json(
        _single(ROOT, "evidence-packs/*/evidence.json").read_bytes(), strict=True
    )

    assert len([item for item in analysis.matrices if item.group_key == "all"]) == 6
    assert len(profiles.rows) == len(profiles.recommendations) == 6
    assert {item.profile_id: item.recommendation for item in profiles.recommendations} == {
        "minimum_direct_labels": "target_hybrid_anchored_distillation_10",
        "maximum_confirmed_capability": "target_hybrid_anchored_distillation_10",
        "maximum_adversarial_resilience": "target_full_retrain",
        "minimum_complexity": "target_full_retrain",
        "no_source_teacher": "target_full_retrain",
        "original_labels_unavailable": "NO_VIABLE_TRAINED_MIGRATION",
    }
    assert len(cases.cases) == 8
    assert evidence.status == "VALIDATED"
    assert len({item.evidence_id for item in evidence.references}) == len(evidence.references)

    validation = Phase4MemoValidationV0_1.model_validate_json(
        _single(ROOT, "memo-validations/*/validation.json").read_bytes(), strict=True
    )
    attempt = Phase4MemoAttemptV0_1.model_validate_json(
        _single(ROOT, "memo-attempts/*/attempt.json").read_bytes(), strict=True
    )
    decision = Phase4DecisionV0_1.model_validate_json(
        _single(ROOT, "decisions/*/decision.json").read_bytes(), strict=True
    )
    showcase_replay = Phase4ShowcaseReplayV0_1.model_validate_json(
        _single(ROOT, "showcase-replays/*/verification.json").read_bytes(), strict=True
    )
    assert validation.status == "PASSED"
    assert attempt.status == "CREDENTIALS_MISSING"
    assert decision.phase4_status == "READY_FOR_GPT_MEMO"
    assert decision.day5_gate == "DAY5_BLOCKED_PENDING_GPT_MEMO"
    assert decision.automatic_phase5 is False
    assert showcase_replay.status == "PASSED"


def _single(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    assert len(matches) == 1
    return matches[0]
