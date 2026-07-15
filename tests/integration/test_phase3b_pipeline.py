from __future__ import annotations

from pathlib import Path

from inheritbench.phase3b.schemas import (
    Phase3BCheckpointDecisionV0_1,
    Phase3BComparisonV0_1,
    Phase3BEvaluationManifestV0_1,
    Phase3BFailureAnalysisV0_1,
    Phase3BHistoricalBaselineV0_1,
    Phase3BReplayVerificationV0_1,
    Phase3BScientificDecisionV0_1,
    Phase3BTrainingManifestV0_1,
)


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


def test_phase3b_real_scientific_evidence_is_complete_and_replayed() -> None:
    training_path = next(Path("artifacts/phase3b/training").glob("*/manifest.json"))
    training = Phase3BTrainingManifestV0_1.model_validate_json(
        training_path.read_bytes(), strict=True
    )
    decision_path = next(Path("artifacts/phase3b/checkpoint-decisions").glob("*/decision.json"))
    checkpoint = Phase3BCheckpointDecisionV0_1.model_validate_json(
        decision_path.read_bytes(), strict=True
    )
    runs = [
        Phase3BEvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in Path("artifacts/phase3b/test").glob("*/manifest.json")
    ]
    replays = [
        Phase3BReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in Path("artifacts/phase3b/replays").glob("*/verification.json")
    ]
    primary_path = next(
        path
        for path in Path("artifacts/phase3b/comparisons").glob("*/comparison.json")
        if '"PRIMARY_CONFIRMATORY_SIX_SYSTEM"' in path.read_text()
    )
    primary = Phase3BComparisonV0_1.model_validate_json(primary_path.read_bytes(), strict=True)
    analysis_path = next(Path("artifacts/phase3b/failure-analysis").glob("*/analysis.json"))
    analysis = Phase3BFailureAnalysisV0_1.model_validate_json(
        analysis_path.read_bytes(), strict=True
    )
    science_path = next(Path("artifacts/phase3b/scientific-decisions").glob("*/decision.json"))
    science = Phase3BScientificDecisionV0_1.model_validate_json(
        science_path.read_bytes(), strict=True
    )

    assert training.status == "COMPLETED"
    assert training.optimizer_steps_completed == 168
    assert training.processed_tokens == 272568
    assert checkpoint.status == "SELECTED"
    assert checkpoint.selected_checkpoint_id is not None
    assert checkpoint.fresh_base_reload_verified is True
    assert len(runs) == 6
    assert {item.split_sha256 for item in runs} == {primary.evaluation_surface_sha256}
    assert all(item.status == "COMPLETED" and item.terminal_predictions == 64 for item in runs)
    replayed = {item.original_artifact_id for item in replays if item.status == "PASSED"}
    assert {item.run_id for item in runs}.issubset(replayed)
    assert analysis.anchored_group["semantic_exact"] == 4
    assert primary.no_mixed_test_surfaces is True
    assert len(primary.rows) == 6
    assert science.scientific_status == "PHASE3B_SCIENTIFICALLY_COMPLETED"
    assert science.day4_gate == "DAY4_UNBLOCKED"
    assert science.publication_independent is True
    assert science.automatic_day4 is False
