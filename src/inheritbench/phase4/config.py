"""Strict Phase 4 configuration loading and path isolation."""

from __future__ import annotations

from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import load_model_config, load_yaml
from inheritbench.phase4.schemas import (
    Phase4AdversarialConfigV0_1,
    Phase4ExperimentConfigV0_1,
    Phase4MemoConfigV0_1,
)


def repository_root(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / ".git").exists() and (parent / "pyproject.toml").is_file():
            return parent
    raise ValueError(f"unable to locate repository root from {path}")


def resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    return repository_root(parent_file) / path


def config_sha256(config: object) -> str:
    return content_sha256(config)


def load_adversarial_config(path: Path) -> Phase4AdversarialConfigV0_1:
    return Phase4AdversarialConfigV0_1.model_validate(load_yaml(path), strict=True)


def load_memo_config(path: Path) -> Phase4MemoConfigV0_1:
    return Phase4MemoConfigV0_1.model_validate(load_yaml(path), strict=True)


def load_experiment_config(path: Path) -> Phase4ExperimentConfigV0_1:
    config = Phase4ExperimentConfigV0_1.model_validate(load_yaml(path), strict=True)
    root = repository_root(path)
    adversarial = load_adversarial_config(resolve(path, config.adversarial_config_path))
    memo = load_memo_config(resolve(path, config.memo_config_path))
    if adversarial.generation.seed != config.seed:
        raise ValueError("Phase 4 generation seed differs from the experiment seed")
    if memo.model != "gpt-5.6-sol":
        raise ValueError("Phase 4 requires the official GPT-5.6 Sol model ID")
    artifact_root = resolve(path, config.artifact_root).resolve()
    showcase_root = resolve(path, config.showcase_root).resolve()
    allowed = {root / "artifacts/phase4", root / "artifacts/showcase/inheritbench-v0.1"}
    if artifact_root not in allowed or showcase_root not in allowed:
        raise ValueError("Phase 4 output roots must match the isolated frozen roots")
    historical = [
        (root / "artifacts/day2").resolve(),
        (root / "artifacts/day3").resolve(),
        (root / "artifacts/day3-matched").resolve(),
        (root / "artifacts/phase3b").resolve(),
    ]
    if any(
        artifact_root == item
        or artifact_root.is_relative_to(item)
        or showcase_root == item
        or showcase_root.is_relative_to(item)
        for item in historical
    ):
        raise ValueError("Phase 4 cannot write beneath historical evidence roots")
    for system in config.systems:
        model = load_model_config(resolve(path, system.model_config_path))
        expected_role = "source" if system.system_id.startswith("source_") else "target"
        if model.role != expected_role:
            raise ValueError(f"model role mismatch for {system.system_id}")
    return config
