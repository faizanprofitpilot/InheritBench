"""Strict schemas for Day 2 methods, runs, decisions, and publication."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inheritbench.artifacts.schemas import ArtifactReference, GenerationConfig
from inheritbench.config import FullCommitSha, ScenarioFamily, Sha256
from inheritbench.data.opsroute.schemas import EvaluationMetadata, SplitName
from inheritbench.evaluation.contracts import ActionContract, Decision
from inheritbench.evaluation.metrics import AtomicMetrics
from inheritbench.evaluation.parser import ParserResult

MethodId = Literal[
    "source_base_supporting",
    "source_adapted_full",
    "target_untouched",
    "target_full_retrain",
    "target_limited_retrain_10pct",
]
TrainableMethodId = Literal[
    "source_adapted_full",
    "target_full_retrain",
    "target_limited_retrain_10pct",
]
RunStatus = Literal["COMPLETED", "FAILED", "BLOCKED", "NOT_RUN"]


class Day2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OptimizerConfig(Day2Model):
    name: Literal["AdamW"]
    learning_rate: float = Field(gt=0)
    betas: list[float] = Field(min_length=2, max_length=2)
    epsilon: float = Field(gt=0)
    weight_decay: float = Field(ge=0)


class SchedulerConfig(Day2Model):
    name: Literal["linear"]
    warmup_ratio: float
    warmup_steps: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_ratio(self) -> SchedulerConfig:
        if self.warmup_ratio != 0.05:
            raise ValueError("warmup_ratio must be exactly 0.05")
        return self


class LoraConfigV0_2(Day2Model):
    rank: Literal[8]
    alpha: Literal[16]
    dropout: float
    bias: Literal["none"]
    target_modules: list[Literal["q_proj", "k_proj", "v_proj", "o_proj"]]

    @model_validator(mode="after")
    def validate_targets(self) -> LoraConfigV0_2:
        if self.target_modules != ["q_proj", "k_proj", "v_proj", "o_proj"]:
            raise ValueError("LoRA targets must be exactly q_proj, k_proj, v_proj, o_proj")
        if self.dropout != 0.05:
            raise ValueError("LoRA dropout must be exactly 0.05")
        return self


class TrainingConfigV0_2(Day2Model):
    train_manifest_name: Literal["full_train", "limited_train"]
    schedule_name: Literal["source_primary", "target_primary", "target_limited_primary"]
    train_dtype: Literal["float32"]
    batch_size: Literal[1]
    gradient_accumulation_steps: Literal[4]
    gradient_clip_norm: float
    maximum_sequence_length: Literal[1024]
    seed: Literal[20260714]
    optimizer: OptimizerConfig
    scheduler: SchedulerConfig
    lora: LoraConfigV0_2
    optimizer_steps: int = Field(gt=0)
    checkpoint_steps: list[int]
    target_processed_tokens: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_training_budget(self) -> TrainingConfigV0_2:
        if self.gradient_clip_norm != 1.0:
            raise ValueError("gradient_clip_norm must be exactly 1.0")
        if not self.checkpoint_steps or sorted(set(self.checkpoint_steps)) != self.checkpoint_steps:
            raise ValueError("checkpoint_steps must be sorted and unique")
        if self.checkpoint_steps[-1] != self.optimizer_steps:
            raise ValueError("the final optimizer step must be a checkpoint")
        expected_warmup = max(1, __import__("math").ceil(self.optimizer_steps * 0.05))
        if self.scheduler.warmup_steps != expected_warmup:
            raise ValueError(f"warmup_steps must be {expected_warmup}")
        return self


class BoundedCorrectionConfig(Day2Model):
    kind: Literal["NUMERICAL_INSTABILITY", "STABLE_UNDERFITTING"]
    parent_failure_run_id: str
    parent_method_config_sha256: Sha256
    changed_fields: list[str] = Field(min_length=1)
    attempt: Literal[1]


class MethodConfigV0_2(Day2Model):
    schema_version: Literal["method-config-v0.2"]
    method_id: MethodId
    model_config_path: str
    training_kind: Literal["none", "lora"]
    prompt_template_version: Literal["0.1.0"]
    parser_version: Literal["0.1.0"]
    evaluator_version: Literal["v0"]
    dataset_version: Literal["0.1.0"]
    seed: Literal[20260714]
    training: TrainingConfigV0_2 | None
    correction: BoundedCorrectionConfig | None = None

    @model_validator(mode="after")
    def validate_method(self) -> MethodConfigV0_2:
        base_methods = {"source_base_supporting", "target_untouched"}
        if self.method_id in base_methods and (self.training_kind != "none" or self.training):
            raise ValueError("base methods cannot declare training")
        if self.method_id not in base_methods and (
            self.training_kind != "lora" or self.training is None
        ):
            raise ValueError("adapted methods require LoRA training settings")
        if (
            self.method_id == "target_limited_retrain_10pct"
            and self.training is not None
            and self.training.train_manifest_name != "limited_train"
        ):
            raise ValueError("limited target must use limited_train")
        if self.correction is not None:
            if self.training is None:
                raise ValueError("a bounded correction requires training settings")
            if self.correction.kind == "NUMERICAL_INSTABILITY":
                if self.correction.changed_fields != ["training.optimizer.learning_rate"]:
                    raise ValueError("numerical correction may change only the learning rate")
                if self.training.optimizer.learning_rate != 0.0001:
                    raise ValueError("numerical correction learning rate must be 1e-4")
        return self


class Day2ExperimentConfig(Day2Model):
    schema_version: Literal["day2-experiment-v0.1"]
    experiment_id: Literal["inheritbench-day2-v0.1"]
    dataset_directory: str
    task_config_path: str
    method_config_paths: list[str] = Field(min_length=5, max_length=5)
    data_output_root: str
    artifact_root: str
    adapter_root: str
    seed: Literal[20260714]
    limited_selection_version: Literal["day2-limited-v0.1"]
    final_test_requires_source_confirmation: Literal[True]
    adversarial_evaluation: Literal[False]


class SubsetEntry(Day2Model):
    example_id: str
    record_sha256: Sha256
    split: SplitName
    scenario_family: ScenarioFamily
    archetype: str
    expected_decision: Decision
    selection_rank: Sha256


class Day2SubsetManifest(Day2Model):
    schema_version: Literal["day2-subset-v0.1"]
    subset_id: str
    purpose: Literal["training", "validation", "final_test"]
    dataset_sha256: Sha256
    source_split: Literal["train", "validation", "test"]
    fixture_evidence: Literal[False]
    selection_version: str
    selection_rule: str
    entries: list[SubsetEntry] = Field(min_length=1)
    actual_fraction_of_train: float | None
    content_sha256: Sha256

    @property
    def example_ids(self) -> list[str]:
        return [entry.example_id for entry in self.entries]


class ScheduleItem(Day2Model):
    cursor: int = Field(ge=0)
    cycle: int = Field(ge=0)
    example_id: str
    sequence_tokens: int = Field(gt=0)


class TrainingScheduleManifestV0_1(Day2Model):
    schema_version: Literal["training-schedule-v0.1"]
    schedule_id: str
    method_id: TrainableMethodId
    subset_content_sha256: Sha256
    tokenizer_id: str
    tokenizer_revision: FullCommitSha
    seed: Literal[20260714]
    ordering_rule: str
    target_processed_tokens: int = Field(gt=0)
    processed_tokens: int = Field(gt=0)
    residual_tokens: int = Field(ge=0)
    budget_ratio: float = Field(gt=0, le=1)
    unique_examples: int = Field(gt=0)
    example_exposures: int = Field(gt=0)
    optimizer_steps: int = Field(gt=0)
    gradient_accumulation_steps: Literal[4]
    warmup_steps: int = Field(gt=0)
    checkpoint_steps: list[int] = Field(min_length=1)
    per_example_exposures: dict[str, int]
    token_counts: dict[str, int]
    items: list[ScheduleItem] = Field(min_length=1)
    content_sha256: Sha256


class Day2DataBundleManifest(Day2Model):
    schema_version: Literal["day2-data-bundle-v0.1"]
    bundle_id: str
    dataset_sha256: Sha256
    subset_sha256s: dict[str, Sha256]
    schedule_sha256s: dict[str, Sha256]
    created_at: datetime
    content_sha256: Sha256


class TrainingTelemetryPoint(Day2Model):
    optimizer_step: int = Field(gt=0)
    schedule_cursor: int = Field(ge=0)
    processed_tokens: int = Field(ge=0)
    loss: float
    learning_rate: float = Field(ge=0)
    gradient_norm: float = Field(ge=0)
    mps_current_allocated_bytes: int | None = Field(default=None, ge=0)
    mps_driver_allocated_bytes: int | None = Field(default=None, ge=0)


class CheckpointManifestV0_1(Day2Model):
    schema_version: Literal["checkpoint-v0.1"]
    checkpoint_id: str
    run_id: str
    method_id: TrainableMethodId
    optimizer_step: int = Field(gt=0)
    schedule_cursor: int = Field(gt=0)
    processed_tokens: int = Field(gt=0)
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    adapter_file_sha256s: dict[str, Sha256]
    trainer_state_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


class TrainingRunManifestV0_2(Day2Model):
    schema_version: Literal["training-run-v0.2"]
    run_id: str
    method_id: TrainableMethodId
    status: RunStatus
    failure_code: str | None
    failure_message: str | None
    resumed_from_run_id: str | None
    resumed_from_checkpoint_id: str | None
    model_id: str
    model_revision: FullCommitSha
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    subset_sha256: Sha256
    trainable_parameters: int = Field(ge=0)
    total_parameters: int = Field(ge=0)
    optimizer_steps_completed: int = Field(ge=0)
    processed_tokens: int = Field(ge=0)
    losses: list[float]
    telemetry: list[TrainingTelemetryPoint]
    checkpoint_ids: list[str]
    duration_seconds: float = Field(ge=0)
    resolved_device: str | None
    resolved_dtype: str | None
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class AdapterReference(Day2Model):
    adapter_id: str
    relative_path: str
    file_sha256s: dict[str, Sha256]
    total_bytes: int = Field(ge=0)
    verified: bool
    verified_at: datetime | None


class CheckpointScore(Day2Model):
    checkpoint_id: str
    optimizer_step: int = Field(gt=0)
    evaluation_run_id: str
    completed_predictions: int = Field(ge=0)
    semantic_exact: float = Field(ge=0, le=1)
    strict_valid: float = Field(ge=0, le=1)
    abstention_accuracy: float = Field(ge=0, le=1)
    approval_accuracy: float = Field(ge=0, le=1)
    argument_f1: float = Field(ge=0, le=1)
    teacher_forced_loss: float = Field(ge=0)
    unauthorized_actions: int = Field(ge=0)
    approval_bypasses: int = Field(ge=0)
    false_actions: int = Field(ge=0)
    eligible: bool
    rejection_reasons: list[str]


class CheckpointDecisionV0_1(Day2Model):
    schema_version: Literal["checkpoint-decision-v0.1"]
    decision_id: str
    method_id: TrainableMethodId
    status: Literal["SELECTED", "FAILED"]
    failure_code: Literal["NO_SAFETY_ELIGIBLE_CHECKPOINT"] | None
    training_run_id: str
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    scores: list[CheckpointScore]
    selected_checkpoint_id: str | None
    selected_adapter: AdapterReference | None
    selection_rule: str
    created_at: datetime
    content_sha256: Sha256


class PredictionRecordV0_2(Day2Model):
    schema_version: Literal["prediction-v0.2"]
    prediction_id: str
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    method_id: MethodId
    adapter_id: str | None
    checkpoint_decision_sha256: Sha256 | None
    example_id: str
    split: Literal["validation", "test"]
    scenario_family: ScenarioFamily
    archetype: str
    model_id: str
    model_revision: FullCommitSha
    model_config_sha256: Sha256
    architecture_class: str | None
    resolved_device: str | None
    resolved_dtype: str | None
    task_version: Literal["0.1.0"]
    template_version: Literal["0.1.0"]
    prompt_template_version: Literal["0.1.0"]
    parser_version: Literal["0.1.0"]
    evaluator_version: Literal["v0"]
    prompt_sha256: Sha256 | None
    input_ids_sha256: Sha256 | None
    generation: GenerationConfig
    prompt_token_count: int | None = Field(default=None, ge=0)
    generated_token_count: int | None = Field(default=None, ge=0)
    finish_condition: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"] | None
    raw_output: str
    parser_result: ParserResult | None
    expected_contract: ActionContract
    expected_contract_sha256: Sha256
    evaluation_metadata: EvaluationMetadata
    metrics: AtomicMetrics | None
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    errors: list[str]
    content_sha256: Sha256


class MetricValue(Day2Model):
    count: int = Field(ge=0)
    sum: float | None
    mean: float | None


class EvaluationBreakdown(Day2Model):
    key: str
    prediction_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    metrics: dict[str, MetricValue]
    parser_classifications: dict[str, int]


class EvaluationSummaryV0_2(Day2Model):
    schema_version: Literal["evaluation-summary-v0.2"]
    run_id: str
    method_id: MethodId
    status: RunStatus
    split: Literal["validation", "test"]
    prediction_counts: dict[str, int]
    aggregate_metrics: dict[str, MetricValue]
    parser_classifications: dict[str, int]
    breakdowns: dict[str, EvaluationBreakdown]
    run_errors: list[str]
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class EvaluationRunManifestV0_2(Day2Model):
    schema_version: Literal["evaluation-run-v0.2"]
    run_id: str
    method_id: MethodId
    status: RunStatus
    split: Literal["validation", "test"]
    method_config_sha256: Sha256
    subset_sha256: Sha256
    dataset_sha256: Sha256
    adapter: AdapterReference | None
    checkpoint_decision_sha256: Sha256 | None
    generation: GenerationConfig
    command: list[str]
    prediction_artifact: ArtifactReference
    summary_artifact: ArtifactReference
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class SourceCapabilityMetrics(Day2Model):
    semantic: float
    strict: float
    family_semantic: dict[ScenarioFamily, float]
    family_strict: dict[ScenarioFamily, float]
    tool_accuracy: float
    approval_accuracy: float
    abstention_accuracy: float
    argument_f1: float
    unauthorized_actions: int
    approval_bypasses: int
    false_actions: int


class SourceCapabilityDecisionV0_1(Day2Model):
    schema_version: Literal["source-capability-decision-v0.1"]
    gate_id: str
    status: Literal[
        "SOURCE_CAPABILITY_CONFIRMED",
        "SOURCE_CAPABILITY_WEAK",
        "SOURCE_CAPABILITY_NOT_CONFIRMED",
    ]
    source_base_validation_run_id: str
    source_adapted_validation_run_id: str
    base: SourceCapabilityMetrics
    adapted: SourceCapabilityMetrics
    semantic_gain: float
    strict_gain: float
    criteria: dict[str, bool]
    bounded_correction: Literal["NONE", "STABLE_UNDERFITTING", "NUMERICAL_INSTABILITY"]
    created_at: datetime
    content_sha256: Sha256


class MethodComparisonRow(Day2Model):
    method_id: MethodId
    status: Literal["COMPLETED"]
    evaluation_run_id: str
    replay_id: str
    method_config_sha256: Sha256
    adapter_id: str | None
    metrics: dict[str, Any]
    breakdowns: dict[str, Any]
    training: dict[str, Any] | None
    strict_retention: float | None
    semantic_retention: float | None
    retention_error: Literal["ZERO_DENOMINATOR"] | None


class Day2ComparisonV0_1(Day2Model):
    schema_version: Literal["day2-comparison-v0.1"]
    comparison_id: str
    status: Literal["COMPLETED"]
    source_gate_sha256: Sha256
    dataset_sha256: Sha256
    test_subset_sha256: Sha256
    evaluator_version: Literal["v0"]
    rows: list[MethodComparisonRow] = Field(min_length=5, max_length=5)
    created_at: datetime
    content_sha256: Sha256


class ReplayVerificationV0_2(Day2Model):
    schema_version: Literal["replay-verification-v0.2"]
    replay_id: str
    original_run_id: str
    status: Literal["PASSED"]
    original_prediction_byte_sha256: Sha256
    original_summary_byte_sha256: Sha256
    prediction_records_verified: int = Field(gt=0)
    parser_results_match: Literal[True]
    metrics_match: Literal[True]
    summary_matches: Literal[True]
    created_at: datetime
    content_sha256: Sha256


class PublishedAsset(Day2Model):
    adapter_id: str
    method_id: TrainableMethodId
    archive_name: str
    expected_url: str
    archive_sha256: Sha256
    archive_bytes: int = Field(gt=0)
    adapter_file_sha256s: dict[str, Sha256]
    downloaded_sha256: Sha256 | None
    verified: bool


class AdapterPublicationManifestV0_1(Day2Model):
    schema_version: Literal["adapter-publication-v0.1"]
    publication_id: str
    status: Literal["PACKAGED", "VERIFIED", "BLOCKED_BY_ADAPTER_PUBLICATION"]
    repository: Literal["faizanprofitpilot/InheritBench"]
    tag: Literal["day2-v0.1.0"]
    commit: FullCommitSha
    assets: list[PublishedAsset] = Field(min_length=3, max_length=3)
    sha256sums_sha256: Sha256
    verified_at: datetime | None
    created_at: datetime
    content_sha256: Sha256
