"""Strict schemas for Day 3 synthetic distillation evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inheritbench.artifacts.schemas import ArtifactReference, GenerationConfig
from inheritbench.config import FullCommitSha, ScenarioFamily, Sha256
from inheritbench.data.opsroute.schemas import EvaluationMetadata, OpsRouteInput
from inheritbench.day2.schemas import (
    AdapterReference,
    CheckpointScore,
    EvaluationBreakdown,
    MetricValue,
)
from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.metrics import AtomicMetrics
from inheritbench.evaluation.parser import ParserResult


class Day3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Day3ExperimentConfigV0_1(Day3Model):
    schema_version: Literal["day3-experiment-v0.1"]
    experiment_id: Literal["inheritbench-day3-v0.1"]
    dataset_directory: str
    task_config_path: str
    source_model_config_path: str
    target_model_config_path: str
    method_config_path: str
    pool_config_path: str
    day2_artifact_root: str
    artifact_root: str
    adapter_root: str
    seed: Literal[20260714]
    adversarial_evaluation: Literal[False]
    automatic_day4: Literal[False]


class SyntheticPoolConfigV0_1(Day3Model):
    schema_version: Literal["synthetic-pool-config-v0.1"]
    generator_version: Literal["day3-candidate-v0.1.0"]
    template_version: Literal["day3-synthetic-template-v0.1.0"]
    leakage_signature_version: Literal["day3-semantic-leakage-v0.1"]
    filter_version: Literal["day3-filter-v0.1.0"]
    selection_version: Literal["day3-synthetic-select-v0.1.0"]
    schedule_version: Literal["day3-synthetic-schedule-v0.1"]
    seed: Literal[20260714]
    initial_per_archetype: Literal[32]
    expansion_per_archetype: Literal[16]
    selected_per_archetype: Literal[14]
    maximum_collision_attempts: Literal[64]
    include_adversarial_text: Literal[False]
    target_processed_tokens: Literal[272643]


class Day3TrainingConfigV0_1(Day3Model):
    train_dtype: Literal["float32"]
    batch_size: Literal[1]
    gradient_accumulation_steps: Literal[4]
    gradient_clip_norm: float
    maximum_sequence_length: Literal[1024]
    learning_rate: float
    betas: list[float] = Field(min_length=2, max_length=2)
    epsilon: float
    weight_decay: float
    warmup_ratio: float
    lora_rank: Literal[8]
    lora_alpha: Literal[16]
    lora_dropout: float
    lora_bias: Literal["none"]
    lora_target_modules: list[Literal["q_proj", "k_proj", "v_proj", "o_proj"]] = Field(
        min_length=4, max_length=4
    )

    @field_validator("betas")
    @classmethod
    def validate_betas(cls, value: list[float]) -> list[float]:
        if value != [0.9, 0.999]:
            raise ValueError("betas must be exactly [0.9, 0.999]")
        return value

    @field_validator("lora_target_modules")
    @classmethod
    def validate_lora_targets(cls, value: list[str]) -> list[str]:
        if value != ["q_proj", "k_proj", "v_proj", "o_proj"]:
            raise ValueError("LoRA targets must be q_proj, k_proj, v_proj, o_proj in order")
        return value

    @model_validator(mode="after")
    def validate_locked_floats(self) -> Day3TrainingConfigV0_1:
        expected = {
            "gradient_clip_norm": 1.0,
            "epsilon": 1e-8,
            "weight_decay": 0.01,
            "warmup_ratio": 0.05,
            "lora_dropout": 0.05,
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValueError(f"{name} must be exactly {value}")
        if self.learning_rate not in {0.0002, 0.0001}:
            raise ValueError("learning_rate must be 2e-4 or the numerical correction 1e-4")
        return self


class Day3MethodConfigV0_1(Day3Model):
    schema_version: Literal["day3-method-config-v0.1"]
    method_id: Literal["target_synthetic_distillation"]
    model_config_path: str
    prompt_template_version: Literal["0.1.0"]
    parser_version: Literal["0.1.0"]
    evaluator_version: Literal["v0"]
    dataset_version: Literal["0.1.0"]
    seed: Literal[20260714]
    training: Day3TrainingConfigV0_1
    correction_attempt: Literal[0, 1] = 0
    correction_parent_run_id: str | None = None

    @model_validator(mode="after")
    def validate_correction(self) -> Day3MethodConfigV0_1:
        if self.correction_attempt == 0:
            if self.training.learning_rate != 0.0002 or self.correction_parent_run_id is not None:
                raise ValueError("primary Day 3 training must use learning rate 2e-4")
        elif self.training.learning_rate != 0.0001 or not self.correction_parent_run_id:
            raise ValueError("the only correction is a linked numerical restart at 1e-4")
        return self


class SyntheticCandidateInputV0_1(Day3Model):
    schema_version: Literal["synthetic-candidate-v0.1"]
    candidate_id: str
    phase: Literal["initial", "expansion"]
    task_id: Literal["opsroute"]
    task_version: Literal["0.1.0"]
    scenario_family: ScenarioFamily
    archetype: str
    template_version: Literal["day3-synthetic-template-v0.1.0"]
    template_id: str
    seed: int
    generation_attempt: int = Field(ge=0, lt=64)
    input: OpsRouteInput
    surface_sha256: Sha256
    input_content_sha256: Sha256
    semantic_leakage_sha256: Sha256
    record_sha256: Sha256


class SyntheticOracleRecordV0_1(Day3Model):
    schema_version: Literal["synthetic-oracle-v0.1"]
    candidate_id: str
    candidate_record_sha256: Sha256
    expected_contract: ActionContract
    evaluation_metadata: EvaluationMetadata
    content_sha256: Sha256


class CorpusDigest(Day3Model):
    path: str
    byte_sha256: Sha256
    records: int = Field(ge=0)


class LeakageAuditV0_1(Day3Model):
    schema_version: Literal["day3-leakage-audit-v0.1"]
    signature_version: Literal["day3-semantic-leakage-v0.1"]
    phase: Literal["initial", "expansion"]
    compared_corpora: list[CorpusDigest]
    candidate_count: int = Field(gt=0)
    unique_id_count: int = Field(gt=0)
    unique_surface_count: int = Field(gt=0)
    unique_input_content_count: int = Field(gt=0)
    unique_semantic_count: int = Field(gt=0)
    collision_rejections: int = Field(ge=0)
    zero_overlap: Literal[True]
    content_sha256: Sha256


class SyntheticPoolManifestV0_1(Day3Model):
    schema_version: Literal["synthetic-pool-v0.1"]
    pool_id: str
    phase: Literal["initial", "expansion"]
    status: Literal["FROZEN"]
    seed: Literal[20260714]
    generator_version: Literal["day3-candidate-v0.1.0"]
    template_version: Literal["day3-synthetic-template-v0.1.0"]
    candidate_count: int
    per_archetype: int
    candidate_artifact: ArtifactReference
    oracle_artifact: ArtifactReference
    leakage_artifact: ArtifactReference
    created_at: datetime
    content_sha256: Sha256


class TeacherAdapterVerificationV0_1(Day3Model):
    schema_version: Literal["teacher-adapter-verification-v0.1"]
    verification_id: str
    status: Literal["VERIFIED"]
    adapter_id: Literal["source_adapted_full-8242bcea6f327545"]
    release_tag: Literal["day2-v0.1.0"]
    release_verification_sha256: Sha256
    archive_url: str
    archive_sha256: Literal["8ee07058b71056bf7119582eb15f9fee4febf20b60f8942efa470be44b84a007"]
    adapter_file_sha256s: dict[str, Sha256]
    adapter_relative_path: str
    verified_at: datetime
    content_sha256: Sha256


class TeacherPredictionV0_1(Day3Model):
    schema_version: Literal["teacher-prediction-v0.1"]
    prediction_id: str
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    candidate_id: str
    candidate_record_sha256: Sha256
    pool_content_sha256: Sha256
    teacher_verification_sha256: Sha256
    model_id: str
    model_revision: FullCommitSha
    adapter_id: str
    resolved_device: str | None
    resolved_dtype: str | None
    prompt_sha256: Sha256 | None
    input_ids_sha256: Sha256 | None
    generation: GenerationConfig
    prompt_token_count: int | None = Field(default=None, ge=0)
    generated_token_count: int | None = Field(default=None, ge=0)
    finish_condition: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"] | None
    raw_output: str
    parser_result: ParserResult | None
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    errors: list[str]
    content_sha256: Sha256


class TeacherRunManifestV0_1(Day3Model):
    schema_version: Literal["teacher-run-v0.1"]
    run_id: str
    phase: Literal["initial", "expansion"]
    status: Literal["COMPLETED", "FAILED"]
    pool_id: str
    pool_content_sha256: Sha256
    teacher_verification_sha256: Sha256
    candidate_count: int
    attempts: int
    completed_outputs: int
    failed_outputs: int
    prompt_tokens: int
    completion_tokens: int
    teacher_generation_processed_tokens: int
    duration_seconds: float = Field(ge=0)
    prediction_artifact: ArtifactReference
    resumed_from_run_id: str | None
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


RejectionReason = Literal[
    "TEACHER_INFERENCE_FAILED",
    "EMPTY_OUTPUT",
    "NORMALIZED_NOT_STRICT",
    "INVALID_JSON",
    "PROSE_OR_MULTIPLE_OBJECTS",
    "SCHEMA_INVALID",
    "TARGET_SEQUENCE_TOO_LONG",
    "SAFETY_VIOLATION",
    "POLICY_CONTRACT_MISMATCH",
]


class SyntheticFilterRecordV0_1(Day3Model):
    schema_version: Literal["synthetic-filter-record-v0.1"]
    candidate_id: str
    candidate_record_sha256: Sha256
    teacher_prediction_sha256: Sha256
    oracle_sha256: Sha256
    accepted: bool
    selected_for_training: bool
    primary_rejection_reason: RejectionReason | None
    secondary_reasons: list[str]
    teacher_label: str | None
    target_sequence_tokens: int | None = Field(default=None, ge=0)
    selection_rank: Sha256
    metrics: AtomicMetrics | None
    content_sha256: Sha256


class SyntheticDatasetManifestV0_1(Day3Model):
    schema_version: Literal["synthetic-dataset-v0.1"]
    dataset_id: str
    status: Literal["COMPLETED", "NEEDS_EXPANSION", "FAILED"]
    failure_code: Literal["INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES"] | None
    pool_ids: list[str]
    pool_sha256s: list[Sha256]
    teacher_run_ids: list[str]
    teacher_run_sha256s: list[Sha256]
    filter_version: Literal["day3-filter-v0.1.0"]
    candidate_count: int
    accepted_count: int
    rejected_count: int
    selected_count: int
    selected_per_archetype: dict[str, int]
    accepted_artifact: ArtifactReference
    rejected_artifact: ArtifactReference
    selected_artifact: ArtifactReference
    created_at: datetime
    content_sha256: Sha256


class SyntheticTrainingExampleV0_1(Day3Model):
    schema_version: Literal["synthetic-training-example-v0.1"]
    candidate: SyntheticCandidateInputV0_1
    teacher_label: str
    teacher_prediction_sha256: Sha256
    oracle_sha256: Sha256


class Day3ScheduleItem(Day3Model):
    cursor: int = Field(ge=0)
    cycle: int = Field(ge=0)
    candidate_id: str
    sequence_tokens: int = Field(gt=0)


class SyntheticTrainingScheduleV0_1(Day3Model):
    schema_version: Literal["synthetic-training-schedule-v0.1"]
    schedule_id: str
    method_id: Literal["target_synthetic_distillation"]
    synthetic_dataset_sha256: Sha256
    tokenizer_id: str
    tokenizer_revision: FullCommitSha
    seed: Literal[20260714]
    target_processed_tokens: Literal[272643]
    processed_tokens: int = Field(gt=0, le=272643)
    residual_tokens: int = Field(ge=0)
    budget_ratio: float = Field(gt=0, le=1)
    unique_examples: Literal[224]
    example_exposures: int = Field(gt=0)
    optimizer_steps: int = Field(gt=0)
    warmup_steps: int = Field(gt=0)
    checkpoint_steps: list[int] = Field(min_length=3, max_length=3)
    token_counts: dict[str, int]
    per_example_exposures: dict[str, int]
    items: list[Day3ScheduleItem]
    content_sha256: Sha256


class Day3TrainingTelemetryPoint(Day3Model):
    optimizer_step: int = Field(gt=0)
    schedule_cursor: int = Field(ge=0)
    processed_tokens: int = Field(ge=0)
    loss: float
    learning_rate: float = Field(ge=0)
    gradient_norm: float = Field(ge=0)
    mps_current_allocated_bytes: int | None = Field(default=None, ge=0)
    mps_driver_allocated_bytes: int | None = Field(default=None, ge=0)


class Day3CheckpointManifestV0_1(Day3Model):
    schema_version: Literal["day3-checkpoint-v0.1"]
    checkpoint_id: str
    run_id: str
    method_id: Literal["target_synthetic_distillation"]
    optimizer_step: int
    schedule_cursor: int
    processed_tokens: int
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    synthetic_dataset_sha256: Sha256
    adapter_file_sha256s: dict[str, Sha256]
    trainer_state_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


class Day3TrainingRunManifestV0_1(Day3Model):
    schema_version: Literal["day3-training-run-v0.1"]
    run_id: str
    method_id: Literal["target_synthetic_distillation"]
    status: Literal["COMPLETED", "FAILED", "NOT_RUN"]
    failure_code: str | None
    failure_message: str | None
    resumed_from_run_id: str | None
    resumed_from_checkpoint_id: str | None
    model_id: str
    model_revision: FullCommitSha
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    synthetic_dataset_sha256: Sha256
    trainable_parameters: int = Field(ge=0)
    total_parameters: int = Field(ge=0)
    optimizer_steps_completed: int = Field(ge=0)
    processed_tokens: int = Field(ge=0)
    losses: list[float]
    telemetry: list[Day3TrainingTelemetryPoint]
    checkpoint_ids: list[str]
    duration_seconds: float = Field(ge=0)
    resolved_device: str | None
    resolved_dtype: str | None
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class Day3CheckpointDecisionV0_1(Day3Model):
    schema_version: Literal["day3-checkpoint-decision-v0.1"]
    decision_id: str
    method_id: Literal["target_synthetic_distillation"]
    status: Literal["SELECTED", "FAILED"]
    failure_code: Literal["NO_SAFETY_ELIGIBLE_CHECKPOINT"] | None
    training_run_id: str
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    synthetic_dataset_sha256: Sha256
    scores: list[CheckpointScore]
    selected_checkpoint_id: str | None
    selected_adapter: AdapterReference | None
    selection_rule: str
    created_at: datetime
    content_sha256: Sha256


class Day3PredictionRecordV0_1(Day3Model):
    schema_version: Literal["day3-prediction-v0.1"]
    prediction_id: str
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    method_id: Literal["target_synthetic_distillation"]
    adapter_id: str
    checkpoint_decision_sha256: Sha256
    synthetic_dataset_sha256: Sha256
    example_id: str
    split: Literal["validation", "test"]
    scenario_family: ScenarioFamily
    archetype: str
    model_id: str
    model_revision: FullCommitSha
    resolved_device: str | None
    resolved_dtype: str | None
    prompt_sha256: Sha256 | None
    input_ids_sha256: Sha256 | None
    generation: GenerationConfig
    prompt_token_count: int | None = Field(default=None, ge=0)
    generated_token_count: int | None = Field(default=None, ge=0)
    finish_condition: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"] | None
    raw_output: str
    parser_result: ParserResult | None
    expected_contract: ActionContract
    evaluation_metadata: EvaluationMetadata
    metrics: AtomicMetrics | None
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    errors: list[str]
    content_sha256: Sha256


class Day3EvaluationSummaryV0_1(Day3Model):
    schema_version: Literal["day3-evaluation-summary-v0.1"]
    run_id: str
    method_id: Literal["target_synthetic_distillation"]
    status: Literal["COMPLETED", "FAILED"]
    split: Literal["validation", "test"]
    prediction_counts: dict[str, int]
    aggregate_metrics: dict[str, MetricValue]
    parser_classifications: dict[str, int]
    breakdowns: dict[str, EvaluationBreakdown]
    run_errors: list[str]
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class Day3EvaluationRunManifestV0_1(Day3Model):
    schema_version: Literal["day3-evaluation-run-v0.1"]
    run_id: str
    method_id: Literal["target_synthetic_distillation"]
    status: Literal["COMPLETED", "FAILED"]
    split: Literal["validation", "test"]
    method_config_sha256: Sha256
    subset_sha256: Sha256
    dataset_sha256: Sha256
    synthetic_dataset_sha256: Sha256
    adapter: AdapterReference
    checkpoint_decision_sha256: Sha256
    generation: GenerationConfig
    prediction_artifact: ArtifactReference
    summary_artifact: ArtifactReference
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class Day3ReplayVerificationV0_1(Day3Model):
    schema_version: Literal["day3-replay-verification-v0.1"]
    replay_id: str
    kind: Literal["teacher", "filter", "schedule", "evaluation", "comparison"]
    original_artifact_id: str
    status: Literal["PASSED"]
    records_verified: int = Field(ge=0)
    byte_hashes_match: Literal[True]
    content_matches: Literal[True]
    duration_seconds: float = Field(ge=0)
    created_at: datetime
    content_sha256: Sha256


class Day3FailureAnalysisV0_1(Day3Model):
    schema_version: Literal["day3-failure-analysis-v0.1"]
    analysis_id: str
    teacher_rejections: dict[str, int]
    test_failure_categories: dict[str, int]
    breakdowns: dict[str, Any]
    source_artifact_sha256s: list[Sha256]
    created_at: datetime
    content_sha256: Sha256


class Day3ComparisonV0_1(Day3Model):
    schema_version: Literal["day3-comparison-v0.1"]
    comparison_id: str
    status: Literal["COMPLETED"]
    day2_comparison_sha256: Sha256
    dataset_sha256: Sha256
    test_subset_sha256: Sha256
    evaluator_version: Literal["v0"]
    rows: list[dict[str, Any]] = Field(min_length=6, max_length=6)
    accounting: dict[str, Any]
    failure_analysis_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


class Day3ScientificDecisionV0_1(Day3Model):
    schema_version: Literal["day3-scientific-decision-v0.1"]
    decision_id: str
    scientific_status: Literal[
        "SCIENTIFICALLY_COMPLETED", "SCIENTIFICALLY_FAILED", "SCIENTIFICALLY_BLOCKED"
    ]
    day4_gate: Literal["DAY4_UNBLOCKED", "DAY4_BLOCKED"]
    reason_code: str
    training_run_id: str | None
    checkpoint_decision_id: str | None
    test_run_id: str | None
    replay_id: str | None
    failure_analysis_id: str | None
    comparison_id: str | None
    evidence_sha256s: list[Sha256]
    created_at: datetime
    content_sha256: Sha256


class Day3PublishedAsset(Day3Model):
    adapter_id: str
    archive_name: str
    expected_url: str
    archive_sha256: Sha256
    archive_bytes: int = Field(gt=0)
    adapter_file_sha256s: dict[str, Sha256]
    downloaded_sha256: Sha256 | None
    verified: bool


class Day3PublicationManifestV0_1(Day3Model):
    schema_version: Literal["day3-publication-v0.1"]
    publication_id: str
    status: Literal["PACKAGED", "VERIFIED", "PUBLICATION_BLOCKED"]
    repository: Literal["faizanprofitpilot/InheritBench"]
    tag: Literal["day3-v0.1.0"]
    commit: FullCommitSha
    scientific_decision_sha256: Sha256
    asset: Day3PublishedAsset
    sha256sums_sha256: Sha256
    attempt: Literal[1, 2]
    error: str | None
    verified_at: datetime | None
    created_at: datetime
    content_sha256: Sha256


class Day3DistributionDecisionV0_1(Day3Model):
    schema_version: Literal["day3-distribution-decision-v0.1"]
    decision_id: str
    publication_status: Literal["PUBLISHED_VERIFIED", "PUBLICATION_BLOCKED", "NOT_ATTEMPTED"]
    scientific_decision_sha256: Sha256
    publication_sha256: Sha256 | None
    day4_gate: Literal["DAY4_UNBLOCKED", "DAY4_BLOCKED"]
    created_at: datetime
    content_sha256: Sha256
