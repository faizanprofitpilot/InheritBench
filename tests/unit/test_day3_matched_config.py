from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from inheritbench.artifacts.hashing import sha256_file
from inheritbench.config import load_yaml
from inheritbench.day3_matched.baseline import (
    build_baseline,
    historical_tree_sha256,
)
from inheritbench.day3_matched.config import load_experiment_config
from inheritbench.day3_matched.schemas import MatchedExperimentConfigV0_1

EXPERIMENT = Path("configs/experiments/day3_matched.yaml")


def test_matched_configs_are_strict_and_isolated() -> None:
    config = load_experiment_config(EXPERIMENT)
    assert config.artifact_root == "artifacts/day3-matched"
    assert config.original_day3_artifact_root == "artifacts/day3"
    raw = load_yaml(EXPERIMENT)
    assert isinstance(raw, dict)
    raw["surprise"] = True
    with pytest.raises(ValidationError):
        MatchedExperimentConfigV0_1.model_validate(raw, strict=True)


def test_original_day3_root_is_rejected_for_outputs() -> None:
    raw = load_yaml(EXPERIMENT)
    assert isinstance(raw, dict)
    raw["artifact_root"] = "artifacts/day3"
    with pytest.raises(ValidationError):
        MatchedExperimentConfigV0_1.model_validate(raw, strict=True)


def test_historical_baseline_matches_frozen_evidence() -> None:
    baseline = build_baseline(EXPERIMENT)
    assert baseline.original_candidate_count == 768
    assert baseline.original_accepted_count == 59
    assert baseline.original_selected_count == 0
    assert baseline.original_day3_tree_sha256 == historical_tree_sha256(Path("artifacts/day3"))
    for item in baseline.files:
        assert sha256_file(Path("artifacts/day3") / item.relative_path) == item.byte_sha256
