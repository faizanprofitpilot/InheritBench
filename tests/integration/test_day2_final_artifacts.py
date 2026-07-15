from datetime import datetime
from pathlib import Path

from inheritbench.day2.evaluation import _read_predictions
from inheritbench.day2.schemas import (
    CheckpointDecisionV0_1,
    Day2ComparisonV0_1,
    EvaluationRunManifestV0_2,
    ReplayVerificationV0_2,
    SourceCapabilityDecisionV0_1,
)


def test_day2_final_artifact_matrix_is_complete() -> None:
    root = Path("artifacts/day2")
    decisions = [
        CheckpointDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "checkpoint-decisions").glob("*/decision.json"))
    ]
    assert len(decisions) == 3
    assert all(item.status == "SELECTED" for item in decisions)
    assert all(item.selected_adapter and item.selected_adapter.verified for item in decisions)

    gates = [
        SourceCapabilityDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "source-gates").glob("*/decision.json"))
    ]
    assert len(gates) == 1
    assert gates[0].status == "SOURCE_CAPABILITY_CONFIRMED"

    test_manifests = [
        EvaluationRunManifestV0_2.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "test").glob("*/manifest.json"))
    ]
    assert len(test_manifests) == 5
    assert all(item.status == "COMPLETED" and item.split == "test" for item in test_manifests)

    replays = [
        ReplayVerificationV0_2.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "replays").glob("*/verification.json"))
    ]
    assert len(replays) == 5
    assert {item.original_run_id for item in replays} == {item.run_id for item in test_manifests}

    comparison_paths = list((root / "comparisons").glob("*/comparison.json"))
    assert len(comparison_paths) == 1
    comparison = Day2ComparisonV0_1.model_validate_json(
        comparison_paths[0].read_bytes(), strict=True
    )
    assert len(comparison.rows) == 5
    assert {row.method_id for row in comparison.rows} == {
        "source_base_supporting",
        "source_adapted_full",
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
    }


def test_serialized_prediction_timestamps_parse_strictly() -> None:
    prediction_paths = sorted(Path("artifacts/day2/test").glob("*/predictions.jsonl"))
    assert len(prediction_paths) == 5
    records = _read_predictions(prediction_paths[0])
    assert len(records) == 32
    assert all(isinstance(record.started_at, datetime) for record in records)
