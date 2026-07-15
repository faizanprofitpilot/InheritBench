"""Strict schemas for the isolated Day 3 distribution-matched recovery."""

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
from inheritbench.day3.schemas import Day3TrainingConfigV0_1, Day3TrainingTelemetryPoint
from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.metrics import AtomicMetrics
from inheritbench.evaluation.parser import ParserResult


class MatchedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class HistoricalArtifactExpectation(MatchedModel):
    relative_path: str
    byte_sha256: Sha256
    content_sha256: Sha256 | None


class MatchedExperimentConfigV0_1(MatchedModel):
    schema_version: Literal["day3-matched-experiment-v0.1"]
    experiment_id: Literal["inheritbench-day3-matched-v0.1"]
    method_id: Literal["target_synthetic_distillation_matched"]
    attempt_id: Literal["distribution_matched_attempt"]
    historical_attempt_id: Literal["independent_pool_attempt"]
    historical_reference_commit: FullCommitSha
    dataset_directory: str
    task_config_path: str
    source_model_config_path: str
    target_model_config_path: str
    method_config_path: str
    pool_config_path: str
    day2_artifact_root: str
    original_day3_artifact_root: Literal["artifacts/day3"]
    artifact_root: Literal["artifacts/day3-matched"]
    adapter_root: Literal["adapters/day3-matched"]
    release_tag: Literal["day3-matched-v0.1.0"]
    historical_artifacts: list[HistoricalArtifactExpectation] = Field(min_length=4)
    seed: Literal[20260714]
    adversarial_evaluation: Literal[False]
    automatic_day4: Literal[False]
    further_day3_attempts_allowed: Literal[False]


class IntegerBucket(MatchedModel):
    name: str
    minimum: int = Field(ge=0)
    maximum: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> IntegerBucket:
        if self.maximum < self.minimum:
            raise ValueError("bucket maximum must be at least its minimum")
        return self


class MatchedPoolConfigV0_1(MatchedModel):
    schema_version: Literal["day3-matched-pool-config-v0.1"]
    generator_version: Literal["day3-matched-candidate-v0.1.0"]
    template_version: Literal["opsroute-template-v0.1.0-matched"]
    distribution_fingerprint_version: Literal["day3-train-distribution-v0.1"]
    joint_stratum_version: Literal["day3-matched-strata-v0.1"]
    leakage_signature_version: Literal["day3-semantic-leakage-v0.1"]
    distribution_audit_version: Literal["day3-distribution-audit-v0.1"]
    filter_version: Literal["day3-filter-v0.1.0"]
    selection_version: Literal["day3-synthetic-select-v0.1.0"]
    schedule_version: Literal["day3-matched-synthetic-schedule-v0.1"]
    seed: Literal[20260714]
    initial_per_archetype: Literal[32]
    expansion_per_archetype: Literal[16]
    selected_per_archetype: Literal[14]
    maximum_collision_attempts: Literal[64]
    prompt_bucket_width: Literal[8]
    prompt_buckets: list[IntegerBucket] = Field(min_length=6, max_length=6)
    refund_amount_buckets: list[IntegerBucket]
    refund_age_buckets: list[IntegerBucket]
    subscription_balance_buckets: list[IntegerBucket]
    forbidden_boundary_values: dict[str, list[int]]
    apportionment: Literal["hamilton_largest_remainder"]
    include_adversarial_text: Literal[False]
    target_processed_tokens: Literal[272643]

    @field_validator("prompt_buckets")
    @classmethod
    def validate_prompt_buckets(cls, value: list[IntegerBucket]) -> list[IntegerBucket]:
        expected = [(344, 351), (352, 359), (360, 367), (368, 375), (376, 383), (384, 391)]
        if [(item.minimum, item.maximum) for item in value] != expected:
            raise ValueError(f"prompt buckets must be exactly {expected}")
        return value


class MatchedMethodConfigV0_1(MatchedModel):
    schema_version: Literal["day3-matched-method-config-v0.1"]
    method_id: Literal["target_synthetic_distillation_matched"]
    attempt_id: Literal["distribution_matched_attempt"]
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
    def validate_correction(self) -> MatchedMethodConfigV0_1:
        if self.correction_attempt == 0:
            if self.training.learning_rate != 0.0002 or self.correction_parent_run_id is not None:
                raise ValueError("primary matched training must use learning rate 2e-4")
        elif self.training.learning_rate != 0.0001 or not self.correction_parent_run_id:
            raise ValueError("the only correction is a linked numerical restart at 1e-4")
        return self


