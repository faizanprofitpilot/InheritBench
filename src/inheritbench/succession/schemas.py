"""Strict schemas for the supported succession replay product."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inheritbench.artifacts.schemas import ArtifactReference
from inheritbench.config import FullCommitSha, Sha256
from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.metrics import AtomicMetrics


class SuccessionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class HashedPathV0_1(SuccessionModel):
    relative_path: str
    byte_sha256: Sha256
    content_sha256: Sha256 | None
    bytes: int = Field(ge=1)


class ModelIdentityV0_1(SuccessionModel):
    model_id: str
    revision: FullCommitSha
    config_path: str
    config_sha256: Sha256


class CapabilityContractV0_1(SuccessionModel):
    python_type: Literal["inheritbench.evaluation.contracts.ActionContract"]
    historical_policy_code_validation: Literal["NONEMPTY_STRING"]
    future_policy_code_validation: Literal["REGISTRY_BACKED"]


class AdapterIdentityV0_1(SuccessionModel):
    adapter_id: Literal["target_hybrid_anchored_distillation_10-7461072c83b4dcde"]
    base_model_id: Literal["allenai/OLMo-2-0425-1B-Instruct"]
    base_model_revision: FullCommitSha
    release_tag: Literal["phase3b-anchored-v0.1.0"]
    release_commit: FullCommitSha
    archive_name: Literal["target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip"]
    archive_sha256: Sha256
    archive_bytes: int = Field(ge=1)
    adapter_file_sha256s: dict[str, Sha256]
    release_url: str
    publication_status: Literal["PUBLISHED_VERIFIED"]
    anonymous_download_verified: Literal[True]
    publication_content_sha256: Sha256


class SuccessionCapabilityPackV0_1(SuccessionModel):
    schema_version: Literal["succession-capability-pack-v0.1"]
    capability_id: Literal["opsroute"]
    capability_version: Literal["0.1.0"]
    support_status: Literal["FIRST_SUPPORTED_CASE"]
    display_name: Literal["OpsRoute"]
    description: str
    task_config: dict[str, str]
    source_model: ModelIdentityV0_1
    target_model: ModelIdentityV0_1
    scenario_families: dict[str, list[str]]
    contract: CapabilityContractV0_1
    policy_registry_path: str
    safety_rules_path: str
    prompt_version: Literal["0.1.0"]
    parser_version: Literal["0.1.0"]
    evaluator_version: Literal["v0"]
    transfer_strategy: Literal["ANCHORED_BEHAVIORAL_TRANSFER"]
    execution_modes: list[Literal["VERIFIED_REPLAY", "PHASED_LOCAL_CLI"]]
    adapter: dict[str, str]
    limitations: list[str] = Field(min_length=3)


class ReplayRecordV0_1(SuccessionModel):
    schema_version: Literal["succession-replay-record-v0.1"]
    surface: Literal["confirmatory", "adversarial"]
    system_id: Literal["target_untouched", "target_hybrid_anchored_distillation_10"]
    example_id: str
    scenario_family: str
    archetype: str
    status: Literal["COMPLETED"]
    parser_classification: Literal["STRICT_VALID", "NORMALIZED_VALID", "UNPARSEABLE"]
    expected_contract: ActionContract
    validated_contract: ActionContract | None
    metrics: AtomicMetrics
    adversarial_profiles: list[str]
    latency_ms: int = Field(ge=0)
    source_prediction_id: str
    source_prediction_content_sha256: Sha256


class SuccessionReplayContextV0_1(SuccessionModel):
    schema_version: Literal["succession-replay-context-v0.1"]
    label_accounting: dict[str, int]
    compute_accounting: dict[str, int | float]
    profile_id: Literal["maximum_confirmed_capability"]
    profile_recommendation: Literal["target_hybrid_anchored_distillation_10"]
    profile_source_sha256: Sha256
    memo_kind: Literal["GPT_5_6_SOL"]
    memo_validation_status: Literal["PASSED"]
    memo_sha256: Sha256
    memo_validation_sha256: Sha256
    content_sha256: Sha256


class SuccessionRunManifestV0_1(SuccessionModel):
    schema_version: Literal["succession-run-manifest-v0.1"]
    run_id: str
    case_id: Literal["opsroute-qwen-olmo"]
    status: Literal["FROZEN"]
    capability_pack_path: str
    capability_pack_sha256: Sha256
    configuration: dict[str, str | int]
    schema_versions: dict[str, str]
    source_artifacts: list[HashedPathV0_1] = Field(min_length=6)
    replay_records: ArtifactReference
    replay_context: ArtifactReference
    operation_order: list[str] = Field(min_length=9, max_length=9)
    readiness_rule_version: Literal["succession-readiness-v0.1"]
    adapter: AdapterIdentityV0_1
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_operation_order(self) -> SuccessionRunManifestV0_1:
        expected = [
            "configuration_validated",
            "frozen_evidence_located",
            "manifest_identity_verified",
            "replay_records_loaded",
            "metrics_aggregated",
            "residual_failures_classified",
            "readiness_rules_applied",
            "adapter_identity_confirmed",
            "readiness_report_generated",
        ]
        if self.operation_order != expected:
            raise ValueError("succession replay operation order differs from v0.1")
        return self


class SurfaceSummaryV0_1(SuccessionModel):
    system_id: str
    surface: Literal["confirmatory", "adversarial"]
    record_count: int = Field(ge=0)
    semantic_exact: int = Field(ge=0)
    strict_valid: int = Field(ge=0)
    decision_correct: int = Field(ge=0)
    tool_correct: int = Field(ge=0)
    arguments_exact: int = Field(ge=0)
    approval_correct: int = Field(ge=0)
    policy_code_correct: int = Field(ge=0)
    reason_code_correct: int = Field(ge=0)
    unauthorized_actions: int = Field(ge=0)
    approval_bypasses: int = Field(ge=0)
    false_actions: int = Field(ge=0)
    strict_invalid: int = Field(ge=0)
    safety_unknown: int = Field(ge=0)
    model_latency_ms: int = Field(ge=0)


class SuccessionEvaluationSummaryV0_1(SuccessionModel):
    schema_version: Literal["succession-evaluation-summary-v0.1"]
    target_before_confirmatory: SurfaceSummaryV0_1
    successor_confirmatory: SurfaceSummaryV0_1
    successor_adversarial: SurfaceSummaryV0_1
    content_sha256: Sha256


class PolicyAliasV0_1(SuccessionModel):
    example_id: str
    expected_policy_code: str
    predicted_policy_code: str


class SuccessionResidualFailuresV0_1(SuccessionModel):
    schema_version: Literal["succession-residual-failures-v0.1"]
    clean_policy_code_aliases: list[PolicyAliasV0_1]
    clean_policy_code_alias_count: int = Field(ge=0)
    adversarial_profile_failures: dict[str, int]
    content_sha256: Sha256


class SuccessionReadinessReportV0_1(SuccessionModel):
    schema_version: Literal["succession-readiness-report-v0.1"]
    run_id: str
    case_id: Literal["opsroute-qwen-olmo"]
    decision: Literal["PASS", "CONDITIONAL_PASS", "BLOCK"]
    reason_codes: list[str] = Field(min_length=1)
    readiness_rule_version: Literal["succession-readiness-v0.1"]
    evaluation_summary_sha256: Sha256
    residual_failures_sha256: Sha256
    adapter_id: str
    adapter_archive_sha256: Sha256
    profile_id: Literal["maximum_confirmed_capability"]
    profile_recommendation: Literal["target_hybrid_anchored_distillation_10"]
    deployment_constraints: list[str] = Field(min_length=1)
    content_sha256: Sha256


class ReplayOperationV0_1(SuccessionModel):
    operation: str
    status: Literal["PASSED"]


class SuccessionReplayReceiptV0_1(SuccessionModel):
    schema_version: Literal["succession-replay-receipt-v0.1"]
    run_id: str
    status: Literal["VERIFIED_REPLAY_COMPLETED"]
    manifest_sha256: Sha256
    replay_records_byte_sha256: Sha256
    operations: list[ReplayOperationV0_1] = Field(min_length=9, max_length=9)
    readiness_report_sha256: Sha256
    content_sha256: Sha256


class SuccessionReplayResult(SuccessionModel):
    summary: SuccessionEvaluationSummaryV0_1
    residuals: SuccessionResidualFailuresV0_1
    readiness: SuccessionReadinessReportV0_1
    receipt: SuccessionReplayReceiptV0_1
    label_accounting: dict[str, int]
    compute_accounting: dict[str, int | float]
    adapter_reference: dict[str, Any]
