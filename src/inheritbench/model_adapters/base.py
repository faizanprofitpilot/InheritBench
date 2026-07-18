"""Model adapter protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    TrainingProfile,
)
from inheritbench.config import ModelConfig
from inheritbench.model_adapters.schemas import (
    GenerationOutput,
    ModelRuntimeIdentity,
    TrainingInitialization,
    TrainingResult,
    TrainingSchedule,
)


class ModelAdapter(Protocol):
    registry_id: str

    def probe(
        self,
        config: ModelConfig,
        *,
        device: str,
        adapter_directory: Path | None = None,
    ) -> ModelRuntimeIdentity: ...

    def generate(
        self,
        config: ModelConfig,
        records: list[CapabilityInputRecord],
        *,
        device: str,
        maximum_new_tokens: int,
        seed: int,
        adapter_directory: Path | None = None,
    ) -> tuple[ModelRuntimeIdentity, list[GenerationOutput]]: ...

    def sequence_lengths(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
    ) -> dict[str, int]: ...

    def training_encoding_manifest(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
    ) -> list[dict[str, Any]]: ...

    def training_initialization(
        self,
        config: ModelConfig,
        profile: TrainingProfile,
        *,
        device: str,
        seed: int,
    ) -> TrainingInitialization: ...

    def train(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
        schedule: TrainingSchedule,
        profile: TrainingProfile,
        *,
        device: str,
        run_id: str,
        output_root: Path,
        seed: int,
        resume_checkpoint: Path | None = None,
    ) -> TrainingResult: ...

    def validation_loss(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
        *,
        device: str,
        adapter_directory: Path,
    ) -> float: ...

    def verify_adapter(
        self,
        config: ModelConfig,
        adapter_directory: Path,
        *,
        device: str,
    ) -> ModelRuntimeIdentity: ...
