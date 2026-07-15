"""Strict schemas for Phase 3B anchored behavioral transfer."""

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


class Phase3BModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class HistoricalArtifactExpectation(Phase3BModel):
    relative_path: str
    byte_sha256: Sha256
    content_sha256: Sha256 | None


class Phase3BExperimentConfigV0_1(Phase3BModel):
    schema_version: Literal["phase3b-experiment-v0.1"]
    experiment_id: Literal["inheritbench-phase3b-anchored-v0.1"]
    method_id: Literal["target_hybrid_anchored_distillation_10"]
    attempt_id: Literal["phase3b_anchored_behavioral_transfer"]
    method_classification: Literal["HYBRID_SYNTHETIC_PLUS_TARGETED_ORIGINAL_ANCHORS"]
    historical_reference_commit: Literal["7283bfe22903ffc554c1f5ab210dea105df68b2b"]
    dataset_directory: str
    task_config_path: str
    source_model_config_path: str
    target_model_config_path: str
    method_config_path: str
    confirmatory_config_path: str
    day2_artifact_root: Literal["artifacts/day2"]
    independent_day3_root: Literal["artifacts/day3"]
    matched_day3_root: Literal["artifacts/day3-matched"]
    artifact_root: Literal["artifacts/phase3b"]
    adapter_root: Literal["adapters/phase3b"]
    release_tag: Literal["phase3b-anchored-v0.1.0"]
    seed: Literal[20260714]
    run_legacy_exploratory_test: Literal[True]
    automatic_day4: Literal[False]
    further_phase3b_variants_allowed: Literal[False]
    historical_artifacts: list[HistoricalArtifactExpectation] = Field(min_length=8)


class HybridMethodConfigV0_1(Phase3BModel):
    schema_version: Literal["phase3b-hybrid-method-v0.1"]
    method_id: Literal["target_hybrid_anchored_distillation_10"]
    attempt_id: Literal["phase3b_anchored_behavioral_transfer"]
    model_config_path: str
    prompt_template_version: Literal["0.1.0"]
    parser_version: Literal["0.1.0"]
    evaluator_version: Literal["v0"]
    dataset_version: Literal["0.1.0"]
    seed: Literal[20260714]
    synthetic_examples: Literal[214]
    original_anchor_examples: Literal[10]
    total_unique_examples: Literal[224]
    target_processed_tokens: Literal[272643]
    training: Day3TrainingConfigV0_1
    correction_attempt: Literal[0, 1] = 0
    correction_parent_run_id: str | None = None

    @model_validator(mode="after")
    def validate_correction(self) -> HybridMethodConfigV0_1:
        if self.correction_attempt == 0:
            if self.training.learning_rate != 0.0002 or self.correction_parent_run_id is not None:
                raise ValueError("primary Phase 3B training must use learning rate 2e-4")
        elif self.training.learning_rate != 0.0001 or not self.correction_parent_run_id:
            raise ValueError("the only correction is a linked numerical restart at 1e-4")
        return self


class IntegerBucket(Phase3BModel):
    name: str
    minimum: int = Field(ge=0)
    maximum: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> IntegerBucket:
        if self.maximum < self.minimum:
            raise ValueError("bucket maximum must be at least its minimum")
        return self


class ConfirmatorySplitConfigV0_1(Phase3BModel):
    schema_version: Literal["phase3b-confirmatory-config-v0.1"]
    generator_version: Literal["phase3b-confirmatory-generator-v0.1"]
    validation_namespace: Literal["phase3b-confirmatory-validation-v0.1"]
    test_namespace: Literal["phase3b-confirmatory-test-v0.1"]
    seed: Literal[20260714]
    validation_per_archetype: Literal[2]
    test_per_archetype: Literal[4]
    validation_count: Literal[32]
    test_count: Literal[64]
    maximum_collision_attempts: Literal[64]
    leakage_signature_version: Literal["day3-semantic-leakage-v0.1"]
    maximum_prompt_tokens: Literal[1024]
    use_adversarial_text: Literal[False]
    boundary_rule: Literal["generic_two_sided_policy_boundary_v0.1"]
    apportionment: Literal["hamilton_largest_remainder"]
    refund_amount_buckets: list[IntegerBucket]
    refund_age_buckets: list[IntegerBucket]
    subscription_balance_buckets: list[IntegerBucket]
    forbidden_boundary_values: dict[str, list[int]]

    @field_validator("forbidden_boundary_values")
    @classmethod
    def validate_forbidden_boundaries(cls, value: dict[str, list[int]]) -> dict[str, list[int]]:
        expected = {
            "amount_minor": [4999, 5000, 5001],
            "payment_age_days": [30, 31],
            "balance_minor": [9999, 10000, 10001],
        }
        if value != expected:
            raise ValueError(f"forbidden boundaries must be exactly {expected}")
        return value


