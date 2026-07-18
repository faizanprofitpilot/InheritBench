"""Trusted evaluator plugin protocol."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from importlib.metadata import entry_points, version
from pathlib import Path
from typing import Any, Protocol

from inheritbench.artifacts.hashing import sha256_file
from inheritbench.capability.schemas import (
    GenericEvaluationResult,
    TrustedEvaluatorPluginConfig,
)


class TrustedEvaluatorPlugin(Protocol):
    plugin_id: str
    plugin_version: str

    def evaluate(
        self,
        *,
        record_id: str,
        raw_output: str,
        model_input: dict[str, Any],
        oracle: dict[str, Any],
    ) -> GenericEvaluationResult: ...


@dataclass(frozen=True)
class TrustedPluginBinding:
    plugin: TrustedEvaluatorPlugin
    distribution: str
    version: str
    code_sha256: str


def load_trusted_plugin(config: TrustedEvaluatorPluginConfig) -> TrustedPluginBinding:
    matches = [
        item
        for item in entry_points(group=config.entry_point_group)
        if item.name == config.entry_point_name
    ]
    if len(matches) != 1:
        raise ValueError("trusted evaluator entry point is missing or ambiguous")
    entry_point = matches[0]
    if entry_point.dist is None or entry_point.dist.name != config.distribution:
        raise ValueError("trusted evaluator distribution does not match configuration")
    installed_version = version(config.distribution)
    if installed_version != config.version:
        raise ValueError("trusted evaluator version does not match configuration")
    loaded = entry_point.load()
    plugin = loaded() if inspect.isclass(loaded) else loaded
    if (
        not hasattr(plugin, "evaluate")
        or plugin.plugin_id != config.entry_point_name
        or plugin.plugin_version != config.version
    ):
        raise ValueError("trusted evaluator does not implement the required protocol")
    module_path = Path(inspect.getfile(plugin.__class__))
    digest = sha256_file(module_path)
    if digest != config.code_sha256:
        raise ValueError("trusted evaluator code hash does not match configuration")
    return TrustedPluginBinding(
        plugin=plugin,
        distribution=config.distribution,
        version=installed_version,
        code_sha256=digest,
    )
