import json
from pathlib import Path

import pytest

from inheritbench.config import ModelConfig
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2 import data
from inheritbench.day2.config import load_experiment_config


def test_day2_data_freeze_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path("configs/experiments/day2.yaml")
    experiment = load_experiment_config(path)
    assert experiment.seed == 20260714
    bundle = next(Path("artifacts/day2/data").glob("day2-data-*"))
    frozen_counts: dict[str, dict[str, int]] = {}
    for schedule_name in ("source_primary", "target_primary"):
        schedule = json.loads((bundle / f"{schedule_name}.json").read_bytes())
        frozen_counts[schedule_name] = {
            item["example_id"]: item["sequence_tokens"] for item in schedule["items"]
        }

    def offline_token_counts(
        model: ModelConfig, examples: list[OpsRouteExample], _prompt_version: str
    ) -> dict[str, int]:
        schedule_name = "source_primary" if model.role == "source" else "target_primary"
        return {
            example.example_id: frozen_counts[schedule_name][example.example_id]
            for example in examples
        }

    monkeypatch.setattr(data, "training_token_counts", offline_token_counts)
    assert data.freeze_data(path) == data.freeze_data(path)
