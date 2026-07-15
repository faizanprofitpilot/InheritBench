"""Strict configuration loading and root isolation for Day 3 recovery."""

from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import load_model_config, load_yaml
from inheritbench.day3_matched.schemas import (
    MatchedExperimentConfigV0_1,
    MatchedMethodConfigV0_1,
    MatchedPoolConfigV0_1,
)


def load_experiment_config(path: Path) -> MatchedExperimentConfigV0_1:
    config = MatchedExperimentConfigV0_1.model_validate(load_yaml(path), strict=True)
    method = load_method_config(resolve(path, config.method_config_path))
    pool = load_pool_config(resolve(path, config.pool_config_path))
    source = load_model_config(resolve(path, config.source_model_config_path))
    target = load_model_config(resolve(path, config.target_model_config_path))
    if source.role != "source" or target.role != "target":
        raise ValueError("matched recovery requires the pinned source and target roles")
    if source.model_family != "qwen2.5" or target.model_family != "olmo2":
        raise ValueError("matched recovery is locked to the Qwen-to-OLMo pair")
    if method.model_config_path != config.target_model_config_path:
        raise ValueError("matched distillation must train the configured target")
    if method.seed != config.seed or pool.seed != config.seed:
        raise ValueError("matched recovery seed mismatch")
    validate_isolated_root(resolve(path, config.artifact_root), config)
    validate_isolated_root(resolve(path, config.adapter_root), config)
    return config


def load_method_config(path: Path) -> MatchedMethodConfigV0_1:
    config = MatchedMethodConfigV0_1.model_validate(load_yaml(path), strict=True)
    model = load_model_config(resolve(path, config.model_config_path))
    if model.role != "target" or model.model_family != "olmo2":
        raise ValueError("matched synthetic distillation requires the pinned OLMo target")
    return config


def load_pool_config(path: Path) -> MatchedPoolConfigV0_1:
    return MatchedPoolConfigV0_1.model_validate(load_yaml(path), strict=True)


def config_sha256(config: object) -> str:
    return content_sha256(config)


def resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    if direct.exists() or path.parts[0] in {"artifacts", "adapters", "data", "configs"}:
        return direct
    return parent_file.parent / path


def validate_isolated_root(path: Path, config: MatchedExperimentConfigV0_1) -> None:
    resolved = path.resolve()
    original = resolve(Path.cwd(), config.original_day3_artifact_root).resolve()
    if resolved == original or resolved.is_relative_to(original):
        raise ValueError("matched recovery must never write beneath artifacts/day3")
    expected = {
        resolve(Path.cwd(), config.artifact_root).resolve(),
        resolve(Path.cwd(), config.adapter_root).resolve(),
    }
    if resolved not in expected:
        raise ValueError("matched recovery output root is not declared by the experiment")
