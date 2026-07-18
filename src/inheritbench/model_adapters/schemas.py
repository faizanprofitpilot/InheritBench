"""Task-neutral model-adapter runtime schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ModelRuntimeIdentity(StrictModel):
    registry_id: str
    model_id: str
    revision: str
    architecture_class: str
    tokenizer_id: str
    tokenizer_revision: str
    device: str
    dtype: str
    adapter_sha256: Sha256 | None


class GenerationOutput(StrictModel):
    record_id: str
    status: Literal["COMPLETED", "FAILED"]
    raw_output: str
    prompt_sha256: Sha256
    input_ids_sha256: Sha256
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    error: str | None
    latency_ms: int = Field(ge=0)


class ScheduleItem(StrictModel):
    cursor: int = Field(ge=0)
    record_id: str
    sequence_tokens: int = Field(gt=0)
    cycle: int = Field(ge=0)
    accumulation_group: int = Field(ge=0)
    optimizer_step: int = Field(gt=0)


class TrainingSchedule(StrictModel):
    schema_version: Literal["inheritbench.training-schedule.v0.2"]
    schedule_id: str
    policy_type: Literal["deterministic-hash-v0.1", "frozen-record-order-v0.1"]
    seed: int = Field(ge=0)
    namespace: str
    items: list[ScheduleItem] = Field(min_length=1)
    processed_tokens: int = Field(gt=0)
    residual_tokens: int = Field(ge=0)
    optimizer_steps: int = Field(gt=0)
    warmup_steps: int = Field(ge=0)
    checkpoint_steps: list[int] = Field(min_length=1)
    order_sha256: Sha256
    content_sha256: Sha256


class TrainingTelemetry(StrictModel):
    optimizer_step: int = Field(gt=0)
    schedule_cursor: int = Field(gt=0)
    processed_tokens: int = Field(gt=0)
    loss: float
    learning_rate: float
    gradient_norm: float
    pre_clip_gradient_norm: float | None = None
    post_clip_gradient_norm: float | None = None
    mps_current_allocated_bytes: int | None
    mps_driver_allocated_bytes: int | None


class TrainingInitialization(StrictModel):
    seed: int = Field(ge=0)
    initial_adapter_sha256: Sha256
    trainable_parameter_names: list[str]
    trainable_parameter_shapes: dict[str, list[int]] = Field(default_factory=dict)
    trainable_parameters: int = Field(ge=0)
    total_parameters: int = Field(ge=0)
    rng_before_model_load_sha256: Sha256 | None = None
    rng_before_lora_sha256: Sha256 | None = None
    rng_after_lora_sha256: Sha256 | None = None


class CheckpointArtifact(StrictModel):
    checkpoint_id: str
    optimizer_step: int = Field(gt=0)
    adapter_directory: str
    adapter_sha256: Sha256
    trainer_state_sha256: Sha256
    validation_loss: float | None


class TrainingResult(StrictModel):
    status: Literal["COMPLETED", "FAILED"]
    run_id: str
    model: ModelRuntimeIdentity
    trainable_parameters: int = Field(ge=0)
    total_parameters: int = Field(ge=0)
    seed: int = Field(default=0, ge=0)
    initial_adapter_sha256: Sha256 = "0" * 64
    trainable_parameter_names: list[str] = Field(default_factory=list)
    trainable_parameter_shapes: dict[str, list[int]] = Field(default_factory=dict)
    rng_before_model_load_sha256: Sha256 | None = None
    rng_before_lora_sha256: Sha256 | None = None
    rng_after_lora_sha256: Sha256 | None = None
    rng_training_start_sha256: Sha256 | None = None
    optimizer_step_one_sha256: Sha256 | None = None
    processed_tokens: int = Field(ge=0)
    optimizer_steps_completed: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    losses: list[float]
    telemetry: list[TrainingTelemetry]
    checkpoints: list[CheckpointArtifact]
    error: str | None