class Phase3BHistoricalBaselineV0_1(Phase3BModel):
    schema_version: Literal["phase3b-historical-baseline-v0.1"]
    baseline_id: str
    status: Literal["PASS"]
    historical_reference_commit: FullCommitSha
    files: list[HistoricalArtifactExpectation]
    matched_candidate_count: Literal[768]
    matched_accepted_count: Literal[719]
    matched_rejected_count: Literal[49]
    duplicate_auto_candidate_count: Literal[48]
    duplicate_auto_accepted_count: Literal[4]
    duplicate_auto_policy_mismatch_count: Literal[44]
    duplicate_auto_uniform_wrong_contract_count: Literal[44]
    diagnosis_verdict: Literal["SOURCE_TEACHER_CAPABILITY_BLIND_SPOT_CONFIRMED"]
    generator_policy_verdict: Literal["GENERATOR_POLICY_CONSISTENCY_CONFIRMED"]
    original_validation_previously_inspected: Literal[True]
    original_test_previously_inspected: Literal[True]
    created_at: datetime
    content_sha256: Sha256


class HybridSelectionPolicyV0_1(Phase3BModel):
    schema_version: Literal["phase3b-selection-policy-v0.1"]
    synthetic_rank_namespace: Literal["phase3b-synthetic-selection-v0.1"]
    anchor_rank_namespace: Literal["phase3b-anchor-selection-v0.1"]
    group_key: Literal["scenario_family+archetype"]
    selected_per_group: Literal[14]
    blindspot_family: Literal["refund_policy_routing"]
    blindspot_archetype: Literal["duplicate_auto_refund"]
    blindspot_synthetic_count: Literal[4]
    anchor_count: Literal[10]
    synthetic_count: Literal[214]
    total_count: Literal[224]
    performance_fields_permitted: Literal[False]


class OriginalAnchorSelectionV0_1(Phase3BModel):
    schema_version: Literal["phase3b-anchor-selection-v0.1"]
    selection_id: str
    policy_sha256: Sha256
    train_artifact_sha256: Sha256
    eligible_ids: list[str] = Field(min_length=14, max_length=14)
    ranks: dict[str, Sha256]
    selected_ids: list[str] = Field(min_length=10, max_length=10)
    unselected_ids: list[str] = Field(min_length=4, max_length=4)
    selected_records_artifact: ArtifactReference
    created_at: datetime
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_partition(self) -> OriginalAnchorSelectionV0_1:
        if set(self.eligible_ids) != set(self.selected_ids) | set(self.unselected_ids):
            raise ValueError("anchor selected/unselected IDs must partition eligible IDs")
        if set(self.selected_ids) & set(self.unselected_ids):
            raise ValueError("anchor selected and unselected IDs must be disjoint")
        if set(self.ranks) != set(self.eligible_ids):
            raise ValueError("anchor ranks must cover every eligible ID")
        return self


class SyntheticSelectionV0_1(Phase3BModel):
    schema_version: Literal["phase3b-synthetic-selection-v0.1"]
    selection_id: str
    policy_sha256: Sha256
    matched_dataset_sha256: Sha256
    matched_filter_sha256: Sha256
    accepted_pool_count: Literal[719]
    selected_ids: list[str] = Field(min_length=214, max_length=214)
    selected_by_group: dict[str, list[str]]
    selection_ranks: dict[str, Sha256]
    blindspot_selected_ids: list[str] = Field(min_length=4, max_length=4)
    teacher_label_sha256s: dict[str, Sha256]
    created_at: datetime
    content_sha256: Sha256


class HybridTrainingRecordV0_1(Phase3BModel):
    schema_version: Literal["phase3b-training-record-v0.1"]
    training_record_id: str
    scenario_family: ScenarioFamily
    archetype: str
    input: OpsRouteInput
    label_origin: Literal["teacher_output", "original_anchor"]
    assistant_label: str
    assistant_label_sha256: Sha256
    parent_artifact_path: str
    parent_artifact_sha256: Sha256
    source_record_id: str
    source_record_sha256: Sha256
    selection_rank: Sha256
    selection_sha256: Sha256
    content_sha256: Sha256


