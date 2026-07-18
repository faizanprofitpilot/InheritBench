"""Deterministic test-only model adapter."""

from __future__ import annotations

import time
from pathlib import Path

from inheritbench.artifacts.hashing import (
    canonical_json,
    input_ids_sha256,
    sha256_bytes,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    TrainingProfile,
)
from inheritbench.config import ModelConfig
from inheritbench.model_adapters.schemas import (
    CheckpointArtifact,
    GenerationOutput,
    ModelRuntimeIdentity,
    TrainingInitialization,
    TrainingResult,
    TrainingSchedule,
    TrainingTelemetry,
)


class FakeModelAdapter:
    def __init__(self, registry_id: str, *, trained: bool = False) -> None:
        self.registry_id = registry_id
        self._trained = trained

    def probe(
        self,
        config: ModelConfig,
        *,
        device: str,
        adapter_directory: Path | None = None,
    ) -> ModelRuntimeIdentity:
        return self._identity(config, device, adapter_directory)

    def generate(
        self,
        config: ModelConfig,
        records: list[CapabilityInputRecord],
        *,
        device: str,
        maximum_new_tokens: int,
        seed: int,
        adapter_directory: Path | None = None,
    ) -> tuple[ModelRuntimeIdentity, list[GenerationOutput]]:
        del maximum_new_tokens, seed
        identity = self._identity(config, device, adapter_directory)
        outputs: list[GenerationOutput] = []
        trained = self._trained or adapter_directory is not None
        for record in records:
            started = time.perf_counter()
            key = (
                "teacher_output"
                if self.registry_id == "fake-source-v0.1"
                else "trained_output"
                if trained
                else "base_output"
            )
            value = record.payload.get(key, record.payload.get("teacher_output"))
            if not isinstance(value, dict):
                outputs.append(
                    GenerationOutput(
                        record_id=record.record_id,
                        status="FAILED",
                        raw_output="",
                        prompt_sha256=sha256_text(canonical_json(record.messages)),
                        input_ids_sha256=input_ids_sha256([]),
                        prompt_tokens=0,
                        completion_tokens=0,
                        error=f"fixture payload lacks {key}",
                        latency_ms=0,
                    )
                )
                continue
            raw_output = canonical_json(value)
            outputs.append(
                GenerationOutput(
                    record_id=record.record_id,
                    status="COMPLETED",
                    raw_output=raw_output,
                    prompt_sha256=sha256_text(canonical_json(record.messages)),
                    input_ids_sha256=input_ids_sha256([ord(char) for char in record.record_id]),
                    prompt_tokens=len(canonical_json(record.payload).split()),
                    completion_tokens=len(raw_output.split()),
                    error=None,
                    latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
                )
            )
        return identity, outputs

    def sequence_lengths(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
    ) -> dict[str, int]:
        del config
        return {
            record.record_id: max(
                1,
                len(canonical_json(record.input_record.messages).split())
                + len(record.assistant_label.split()),
            )
            for record in records
        }

    def training_encoding_manifest(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
    ) -> list[dict[str, object]]:
        lengths = self.sequence_lengths(config, records)
        return [
            {
                "record_id": record.record_id,
                "prompt_sha256": sha256_text(canonical_json(record.input_record.messages)),
                "assistant_label_sha256": record.assistant_label_sha256,
                "prompt_input_ids_sha256": input_ids_sha256(
                    [ord(char) for char in canonical_json(record.input_record.messages)]
                ),
                "assistant_input_ids_sha256": input_ids_sha256(
                    [ord(char) for char in record.assistant_label]
                ),
                "input_ids_sha256": input_ids_sha256([ord(char) for char in record.record_id]),
                "labels_sha256": sha256_text(record.assistant_label),
                "attention_mask_sha256": input_ids_sha256([1] * lengths[record.record_id]),
                "prompt_tokens": max(0, lengths[record.record_id] - 1),
                "supervised_tokens": 1,
                "sequence_tokens": lengths[record.record_id],
            }
            for record in sorted(records, key=lambda item: item.record_id)
        ]

    def training_initialization(
        self,
        config: ModelConfig,
        profile: TrainingProfile,
        *,
        device: str,
        seed: int,
    ) -> TrainingInitialization:
        del profile, device
        return TrainingInitialization(
            seed=seed,
            initial_adapter_sha256=sha256_text(
                f"{self.registry_id}:{config.revision}:{seed}:initial-adapter"
            ),
            trainable_parameter_names=["fake.lora_A", "fake.lora_B"],
            trainable_parameters=1024,
            total_parameters=4096,
        )

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
    ) -> TrainingResult:
        del records, profile, resume_checkpoint
        checkpoints: list[CheckpointArtifact] = []
        telemetry: list[TrainingTelemetry] = []
        for step in range(1, schedule.optimizer_steps + 1):
            telemetry.append(
                TrainingTelemetry(
                    optimizer_step=step,
                    schedule_cursor=min(step, len(schedule.items)),
                    processed_tokens=min(
                        schedule.processed_tokens,
                        int(schedule.processed_tokens * step / schedule.optimizer_steps),
                    ),
                    loss=1.0 / (step + 1),
                    learning_rate=0.0002 * (1 - step / schedule.optimizer_steps),
                    gradient_norm=0.5,
                    mps_current_allocated_bytes=None,
                    mps_driver_allocated_bytes=None,
                )
            )
            if step in schedule.checkpoint_steps:
                checkpoint_id = f"{run_id}-step-{step:04d}"
                adapter_bytes = canonical_json(
                    {"registry_id": self.registry_id, "step": step, "trained": True}
                ).encode()
                trainer_bytes = canonical_json(
                    {"optimizer_step": step, "schedule_id": schedule.schedule_id}
                ).encode()
                directory = write_atomic_bundle(
                    output_root,
                    checkpoint_id,
                    {
                        "adapter_config.json": adapter_bytes + b"\n",
                        "adapter_model.fake": adapter_bytes,
                        "trainer_state.json": trainer_bytes + b"\n",
                    },
                )
                checkpoints.append(
                    CheckpointArtifact(
                        checkpoint_id=checkpoint_id,
                        optimizer_step=step,
                        adapter_directory=str(directory),
                        adapter_sha256=sha256_bytes(adapter_bytes),
                        trainer_state_sha256=sha256_bytes(trainer_bytes + b"\n"),
                        validation_loss=None,
                    )
                )
        return TrainingResult(
            status="COMPLETED",
            run_id=run_id,
            model=self._identity(config, device, None),
            trainable_parameters=1024,
            total_parameters=4096,
            seed=seed,
            initial_adapter_sha256=sha256_text(
                f"{self.registry_id}:{config.revision}:{seed}:initial-adapter"
            ),
            trainable_parameter_names=["fake.lora_A", "fake.lora_B"],
            processed_tokens=schedule.processed_tokens,
            optimizer_steps_completed=schedule.optimizer_steps,
            duration_seconds=0.0,
            losses=[point.loss for point in telemetry],
            telemetry=telemetry,
            checkpoints=checkpoints,
            error=None,
        )

    def validation_loss(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
        *,
        device: str,
        adapter_directory: Path,
    ) -> float:
        del config, records, device
        step = int(adapter_directory.name.rsplit("-", 1)[-1])
        return 1.0 / (step + 1)

    def verify_adapter(
        self,
        config: ModelConfig,
        adapter_directory: Path,
        *,
        device: str,
    ) -> ModelRuntimeIdentity:
        if not (adapter_directory / "adapter_model.fake").is_file():
            raise FileNotFoundError("fake adapter payload is missing")
        return self._identity(config, device, adapter_directory)

    def _identity(
        self,
        config: ModelConfig,
        device: str,
        adapter_directory: Path | None,
    ) -> ModelRuntimeIdentity:
        adapter_sha = None
        if adapter_directory is not None:
            candidate = adapter_directory / "adapter_model.fake"
            if candidate.is_file():
                adapter_sha = sha256_file(candidate)
        return ModelRuntimeIdentity(
            registry_id=self.registry_id,
            model_id=config.model_id,
            revision=config.revision,
            architecture_class=config.expected_architecture_class,
            tokenizer_id=config.tokenizer_id,
            tokenizer_revision=config.tokenizer_revision,
            device=device,
            dtype="float32",
            adapter_sha256=adapter_sha,
        )
