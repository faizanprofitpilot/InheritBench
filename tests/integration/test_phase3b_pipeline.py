from __future__ import annotations

from pathlib import Path

from inheritbench.phase3b.schemas import Phase3BHistoricalBaselineV0_1


def test_phase3b_baseline_materializes_immutable_blindspot_diagnosis() -> None:
    paths = list(Path("artifacts/phase3b/historical-baselines").glob("*/baseline.json"))
    assert len(paths) == 1
    baseline = Phase3BHistoricalBaselineV0_1.model_validate_json(paths[0].read_bytes(), strict=True)
    assert baseline.status == "PASS"
    assert baseline.matched_candidate_count == 768
    assert baseline.matched_accepted_count == 719
    assert baseline.duplicate_auto_candidate_count == 48
    assert baseline.duplicate_auto_accepted_count == 4
    assert baseline.duplicate_auto_policy_mismatch_count == 44
    assert baseline.duplicate_auto_uniform_wrong_contract_count == 44
    assert baseline.diagnosis_verdict == "SOURCE_TEACHER_CAPABILITY_BLIND_SPOT_CONFIRMED"