class HybridLabelAccounting(Phase3BModel):
    original_labels_directly_used_by_target: Literal[10]
    original_labels_used_upstream_to_train_teacher: Literal[224]
    original_labeled_records_used_to_design_distribution: Literal[224]
    synthetic_labels_used_by_target: Literal[214]
    original_anchor_labels_used_by_target: Literal[10]
    total_unique_target_training_examples: Literal[224]
    synthetic_candidates_previously_generated: Literal[768]
    accepted_synthetic_pool_available: Literal[719]
    selected_synthetic_examples: Literal[214]
    selected_original_anchor_examples: Literal[10]
    teacher_generation_processed_tokens: Literal[323601]
    teacher_generation_duration_seconds: float
    source_teacher_training_tokens: Literal[379768]
    source_teacher_training_duration_seconds: float

    @model_validator(mode="after")
    def validate_frozen_durations(self) -> HybridLabelAccounting:
        if self.teacher_generation_duration_seconds != 1122.69:
            raise ValueError("teacher generation duration must match frozen evidence")
        if self.source_teacher_training_duration_seconds != 437.86:
            raise ValueError("source teacher duration must match frozen evidence")
        return self


class HybridDatasetManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-hybrid-dataset-v0.1"]
    dataset_id: str
    status: Literal["FROZEN"]
    synthetic_selection_sha256: Sha256
    anchor_selection_sha256: Sha256
    records_artifact: ArtifactReference
    synthetic_count: Literal[214]
    anchor_count: Literal[10]
    total_count: Literal[224]
    family_counts: dict[ScenarioFamily, int]
    group_counts: dict[str, int]
    accounting: HybridLabelAccounting
    created_at: datetime
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_counts(self) -> HybridDatasetManifestV0_1:
        if self.family_counts != {
            "refund_policy_routing": 112,
            "subscription_cancellation_retention": 112,
        }:
            raise ValueError("hybrid dataset must contain 112 examples per family")
        if len(self.group_counts) != 16 or set(self.group_counts.values()) != {14}:
            raise ValueError("hybrid dataset must contain 14 examples in all 16 groups")
        return self


class ConfirmatoryExampleV0_1(Phase3BModel):
    schema_version: Literal["phase3b-confirmatory-example-v0.1"]
    example_id: str
    split: Literal["confirmatory_validation", "confirmatory_test"]
    scenario_family: ScenarioFamily
    archetype: str
    slot: int = Field(ge=0)
    generation_attempt: int = Field(ge=0, lt=64)
    seed: int
    template_id: str
    input: OpsRouteInput
    prompt_token_count: int = Field(gt=0, le=1024)
    surface_sha256: Sha256
    input_content_sha256: Sha256
    semantic_leakage_sha256: Sha256
    record_sha256: Sha256


class ConfirmatoryOracleRecordV0_1(Phase3BModel):
    schema_version: Literal["phase3b-confirmatory-oracle-v0.1"]
    example_id: str
    example_record_sha256: Sha256
    expected_contract: ActionContract
    evaluation_metadata: EvaluationMetadata
    content_sha256: Sha256


class CorpusDigestV0_1(Phase3BModel):
    corpus_id: str
    path: str
    byte_sha256: Sha256
    content_sha256: Sha256 | None
    records_materialized: int = Field(ge=0)
    reference_only: bool


class ConfirmatorySplitManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-confirmatory-split-v0.1"]
    split_id: str
    split: Literal["confirmatory_validation", "confirmatory_test"]
    status: Literal["FROZEN"]
    example_count: Literal[32, 64]
    per_archetype_count: Literal[2, 4]
    family_counts: dict[ScenarioFamily, int]
    inputs_artifact: ArtifactReference
    oracle_artifact: ArtifactReference
    example_ids_sha256: Sha256
    generator_config_sha256: Sha256
    created_before_training: Literal[True]
    created_at: datetime
    content_sha256: Sha256


class ConfirmatoryBundleManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-confirmatory-bundle-v0.1"]
    bundle_id: str
    status: Literal["FROZEN"]
    validation_sha256: Sha256
    test_sha256: Sha256
    validation_artifact: ArtifactReference
    test_artifact: ArtifactReference
    generator_config_sha256: Sha256
    created_at: datetime
    content_sha256: Sha256


