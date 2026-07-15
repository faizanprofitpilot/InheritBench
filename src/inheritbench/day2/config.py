"""Day 2 configuration loading and cross-file validation."""

from __future__ import annotations

from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import ModelConfig, load_model_config, load_yaml
from inheritbench.day2.schemas import Day2ExperimentConfig, MethodConfigV0_2, MethodId


def load_method_config(path: Path) -> MethodConfigV0_2:
    config = MethodConfigV0_2.model_validate(load_yaml(path), strict=True)
    model = load_model_config(_resolve(path, config.model_config_path))
    _validate_method_model(config, model)
    return config


def load_experiment_config(path: Path) -> Day2ExperimentConfig:
    config = Day2ExperimentConfig.model_validate(load_yaml(path), strict=True)
    methods = [load_method_config(_resolve(path, item)) for item in config.method_config_paths]
    expected: set[MethodId] = {
        "source_base_supporting",
        "source_adapted_full",
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
    }
    actual = {method.method_id for method in methods}
    if actual != expected or len(methods) != len(actual):
        raise ValueError(f"experiment methods must be exactly {sorted(expected)}")
    return config


def method_config_hash(config: MethodConfigV0_2) -> str:
    return content_sha256(config)


def resolved_model_config(method_path: Path, config: MethodConfigV0_2) -> ModelConfig:
    return load_model_config(_resolve(method_path, config.model_config_path))


def _resolve(parent_file: Path, candidate: str) -> Path:
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        return candidate_path
    direct = Path.cwd() / candidate_path
    if direct.exists():
        return direct
    return parent_file.parent / candidate_path


def _validate_method_model(method: MethodConfigV0_2, model: ModelConfig) -> None:
    source = method.method_id.startswith("source_")
    if source and model.role != "source":
        raise ValueError(f"{method.method_id} must reference the source model")
    if not source and model.role != "target":
        raise ValueError(f"{method.method_id} must reference the target model")
    if model.revision != model.tokenizer_revision:
        raise ValueError("Day 2 requires matching pinned model and tokenizer revisions")
