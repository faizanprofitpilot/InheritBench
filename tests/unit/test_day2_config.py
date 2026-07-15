from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from inheritbench.config import load_yaml
from inheritbench.day2.config import load_experiment_config, load_method_config
from inheritbench.day2.schemas import MethodConfigV0_2


def test_day2_experiment_contains_exact_methods() -> None:
    experiment = load_experiment_config(Path("configs/experiments/day2.yaml"))
    methods = {load_method_config(Path(path)).method_id for path in experiment.method_config_paths}
    assert methods == {
        "source_base_supporting",
        "source_adapted_full",
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
    }


def test_day2_method_rejects_unknown_fields() -> None:
    raw = load_yaml(Path("configs/methods/source_base_supporting.yaml"))
    assert isinstance(raw, dict)
    raw["surprise"] = True
    with pytest.raises(ValidationError):
        MethodConfigV0_2.model_validate(raw, strict=True)


def test_source_method_rejects_target_model(tmp_path: Path) -> None:
    raw = load_yaml(Path("configs/methods/source_base_supporting.yaml"))
    assert isinstance(raw, dict)
    raw["model_config_path"] = "configs/models/target.yaml"
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="source model"):
        load_method_config(path)


def test_locked_warmup_is_ceil_five_percent() -> None:
    source = load_method_config(Path("configs/methods/source_adapted_full.yaml"))
    target = load_method_config(Path("configs/methods/target_full_retrain.yaml"))
    assert source.training is not None
    assert target.training is not None
    assert source.training.scheduler.warmup_steps == 12
    assert target.training.scheduler.warmup_steps == 9