class ConfirmatoryLeakageAuditV0_1(Phase3BModel):
    schema_version: Literal["phase3b-confirmatory-leakage-v0.1"]
    audit_id: str
    status: Literal["PASS", "FAIL"]
    validation_sha256: Sha256
    test_sha256: Sha256
    compared_corpora: list[CorpusDigestV0_1]
    id_collisions: list[str]
    surface_collisions: list[str]
    input_content_collisions: list[str]
    record_collisions: list[str]
    semantic_collisions: list[str]
    rejected_generation_attempts: int = Field(ge=0)
    boundary_coverage: dict[str, int]
    support_violations: list[str]
    created_at: datetime
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_pass(self) -> ConfirmatoryLeakageAuditV0_1:
        collisions = (
            self.id_collisions
            + self.surface_collisions
            + self.input_content_collisions
            + self.record_collisions
            + self.semantic_collisions
        )
        if self.status == "PASS" and (collisions or self.support_violations):
            raise ValueError("a passing confirmatory audit must have no collisions or violations")
        return self


class HybridScheduleItem(Phase3BModel):
    cursor: int = Field(ge=0)
    cycle: int = Field(ge=0)
    training_record_id: str
    label_origin: Literal["teacher_output", "original_anchor"]
    sequence_tokens: int = Field(gt=0)


class HybridTrainingScheduleV0_1(Phase3BModel):
    schema_version: Literal["phase3b-hybrid-schedule-v0.1"]
    schedule_id: str
    hybrid_dataset_sha256: Sha256
    tokenizer_id: str
    tokenizer_revision: FullCommitSha
    seed: Literal[20260714]
    ordering_namespace: Literal["phase3b-hybrid-schedule-v0.1"]
    target_processed_tokens: Literal[272643]
    processed_tokens: int = Field(gt=0, le=272643)
    residual_tokens: int = Field(ge=0)
    budget_ratio: float = Field(gt=0, le=1)
    unique_examples: Literal[224]
    total_exposures: int = Field(gt=0)
    optimizer_steps: int = Field(gt=0)
    warmup_steps: int = Field(gt=0)
    checkpoint_steps: list[int] = Field(min_length=3, max_length=3)
    token_counts: dict[str, int]
    exposure_counts_by_record: dict[str, int]
    exposure_counts_by_origin: dict[str, int]
    items: list[HybridScheduleItem]
    created_at: datetime
    content_sha256: Sha256


class Phase3BPreregistrationAttestationV0_1(Phase3BModel):
    schema_version: Literal["phase3b-preregistration-attestation-v0.1"]
    attestation_id: str
    preregistration_commit: FullCommitSha
    worktree_clean: Literal[True]
    tracked_diff_sha256: None
    experiment_config_sha256: Sha256
    method_config_sha256: Sha256
    confirmatory_config_sha256: Sha256
    baseline_sha256: Sha256
    synthetic_selection_sha256: Sha256
    anchor_selection_sha256: Sha256
    hybrid_dataset_sha256: Sha256
    confirmatory_validation_sha256: Sha256
    confirmatory_test_sha256: Sha256
    confirmatory_leakage_audit_sha256: Sha256
    training_schedule_sha256: Sha256
    required_paths_in_commit: list[str] = Field(min_length=10)
    git_object_verification_passed: Literal[True]
    created_at: datetime
    content_sha256: Sha256


class Phase3BLineageV0_1(Phase3BModel):
    historical_reference_commit: FullCommitSha
    preregistration_commit: FullCommitSha
    preregistration_attestation_sha256: Sha256
    original_dataset_sha256: Sha256
    train_byte_sha256: Sha256
    task_config_sha256: Sha256
    source_teacher_adapter_sha256: Sha256
    source_teacher_release_verification_sha256: Sha256
    matched_teacher_run_sha256s: tuple[Sha256, Sha256]
    matched_accepted_dataset_sha256: Sha256
    synthetic_selection_sha256: Sha256
    anchor_selection_sha256: Sha256
    hybrid_dataset_sha256: Sha256
    confirmatory_validation_sha256: Sha256
    confirmatory_test_sha256: Sha256
    confirmatory_leakage_audit_sha256: Sha256
    training_schedule_sha256: Sha256
    target_model_revision: FullCommitSha
    checkpoint_decision_sha256: Sha256 | None
    prompt_version: Literal["0.1.0"]
    parser_version: Literal["0.1.0"]
    evaluator_version: Literal["v0"]


