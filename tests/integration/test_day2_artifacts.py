from pathlib import Path

from inheritbench.day2.config import load_experiment_config
from inheritbench.day2.data import freeze_data


def test_day2_data_freeze_is_idempotent() -> None:
    path = Path("configs/experiments/day2.yaml")
    experiment = load_experiment_config(path)
    assert experiment.seed == 20260714
    assert freeze_data(path) == freeze_data(path)
