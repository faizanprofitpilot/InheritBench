from __future__ import annotations

from pathlib import Path

from inheritbench.day3.schemas import (
    Day3DistributionDecisionV0_1,
    Day3ReplayVerificationV0_1,
    Day3ScientificDecisionV0_1,
    LeakageAuditV0_1,
    SyntheticDatasetManifestV0_1,
    SyntheticPoolManifestV0_1,
    TeacherAdapterVerificationV0_1,
    TeacherPredictionV0_1,
    TeacherRunManifestV0_1,
)

DAY3_ROOT = Path("artifacts/day3")


def test_real_day3_terminal_evidence_is_consistent() -> None:
    pool_paths = sorted((DAY3_ROOT / "pools").glob("*/manifest.json"))
    pools = [
        SyntheticPoolManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in pool_paths
    ]
    assert [(pool.phase, pool.candidate_count) for pool in pools] == [
        ("expansion", 256),
        ("initial", 512),
    ]
    audits = [
        LeakageAuditV0_1.model_validate_json(
            (manifest_path.parent / "leakage_audit.json").read_bytes(), strict=True
        )
        for manifest_path in pool_paths
    ]
    assert all(audit.zero_overlap for audit in audits)

    verification_path = next((DAY3_ROOT / "teacher-verifications").glob("*/verification.json"))
    verification = TeacherAdapterVerificationV0_1.model_validate_json(
        verification_path.read_bytes(), strict=True
    )
    assert verification.status == "VERIFIED"

    teacher_paths = sorted((DAY3_ROOT / "teacher-runs").glob("*/manifest.json"))
    teachers = [
        TeacherRunManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in teacher_paths
    ]
    assert sum(run.candidate_count for run in teachers) == 768
    assert sum(run.completed_outputs for run in teachers) == 768
    assert sum(run.failed_outputs for run in teachers) == 0
    for manifest_path, run in zip(teacher_paths, teachers, strict=True):
        prediction_path = manifest_path.parent / "predictions.jsonl"
        predictions = [
            TeacherPredictionV0_1.model_validate_json(line, strict=True)
            for line in prediction_path.read_text(encoding="utf-8").splitlines()
        ]
        assert len(predictions) == run.candidate_count

    dataset_path = next(
        path
        for path in (DAY3_ROOT / "synthetic-data").glob("*/manifest.json")
        if SyntheticDatasetManifestV0_1.model_validate_json(path.read_bytes(), strict=True).status
        == "FAILED"
    )
    dataset = SyntheticDatasetManifestV0_1.model_validate_json(
        dataset_path.read_bytes(), strict=True
    )
    assert dataset.candidate_count == 768
    assert dataset.accepted_count == 59
    assert dataset.rejected_count == 709
    assert dataset.selected_count == 0
    assert dataset.failure_code == "INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES"

    replay_paths = sorted((DAY3_ROOT / "replays").glob("*/verification.json"))
    replays = [
        Day3ReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in replay_paths
    ]
    assert len(replays) == 3
    assert sum(replay.records_verified for replay in replays) == 1_536
    assert all(replay.status == "PASSED" for replay in replays)

    science_path = next((DAY3_ROOT / "scientific-decisions").glob("*/decision.json"))
    science = Day3ScientificDecisionV0_1.model_validate_json(science_path.read_bytes(), strict=True)
    assert science.scientific_status == "SCIENTIFICALLY_FAILED"
    assert science.day4_gate == "DAY4_BLOCKED"
    assert science.reason_code == "INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES"

    distribution_path = next((DAY3_ROOT / "distribution-decisions").glob("*/decision.json"))
    distribution = Day3DistributionDecisionV0_1.model_validate_json(
        distribution_path.read_bytes(), strict=True
    )
    assert distribution.publication_status == "NOT_ATTEMPTED"
    assert distribution.day4_gate == "DAY4_BLOCKED"

    for directory in ("training", "validation", "test", "comparisons", "publications"):
        assert not any((DAY3_ROOT / directory).glob("*"))