class HistoricalBaselineV0_1(MatchedModel):
    schema_version: Literal["day3-matched-historical-baseline-v0.1"]
    baseline_id: str
    attempt_id: Literal["independent_pool_attempt"]
    reference_commit: FullCommitSha
    files: list[HistoricalArtifactExpectation]
    original_day3_tree_sha256: Sha256
    original_candidate_count: Literal[768]
    original_accepted_count: Literal[59]
    original_selected_count: Literal[0]
    original_scientific_status: Literal["SCIENTIFICALLY_FAILED"]
    original_day4_gate: Literal["DAY4_BLOCKED"]
    created_at: datetime
    content_sha256: Sha256


class DistributionStratumV0_1(MatchedModel):
    stratum_sha256: Sha256
    scenario_family: ScenarioFamily
    archetype: str
    template_family: str
    prompt_bucket: str
    numeric_buckets: dict[str, str]
    categorical_facts: dict[str, Any]
    expected_decision: str
    expected_tool: str | None
    expected_approval_required: bool
    expected_policy_code: str
    expected_reason_code: str
    train_count: int = Field(gt=0)


class DistributionFingerprintV0_1(MatchedModel):
    schema_version: Literal["day3-train-distribution-v0.1"]
    fingerprint_id: str
    status: Literal["FROZEN"]
    train_records: Literal[224]
    dataset_sha256: Sha256
    train_byte_sha256: Sha256
    task_config_sha256: Sha256
    generator_source_sha256: Sha256
    tokenizer_id: str
    tokenizer_revision: FullCommitSha
    prompt_template_version: Literal["0.1.0"]
    prompt_bucket_width: Literal[8]
    strata: list[DistributionStratumV0_1]
    marginal_histograms: dict[str, dict[str, int]]
    forbidden_boundary_counts: dict[str, int]
    created_at: datetime
    content_sha256: Sha256


class MatchedCandidateInputV0_1(MatchedModel):
    schema_version: Literal["day3-matched-candidate-v0.1"]
    candidate_id: str
    attempt_id: Literal["distribution_matched_attempt"]
    phase: Literal["initial", "expansion"]
    task_id: Literal["opsroute"]
    task_version: Literal["0.1.0"]
    scenario_family: ScenarioFamily
    archetype: str
    source_stratum_sha256: Sha256
    template_version: Literal["opsroute-template-v0.1.0-matched"]
    template_id: str
    prompt_bucket: str
    numeric_buckets: dict[str, str]
    seed: int
    generation_attempt: int = Field(ge=0, lt=64)
    input: OpsRouteInput
    surface_sha256: Sha256
    input_content_sha256: Sha256
    semantic_leakage_sha256: Sha256
    record_sha256: Sha256

    @field_validator("candidate_id")
    @classmethod
    def validate_candidate_id(cls, value: str) -> str:
        if not value.startswith("matched_synthetic_opsroute_v010_"):
            raise ValueError("matched candidate IDs require the matched namespace")
        return value


class MatchedOracleRecordV0_1(MatchedModel):
    schema_version: Literal["day3-matched-oracle-v0.1"]
    candidate_id: str
    candidate_record_sha256: Sha256
    expected_contract: ActionContract
    evaluation_metadata: EvaluationMetadata
    content_sha256: Sha256


class CorpusDigestV0_1(MatchedModel):
    corpus_id: str
    path: str
    byte_sha256: Sha256
    content_sha256: Sha256 | None
    records_materialized: int = Field(ge=0)
    reference_only: bool


class DistributionMatchAuditV0_1(MatchedModel):
    schema_version: Literal["day3-distribution-audit-v0.1"]
    audit_id: str
    phase: Literal["initial", "expansion"]
    status: Literal["PASS", "FAIL"]
    fingerprint_sha256: Sha256
    candidate_count: int = Field(gt=0)
    expected_strata: dict[str, int]
    observed_strata: dict[str, int]
    expected_marginals: dict[str, dict[str, int]]
    observed_marginals: dict[str, dict[str, int]]
    support_violations: list[str]
    prompt_bucket_violations: list[str]
    boundary_violations: list[str]
    created_at: datetime
    content_sha256: Sha256


