from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from inheritbench.day3_matched.schemas import (
    Day3RecoveryDecisionV0_1,
    DistributionFingerprintV0_1,
    DistributionMatchAuditV0_1,
    MatchedDistributionDecisionV0_1,
    MatchedLeakageAuditV0_1,
    MatchedPoolManifestV0_1,
    MatchedReplayVerificationV0_1,
    MatchedSyntheticDatasetManifestV0_1,
    MatchedTeacherRunManifestV0_1,
    SyntheticAttemptComparisonV0_1,
)

ROOT = Path("artifacts/day3-matched")


def test_matched_pool_and_teacher_evidence_is_complete() -> None:
    fingerprint_path = next((ROOT / "fingerprints").glob("*/fingerprint.json"))
    fingerprint = DistributionFingerprintV0_1.model_validate_json(
        fingerprint_path.read_bytes(), strict=True
    )
    assert fingerprint.train_records == 224

    pool_paths = sorted((ROOT / "pools").glob("*/manifest.json"))
    pools = [
        MatchedPoolManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in pool_paths
    ]
    assert {item.phase: item.candidate_count for item in pools} == {
        "initial": 512,
        "expansion": 256,
    }
    for path in pool_paths:
        distribution = DistributionMatchAuditV0_1.model_validate_json(
            (path.parent / "distribution_audit.json").read_bytes(), strict=True
        )
        leakage = MatchedLeakageAuditV0_1.model_validate_json(
            (path.parent / "leakage_audit.json").read_bytes(), strict=True
        )
        assert distribution.status == "PASS"
        assert leakage.status == "PASS"
        assert leakage.zero_overlap is True

    teacher_paths = sorted((ROOT / "teacher-runs").glob("*/manifest.json"))
    teachers = [
        MatchedTeacherRunManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in teacher_paths
    ]
    assert sum(item.candidate_count for item in teachers) == 768
    assert sum(item.completed_outputs for item in teachers) == 768
    assert sum(item.failed_outputs for item in teachers) == 0


def test_matched_recovery_is_replayed_terminal_negative() -> None:
    dataset_paths = sorted((ROOT / "synthetic-data").glob("*/manifest.json"))
    datasets = [
        MatchedSyntheticDatasetManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in dataset_paths
    ]
    terminal = next(item for item in datasets if item.status == "TERMINAL_NEGATIVE")
    terminal_path = next(path.parent for path in dataset_paths if terminal.dataset_id in str(path))
    assert terminal.candidate_count == 768
    assert terminal.accepted_count == 719
    assert terminal.rejected_count == 49
    assert terminal.selected_count == 0

    candidate_archetypes = {}
    for path in sorted((ROOT / "pools").glob("*/candidate_inputs.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            candidate = json.loads(line)
            candidate_archetypes[candidate["candidate_id"]] = (
                f"{candidate['scenario_family']}:{candidate['archetype']}"
            )
    accepted: Counter[str] = Counter()
    for line in (terminal_path / "filter_records.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["accepted"]:
            accepted[candidate_archetypes[record["candidate_id"]]] += 1
    assert accepted["refund_policy_routing:duplicate_auto_refund"] == 4
    assert len(accepted) == 16

    comparison_path = next((ROOT / "comparisons").glob("*/attempt_comparison.json"))
    comparison = SyntheticAttemptComparisonV0_1.model_validate_json(
        comparison_path.read_bytes(), strict=True
    )
    assert [row["accepted_count"] for row in comparison.rows] == [59, 719]

    recovery_path = next((ROOT / "recovery-decisions").glob("*/decision.json"))
    recovery = Day3RecoveryDecisionV0_1.model_validate_json(recovery_path.read_bytes(), strict=True)
    assert recovery.recovery_status == "RECOVERY_TERMINAL_NEGATIVE"
    assert recovery.day4_gate == "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT"
    assert recovery.further_day3_attempts_allowed is False
    assert recovery.automatic_day4_started is False

    distribution_path = next((ROOT / "distribution-decisions").glob("*/decision.json"))
    distribution = MatchedDistributionDecisionV0_1.model_validate_json(
        distribution_path.read_bytes(), strict=True
    )
    assert distribution.publication_status == "NOT_ATTEMPTED"
    assert distribution.day4_gate == recovery.day4_gate

    replays = [
        MatchedReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((ROOT / "replays").glob("*/verification.json"))
    ]
    replay_kinds = Counter(item.kind for item in replays)
    assert replay_kinds == {
        "fingerprint": 1,
        "distribution": 2,
        "leakage": 2,
        "teacher": 2,
        "filter": 1,
        "failure_analysis": 1,
        "attempt_comparison": 1,
        "recovery_decision": 1,
    }

    assert not (ROOT / "training").exists()
    assert not (ROOT / "test").exists()
    assert not (ROOT / "publications").exists()
