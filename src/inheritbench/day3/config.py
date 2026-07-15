"""Day 3 strict configuration loading."""

from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import load_model_config, load_yaml
from inheritbench.day3.schemas import (
    Day3ExperimentConfigV0_1,
    Day3MethodConfigV0_1,
    SyntheticPoolConfigV0_1,
)


def load_experiment_config(path: Path) -> Day3ExperimentConfigV0_1:
    config = Day3ExperimentConfigV0_1.model_validate(load_yaml(path), strict=True)
    method = load_method_config(_resolve(path, config.method_config_path))
    pool = load_pool_config(_resolve(path, config.pool_config_path))
    source = load_model_config(_resolve(path, config.source_model_config_path))
    target = load_model_config(_resolve(path, config.target_model_config_path))
    if source.role != "source" or target.role != "target":
        raise ValueError("Day 3 requires the pinned source and target model roles")
    if method.model_config_path != config.target_model_config_path:
        raise ValueError("synthetic distillation must train the configured target model")
    if pool.seed != config.seed or method.seed != config.seed:
        raise ValueError("Day 3 seed mismatch")
    return config


def load_method_config(path: Path) -> Day3MethodConfigV0_1:
    config = Day3MethodConfigV0_1.model_validate(load_yaml(path), strict=True)
    model = load_model_config(_resolve(path, config.model_config_path))
    if model.role != "target" or model.model_family != "olmo2":
        raise ValueError("target_synthetic_distillation requires the pinned OLMo target")
    return config


def load_pool_config(path: Path) -> SyntheticPoolConfigV0_1:
    return SyntheticPoolConfigV0_1.model_validate(load_yaml(path), strict=True)


def config_sha256(config: object) -> str:
    return content_sha256(config)


def resolve(parent_file: Path, candidate: str) -> Path:
    return _resolve(parent_file, candidate)


def _resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    if direct.exists() or path.parts[0] in {"artifacts", "adapters", "data", "configs"}:
        return direct
    return parent_file.parent / path