class MatchedLeakageAuditV0_1(MatchedModel):
    schema_version: Literal["day3-matched-leakage-audit-v0.1"]
    audit_id: str
    signature_version: Literal["day3-semantic-leakage-v0.1"]
    phase: Literal["initial", "expansion"]
    status: Literal["PASS", "FAIL"]
    compared_corpora: list[CorpusDigestV0_1]
    candidate_count: int = Field(gt=0)
    unique_id_count: int = Field(gt=0)
    unique_surface_count: int = Field(gt=0)
    unique_input_content_count: int = Field(gt=0)
    unique_record_count: int = Field(gt=0)
    unique_semantic_count: int = Field(gt=0)
    id_collisions: list[str]
    surface_collisions: list[str]
    input_content_collisions: list[str]
    record_collisions: list[str]
    semantic_collisions: list[str]
    collision_rejections: int = Field(ge=0)
    zero_overlap: bool
    created_at: datetime
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_status(self) -> MatchedLeakageAuditV0_1:
        collisions = (
            self.id_collisions
            + self.surface_collisions
            + self.input_content_collisions
            + self.record_collisions
            + self.semantic_collisions
        )
        if self.status == "PASS" and (collisions or not self.zero_overlap):
            raise ValueError("a passing leakage audit must prove zero overlap")
        return self


class MatchedPoolManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-pool-v0.1"]
    pool_id: str
    attempt_id: Literal["distribution_matched_attempt"]
    phase: Literal["initial", "expansion"]
    status: Literal["FROZEN"]
    seed: Literal[20260714]
    generator_version: Literal["day3-matched-candidate-v0.1.0"]
    candidate_count: int
    per_archetype: int
    fingerprint_sha256: Sha256
    distribution_audit_sha256: Sha256 | None
    leakage_audit_sha256: Sha256 | None
    candidate_artifact: ArtifactReference
    oracle_artifact: ArtifactReference
    created_at: datetime
    content_sha256: Sha256


class TeacherReferenceV0_1(MatchedModel):
    schema_version: Literal["day3-matched-teacher-reference-v0.1"]
    reference_id: str
    status: Literal["VERIFIED"]
    source_verification_path: str
    source_verification_sha256: Sha256
    adapter_id: Literal["source_adapted_full-8242bcea6f327545"]
    release_tag: Literal["day2-v0.1.0"]
    archive_sha256: Literal["8ee07058b71056bf7119582eb15f9fee4febf20b60f8942efa470be44b84a007"]
    adapter_file_sha256s: dict[str, Sha256]
    adapter_relative_path: str
    model_id: str
    model_revision: FullCommitSha
    tokenizer_id: str
    tokenizer_revision: FullCommitSha
    verified_at: datetime
    content_sha256: Sha256


class MatchedTeacherPredictionV0_1(MatchedModel):
    schema_version: Literal["day3-matched-teacher-prediction-v0.1"]
    prediction_id: str
    run_id: str
    attempt_id: Literal["distribution_matched_attempt"]
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    candidate_id: str
    candidate_record_sha256: Sha256
    pool_content_sha256: Sha256
    distribution_audit_sha256: Sha256
    leakage_audit_sha256: Sha256
    teacher_reference_sha256: Sha256
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


class MatchedTeacherRunManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-teacher-run-v0.1"]
    run_id: str
    attempt_id: Literal["distribution_matched_attempt"]
    phase: Literal["initial", "expansion"]
    status: Literal["COMPLETED", "FAILED"]
    pool_id: str
    pool_content_sha256: Sha256
    fingerprint_sha256: Sha256
    distribution_audit_sha256: Sha256
    leakage_audit_sha256: Sha256
    teacher_reference_sha256: Sha256
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


