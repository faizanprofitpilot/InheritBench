from __future__ import annotations

from pathlib import Path

import pytest

from inheritbench.artifacts.hashing import sha256_file
from inheritbench.phase4.config import load_experiment_config
from inheritbench.phase4.memo import generate_gpt_memo
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
from inheritbench.phase4.showcase import build_showcase, finalize

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

    validations = [
        Phase4MemoValidationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(ROOT.glob("memo-validations/*/validation.json"))
    ]
    attempts = [
        Phase4MemoAttemptV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(ROOT.glob("memo-attempts/*/attempt.json"))
    ]
    decisions = [
        Phase4DecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(ROOT.glob("decisions/*/decision.json"))
    ]
    showcase_replays = [
        Phase4ShowcaseReplayV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(ROOT.glob("showcase-replays/*/verification.json"))
    ]
    assert len(validations) == 2
    assert {item.status for item in validations} == {"PASSED"}
    assert [(item.attempt_number, item.request_kind, item.status) for item in attempts] == [
        (2, "REPAIR", "INVALID_RESPONSE"),
        (1, "INITIAL", "INVALID_RESPONSE"),
        (1, "INITIAL", "CREDENTIALS_MISSING"),
    ]
    assert {item.phase4_status for item in decisions} == {
        "READY_FOR_GPT_MEMO",
        "PHASE4_COMPLETED_WITH_VALIDATED_GPT_MEMO",
    }
    final = next(
        item
        for item in decisions
        if item.phase4_status == "PHASE4_COMPLETED_WITH_VALIDATED_GPT_MEMO"
    )
    assert final.day5_gate == "DAY5_UNBLOCKED"
    assert final.automatic_phase5 is False
    assert len(showcase_replays) == 2
    assert {item.status for item in showcase_replays} == {"PASSED"}
    assert Path("artifacts/showcase/inheritbench-v0.1-gpt/manifest.json").is_file()


def test_phase4_completed_state_is_permanently_frozen() -> None:
    with pytest.raises(ValueError, match=r"validated GPT-5\.6 Sol memo already exists"):
        generate_gpt_memo(EXPERIMENT)
    with pytest.raises(FileExistsError, match="showcase already exists"):
        build_showcase(EXPERIMENT)
    with pytest.raises(ValueError, match="completed decision already exists"):
        finalize(EXPERIMENT)


def _single(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    assert len(matches) == 1
    return matches[0]