class Phase3BCheckpointManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-checkpoint-v0.1"]
    checkpoint_id: str
    run_id: str
    method_id: Literal["target_hybrid_anchored_distillation_10"]
    optimizer_step: int = Field(gt=0)
    schedule_cursor: int = Field(gt=0)
    processed_tokens: int = Field(gt=0)
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    hybrid_dataset_sha256: Sha256
    adapter_file_sha256s: dict[str, Sha256]
    trainer_state_sha256: Sha256
    lineage: Phase3BLineageV0_1
    created_at: datetime
    content_sha256: Sha256


class Phase3BTrainingManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-training-run-v0.1"]
    run_id: str
    method_id: Literal["target_hybrid_anchored_distillation_10"]
    status: Literal["COMPLETED", "FAILED", "NOT_RUN"]
    failure_code: str | None
    failure_message: str | None
    resumed_from_run_id: str | None
    resumed_from_checkpoint_id: str | None
    correction: Literal["NONE", "NUMERICAL_LR_1E_4"]
    fresh_base_verified: bool
    model_id: Literal["allenai/OLMo-2-0425-1B-Instruct"]
    model_revision: FullCommitSha
    adapter_inputs_loaded: list[str]
    method_config_sha256: Sha256
    hybrid_dataset_sha256: Sha256
    schedule_sha256: Sha256
    optimizer_steps_completed: int = Field(ge=0)
    processed_tokens: int = Field(ge=0)
    trainable_parameters: int = Field(ge=0)
    total_parameters: int = Field(ge=0)
    losses: list[float]
    telemetry: list[Day3TrainingTelemetryPoint]
    checkpoint_ids: list[str]
    duration_seconds: float = Field(ge=0)
    resolved_device: str | None
    resolved_dtype: str | None
    lineage: Phase3BLineageV0_1
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class Phase3BCheckpointDecisionV0_1(Phase3BModel):
    schema_version: Literal["phase3b-checkpoint-decision-v0.1"]
    decision_id: str
    method_id: Literal["target_hybrid_anchored_distillation_10"]
    status: Literal["SELECTED", "NO_SAFETY_ELIGIBLE_CHECKPOINT"]
    failure_code: Literal["NO_SAFETY_ELIGIBLE_CHECKPOINT"] | None
    training_run_id: str
    confirmatory_validation_sha256: Sha256
    method_config_sha256: Sha256
    schedule_sha256: Sha256
    hybrid_dataset_sha256: Sha256
    scores: list[CheckpointScore]
    selected_checkpoint_id: str | None
    selected_adapter: AdapterReference | None
    fresh_base_reload_verified: bool
    selection_rule: Literal["semantic,strict,abstention,approval,argument_f1,loss,earliest"]
    lineage: Phase3BLineageV0_1
    created_at: datetime
    content_sha256: Sha256


Phase3BSystemId = Literal[
    "source_base_supporting",
    "source_adapted_full",
    "target_untouched",
    "target_full_retrain",
    "target_limited_retrain_10pct",
    "target_hybrid_anchored_distillation_10",
]
Phase3BSplit = Literal["confirmatory_validation", "confirmatory_test", "exploratory_legacy_test"]


class Phase3BPredictionRecordV0_1(Phase3BModel):
    schema_version: Literal["phase3b-prediction-v0.1"]
    prediction_id: str
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    system_id: Phase3BSystemId
    split: Phase3BSplit
    adapter_id: str | None
    checkpoint_decision_sha256: Sha256 | None
    example_id: str
    scenario_family: ScenarioFamily
    archetype: str
    model_id: str
    model_revision: FullCommitSha
    resolved_device: str | None
    resolved_dtype: str | None
    prompt_sha256: Sha256 | None
    input_ids_sha256: Sha256 | None
    generation: GenerationConfig
    raw_output: str
    parser_result: ParserResult | None
    expected_contract: ActionContract
    evaluation_metadata: EvaluationMetadata
    metrics: AtomicMetrics | None
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    errors: list[str]
    lineage: Phase3BLineageV0_1
    content_sha256: Sha256


