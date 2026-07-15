"""Phase 3B strict configuration and root isolation."""

from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import load_model_config, load_yaml
from inheritbench.phase3b.schemas import (
    ConfirmatorySplitConfigV0_1,
    HybridMethodConfigV0_1,
    Phase3BExperimentConfigV0_1,
)


def load_experiment_config(path: Path) -> Phase3BExperimentConfigV0_1:
    config = Phase3BExperimentConfigV0_1.model_validate(load_yaml(path), strict=True)
    method = load_method_config(resolve(path, config.method_config_path))
    confirmatory = load_confirmatory_config(resolve(path, config.confirmatory_config_path))
    source = load_model_config(resolve(path, config.source_model_config_path))
    target = load_model_config(resolve(path, config.target_model_config_path))
    if source.role != "source" or source.model_family != "qwen2.5":
        raise ValueError("Phase 3B requires the pinned Qwen source")
    if target.role != "target" or target.model_family != "olmo2":
        raise ValueError("Phase 3B requires the pinned OLMo target")
    if method.model_config_path != config.target_model_config_path:
        raise ValueError("Phase 3B must train the configured target")
    if method.seed != config.seed or confirmatory.seed != config.seed:
        raise ValueError("Phase 3B seed mismatch")
    validate_isolated_root(resolve(path, config.artifact_root), config)
    validate_isolated_root(resolve(path, config.adapter_root), config)
    return config


def load_method_config(path: Path) -> HybridMethodConfigV0_1:
    config = HybridMethodConfigV0_1.model_validate(load_yaml(path), strict=True)
    target = load_model_config(resolve(path, config.model_config_path))
    if target.role != "target" or target.model_family != "olmo2":
        raise ValueError("anchored transfer requires the pinned OLMo target")
    return config


def load_confirmatory_config(path: Path) -> ConfirmatorySplitConfigV0_1:
    return ConfirmatorySplitConfigV0_1.model_validate(load_yaml(path), strict=True)


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


def validate_isolated_root(path: Path, config: Phase3BExperimentConfigV0_1) -> None:
    resolved = path.resolve()
    forbidden = [
        resolve(Path.cwd(), config.day2_artifact_root).resolve(),
        resolve(Path.cwd(), config.independent_day3_root).resolve(),
        resolve(Path.cwd(), config.matched_day3_root).resolve(),
    ]
    if any(resolved == root or resolved.is_relative_to(root) for root in forbidden):
        raise ValueError("Phase 3B must never write beneath historical artifact roots")
    expected = {
        resolve(Path.cwd(), config.artifact_root).resolve(),
        resolve(Path.cwd(), config.adapter_root).resolve(),
    }
    if resolved not in expected:
        raise ValueError("Phase 3B output root is not declared by the experiment")