MatchedRejectionReason = Literal[
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


class MatchedFilterDecisionV0_1(MatchedModel):
    schema_version: Literal["day3-matched-filter-record-v0.1"]
    candidate_id: str
    candidate_record_sha256: Sha256
    teacher_prediction_sha256: Sha256
    oracle_sha256: Sha256
    accepted: bool
    selected_for_training: bool
    primary_rejection_reason: MatchedRejectionReason | None
    secondary_reasons: list[str]
    teacher_label: str | None
    target_sequence_tokens: int | None = Field(default=None, ge=0)
    selection_rank: Sha256
    metrics: AtomicMetrics | None
    content_sha256: Sha256


class MatchedTrainingExampleV0_1(MatchedModel):
    schema_version: Literal["day3-matched-training-example-v0.1"]
    candidate: MatchedCandidateInputV0_1
    teacher_label: str
    teacher_prediction_sha256: Sha256
    oracle_sha256: Sha256


class MatchedSyntheticDatasetManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-synthetic-dataset-v0.1"]
    dataset_id: str
    attempt_id: Literal["distribution_matched_attempt"]
    status: Literal["COMPLETED", "NEEDS_EXPANSION", "TERMINAL_NEGATIVE"]
    failure_code: Literal["INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES"] | None
    pool_ids: list[str]
    pool_sha256s: list[Sha256]
    teacher_run_ids: list[str]
    teacher_run_sha256s: list[Sha256]
    distribution_audit_sha256s: list[Sha256]
    leakage_audit_sha256s: list[Sha256]
    filter_version: Literal["day3-filter-v0.1.0"]
    candidate_count: int
    accepted_count: int
    rejected_count: int
    selected_count: int
    selected_per_archetype: dict[str, int]
    original_labels_directly_used_by_target: Literal[0]
    original_labels_used_upstream_to_train_teacher: Literal[224]
    accepted_artifact: ArtifactReference
    rejected_artifact: ArtifactReference
    selected_artifact: ArtifactReference
    created_at: datetime
    content_sha256: Sha256


class MatchedScheduleItem(MatchedModel):
    cursor: int = Field(ge=0)
    cycle: int = Field(ge=0)
    candidate_id: str
    sequence_tokens: int = Field(gt=0)


class MatchedTrainingScheduleV0_1(MatchedModel):
    schema_version: Literal["day3-matched-training-schedule-v0.1"]
    schedule_id: str
    method_id: Literal["target_synthetic_distillation_matched"]
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
    items: list[MatchedScheduleItem]
    content_sha256: Sha256


class MatchedCheckpointManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-checkpoint-v0.1"]
    checkpoint_id: str
    run_id: str
    method_id: Literal["target_synthetic_distillation_matched"]
    optimizer_step: int
    schedule_cursor: int
    processed_tokens: int
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    synthetic_dataset_sha256: Sha256
    fingerprint_sha256: Sha256
    adapter_file_sha256s: dict[str, Sha256]
    trainer_state_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


class MatchedTrainingRunManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-training-run-v0.1"]
    run_id: str
    attempt_id: Literal["distribution_matched_attempt"]
    method_id: Literal["target_synthetic_distillation_matched"]
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
    fingerprint_sha256: Sha256
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


class MatchedCheckpointDecisionV0_1(MatchedModel):
    schema_version: Literal["day3-matched-checkpoint-decision-v0.1"]
    decision_id: str
    method_id: Literal["target_synthetic_distillation_matched"]
    status: Literal["SELECTED", "TERMINAL_NEGATIVE"]
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


class MatchedPredictionRecordV0_1(MatchedModel):
    schema_version: Literal["day3-matched-prediction-v0.1"]
    prediction_id: str
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    method_id: Literal["target_synthetic_distillation_matched"]
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


class MatchedEvaluationSummaryV0_1(MatchedModel):
    schema_version: Literal["day3-matched-evaluation-summary-v0.1"]
    run_id: str
    method_id: Literal["target_synthetic_distillation_matched"]
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


class MatchedEvaluationRunManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-evaluation-run-v0.1"]
    run_id: str
    method_id: Literal["target_synthetic_distillation_matched"]
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


class MatchedFailureAnalysisV0_1(MatchedModel):
    schema_version: Literal["day3-matched-failure-analysis-v0.1"]
    analysis_id: str
    teacher_rejections: dict[str, int]
    test_failure_categories: dict[str, int]
    breakdowns: dict[str, Any]
    source_artifact_sha256s: list[Sha256]
    created_at: datetime
    content_sha256: Sha256


class SyntheticAttemptComparisonV0_1(MatchedModel):
    schema_version: Literal["day3-synthetic-attempt-comparison-v0.1"]
    comparison_id: str
    status: Literal["COMPLETED"]
    rows: list[dict[str, Any]] = Field(min_length=2, max_length=2)
    historical_baseline_sha256: Sha256
    matched_dataset_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


class MatchedMethodComparisonV0_1(MatchedModel):
    schema_version: Literal["day3-matched-method-comparison-v0.1"]
    comparison_id: str
    status: Literal["COMPLETED"]
    day2_comparison_sha256: Sha256
    attempt_comparison_sha256: Sha256
    dataset_sha256: Sha256
    test_subset_sha256: Sha256
    evaluator_version: Literal["v0"]
    rows: list[dict[str, Any]] = Field(min_length=6, max_length=6)
    accounting: dict[str, Any]
    failure_analysis_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


ReplayKind = Literal[
    "fingerprint",
    "distribution",
    "leakage",
    "teacher",
    "filter",
    "schedule",
    "training",
    "evaluation",
    "failure_analysis",
    "attempt_comparison",
    "method_comparison",
    "recovery_decision",
]


class MatchedReplayVerificationV0_1(MatchedModel):
    schema_version: Literal["day3-matched-replay-verification-v0.1"]
    replay_id: str
    kind: ReplayKind
    original_artifact_id: str
    status: Literal["PASSED"]
    records_verified: int = Field(ge=0)
    byte_hashes_match: Literal[True]
    content_matches: Literal[True]
    duration_seconds: float = Field(ge=0)
    created_at: datetime
    content_sha256: Sha256


class Day3RecoveryDecisionV0_1(MatchedModel):
    schema_version: Literal["day3-recovery-decision-v0.1"]
    decision_id: str
    recovery_status: Literal[
        "RECOVERY_SCIENTIFICALLY_COMPLETED",
        "RECOVERY_TERMINAL_NEGATIVE",
        "RECOVERY_BLOCKED",
    ]
    day4_gate: Literal[
        "DAY4_UNBLOCKED",
        "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT",
        "DAY4_BLOCKED",
    ]
    reason_code: str
    dataset_id: str | None
    training_run_id: str | None
    checkpoint_decision_id: str | None
    test_run_id: str | None
    attempt_comparison_id: str
    method_comparison_id: str | None
    evidence_sha256s: list[Sha256]
    further_day3_attempts_allowed: Literal[False]
    automatic_day4_started: Literal[False]
    created_at: datetime
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_gate(self) -> Day3RecoveryDecisionV0_1:
        expected = {
            "RECOVERY_SCIENTIFICALLY_COMPLETED": "DAY4_UNBLOCKED",
            "RECOVERY_TERMINAL_NEGATIVE": ("DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT"),
            "RECOVERY_BLOCKED": "DAY4_BLOCKED",
        }
        if self.day4_gate != expected[self.recovery_status]:
            raise ValueError("recovery status and Day 4 gate disagree")
        return self


class MatchedPublishedAsset(MatchedModel):
    adapter_id: str
    archive_name: str
    expected_url: str
    archive_sha256: Sha256
    archive_bytes: int = Field(gt=0)
    adapter_file_sha256s: dict[str, Sha256]
    downloaded_sha256: Sha256 | None
    verified: bool


class MatchedPublicationManifestV0_1(MatchedModel):
    schema_version: Literal["day3-matched-publication-v0.1"]
    publication_id: str
    status: Literal["PACKAGED", "PUBLISHED_VERIFIED", "PUBLICATION_BLOCKED"]
    repository: Literal["faizanprofitpilot/InheritBench"]
    tag: Literal["day3-matched-v0.1.0"]
    commit: FullCommitSha
    recovery_decision_sha256: Sha256
    asset: MatchedPublishedAsset
    sha256sums_sha256: Sha256
    attempt: Literal[1, 2]
    error: str | None
    verified_at: datetime | None
    created_at: datetime
    content_sha256: Sha256


class MatchedDistributionDecisionV0_1(MatchedModel):
    schema_version: Literal["day3-matched-distribution-decision-v0.1"]
    decision_id: str
    publication_status: Literal["PUBLISHED_VERIFIED", "PUBLICATION_BLOCKED", "NOT_ATTEMPTED"]
    recovery_decision_sha256: Sha256
    publication_sha256: Sha256 | None
    day4_gate: Literal[
        "DAY4_UNBLOCKED",
        "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT",
        "DAY4_BLOCKED",
    ]
    created_at: datetime
    content_sha256: Sha256