class Phase3BEvaluationSummaryV0_1(Phase3BModel):
    schema_version: Literal["phase3b-evaluation-summary-v0.1"]
    run_id: str
    system_id: Phase3BSystemId
    status: Literal["COMPLETED", "FAILED"]
    split: Phase3BSplit
    prediction_counts: dict[str, int]
    aggregate_metrics: dict[str, MetricValue]
    parser_classifications: dict[str, int]
    breakdowns: dict[str, EvaluationBreakdown]
    run_errors: list[str]
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class Phase3BEvaluationManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-evaluation-run-v0.1"]
    run_id: str
    system_id: Phase3BSystemId
    split: Phase3BSplit
    status: Literal["COMPLETED", "FAILED"]
    expected_predictions: Literal[32, 64]
    terminal_predictions: int = Field(ge=0)
    split_sha256: Sha256
    oracle_sha256: Sha256
    adapter: AdapterReference | None
    checkpoint_decision_sha256: Sha256 | None
    exactly_once_guard_sha256: Sha256 | None
    generation: GenerationConfig
    prediction_artifact: ArtifactReference
    summary_artifact: ArtifactReference
    lineage: Phase3BLineageV0_1
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class Phase3BFailureAnalysisV0_1(Phase3BModel):
    schema_version: Literal["phase3b-failure-analysis-v0.1"]
    analysis_id: str
    confirmatory_evaluation_sha256: Sha256
    overall: dict[str, Any]
    by_family_archetype: dict[str, dict[str, Any]]
    anchored_group: dict[str, Any]
    synthetic_only_groups: dict[str, Any]
    parser_classes: dict[str, int]
    contract_mismatches: dict[str, int]
    safety_flags: dict[str, Any]
    lineage: Phase3BLineageV0_1
    created_at: datetime
    content_sha256: Sha256


class Phase3BComparisonV0_1(Phase3BModel):
    schema_version: Literal["phase3b-comparison-v0.1"]
    comparison_id: str
    comparison_kind: Literal[
        "DATA_COMPOSITION",
        "ATTEMPT_STATUS",
        "PRIMARY_CONFIRMATORY_SIX_SYSTEM",
        "EXPLORATORY_LEGACY_TEST",
    ]
    status: Literal["COMPLETED"]
    evaluation_surface_sha256: Sha256 | None
    rows: list[dict[str, Any]]
    no_mixed_test_surfaces: bool
    replay_sha256s: list[Sha256]
    lineage: Phase3BLineageV0_1
    created_at: datetime
    content_sha256: Sha256


class Phase3BReplayVerificationV0_1(Phase3BModel):
    schema_version: Literal["phase3b-replay-v0.1"]
    replay_id: str
    kind: Literal[
        "baseline",
        "selection",
        "confirmatory",
        "leakage",
        "schedule",
        "training",
        "evaluation",
        "analysis",
        "comparison",
        "science",
    ]
    original_artifact_id: str
    original_content_sha256: Sha256
    recomputed_content_sha256: Sha256
    byte_hashes_verified: bool
    atomic_values_equal: bool
    status: Literal["PASSED", "FAILED"]
    lineage: Phase3BLineageV0_1 | None
    created_at: datetime
    content_sha256: Sha256


class Phase3BScientificDecisionV0_1(Phase3BModel):
    schema_version: Literal["phase3b-scientific-decision-v0.1"]
    decision_id: str
    scientific_status: Literal[
        "PHASE3B_SCIENTIFICALLY_COMPLETED",
        "PHASE3B_TERMINAL_NEGATIVE",
        "PHASE3B_BLOCKED",
    ]
    day4_gate: Literal[
        "DAY4_UNBLOCKED",
        "DAY4_UNBLOCKED_WITH_NEGATIVE_ANCHORED_TRANSFER_RESULT",
        "DAY4_BLOCKED",
    ]
    reason_code: str
    lineage: Phase3BLineageV0_1
    evaluation_replay_sha256: Sha256 | None
    comparison_sha256: Sha256 | None
    accounting_sha256: Sha256
    publication_independent: Literal[True]
    automatic_day4: Literal[False]
    further_phase3b_variants_allowed: Literal[False]
    created_at: datetime
    content_sha256: Sha256


class Phase3BPublicationManifestV0_1(Phase3BModel):
    schema_version: Literal["phase3b-publication-v0.1"]
    publication_id: str
    publication_status: Literal["PUBLISHED_VERIFIED", "PUBLICATION_BLOCKED", "NOT_ATTEMPTED"]
    scientific_decision_sha256: Sha256
    lineage: Phase3BLineageV0_1
    release_tag: Literal["phase3b-anchored-v0.1.0"]
    release_commit: FullCommitSha | None
    archive_name: str | None
    archive_sha256: Sha256 | None
    adapter_file_sha256s: dict[str, Sha256]
    urls: list[str]
    attempts: int = Field(ge=0, le=2)
    anonymous_download_verified: bool
    verification_timestamp: datetime | None
    content_sha256: Sha256
