from __future__ import annotations

from pathlib import Path

from inheritbench.phase3b.schemas import HybridTrainingScheduleV0_1


def test_phase3b_schedule_matches_budget_without_anchor_weighting() -> None:
    paths = list(Path("artifacts/phase3b/schedules").glob("*/schedule.json"))
    assert len(paths) == 1
    schedule = HybridTrainingScheduleV0_1.model_validate_json(paths[0].read_bytes(), strict=True)
    exposures = list(schedule.exposure_counts_by_record.values())

    assert schedule.processed_tokens == 272568
    assert schedule.residual_tokens == 75
    assert schedule.processed_tokens <= schedule.target_processed_tokens
    assert schedule.total_exposures == 672
    assert schedule.optimizer_steps == 168
    assert schedule.warmup_steps == 9
    assert schedule.checkpoint_steps == [56, 112, 168]
    assert max(exposures) == min(exposures) == 3
    assert schedule.exposure_counts_by_origin == {
        "original_anchor": 30,
        "teacher_output": 642,
    }
