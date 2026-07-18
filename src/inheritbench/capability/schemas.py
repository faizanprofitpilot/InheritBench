"""Strict schemas for capability packs and normalized evaluation results."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("path must be a safe relative POSIX path")
    return value


class CapabilityIdentity(StrictModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    status: Literal["DRAFT", "READY", "REFERENCE", "FIXTURE_ONLY"]
    profile: Literal["structured-json-v0.1"]


class PackPaths(StrictModel):
    input_schema: str
    output_schema: str
    cross_field_schema: str
    evaluator: str
    system_prompt: str
    safety_rules: str
    readiness_rules: str
    decision_vocabulary: str
    tool_vocabulary: str
    reason_code_vocabulary: str
    policy_code_vocabulary: str
    source_gate_inputs: str
    direct_train: str
    transfer_pool_inputs: str
    validation_inputs: str
    confirmatory_inputs: str
    adversarial_inputs: str
    source_gate_oracle: str
    transfer_pool_oracle: str
    validation_oracle: str
    confirmatory_oracle: str
    adversarial_oracle: str
    anchors: str

    @field_validator("*")
    @classmethod
    def validate_paths(cls, value: str) -> str:
        return _safe_relative(value)


class PromptContract(StrictModel):
    version: str = Field(min_length=1)
    maximum_prompt_tokens: int = Field(gt=0, le=32768)
    maximum_new_tokens: int = Field(gt=0, le=4096)
    input_rendering: Literal["canonical-json"]


class TrainingProfile(StrictModel):
    target_processed_tokens: int = Field(gt=0)
    batch_size: Literal[1]
    gradient_accumulation_steps: int = Field(gt=0)
    gradient_clip_norm: float = Field(gt=0)
    learning_rate: float = Field(gt=0)
    betas: list[float] = Field(min_length=2, max_length=2)
    epsilon: float = Field(gt=0)
    weight_decay: float = Field(ge=0)
    warmup_ratio: float = Field(ge=0, le=1)
    maximum_sequence_length: int = Field(gt=0)
    lora_rank: int = Field(gt=0)
    lora_alpha: int = Field(gt=0)
    lora_dropout: float = Field(ge=0, lt=1)
    checkpoint_fractions: list[float] = Field(min_length=1)


class DeterministicSchedulePolicy(StrictModel):
    type: Literal["deterministic-hash-v0.1"]
    namespace: str = Field(min_length=1)


class FrozenSchedulePolicy(StrictModel):
    type: Literal["frozen-record-order-v0.1"]
    artifact: str
    sha256: Sha256

    @field_validator("artifact")
    @classmethod
    def validate_artifact(cls, value: str) -> str:
        return _safe_relative(value)


SchedulePolicy = Annotated[
    DeterministicSchedulePolicy | FrozenSchedulePolicy,
    Field(discriminator="type"),
]


CheckpointRankMetric = Literal[
    "semantic_rate",
    "historical_strict_rate",
    "minimum_group_semantic_rate",
    "mean_field_correctness",
    "validation_loss_ascending",
    "optimizer_step_ascending",
]


class CheckpointPolicy(StrictModel):
    policy_id: str = Field(min_length=1)
    require_complete_validation: Literal[True]
    maximum_blocker_safety_findings: int = Field(ge=0)
    ranking: list[CheckpointRankMetric] = Field(min_length=1)

    @field_validator("ranking")
    @classmethod
    def validate_ranking(cls, value: list[CheckpointRankMetric]) -> list[CheckpointRankMetric]:
        if len(value) != len(set(value)):
            raise ValueError("checkpoint ranking metrics must be unique")
        return value


class StrategyProfile(StrictModel):
    strategy_id: Literal[
        "direct-target-lora-v0.1",
        "anchored-behavioral-transfer-v0.1",
    ]
    minimum_examples_per_group: int = Field(gt=0)
    selection_namespace: str = Field(min_length=1)
    teacher_selection_namespace: str | None = None
    anchor_selection_namespace: str | None = None
    teacher_outputs_artifact: str | None = None
    teacher_outputs_sha256: Sha256 | None = None
    checkpoint_validation_surface: Literal["source_gate", "validation"] = "validation"
    checkpoint_policy: CheckpointPolicy
    schedule_policy: SchedulePolicy
    training: TrainingProfile

    @field_validator("teacher_outputs_artifact")
    @classmethod
    def validate_teacher_outputs_artifact(cls, value: str | None) -> str | None:
        return None if value is None else _safe_relative(value)


class ModelAllowlist(StrictModel):
    source_registry_ids: list[str] = Field(min_length=1)
    target_registry_ids: list[str] = Field(min_length=1)
    default_source_adapter_path: str | None
    default_source_adapter_sha256: Sha256 | None

    @field_validator("default_source_adapter_path")
    @classmethod
    def validate_adapter_path(cls, value: str | None) -> str | None:
        return None if value is None else _safe_relative(value)


class CapabilityPackConfig(StrictModel):
    pack_schema_version: Literal["inheritbench.capability-pack.v0.2"]
    capability: CapabilityIdentity
    paths: PackPaths
    prompt: PromptContract
    models: ModelAllowlist
    strategies: list[StrategyProfile] = Field(min_length=1)
    coverage_group_key: str = Field(min_length=1)
    seed: int = Field(ge=0)


class ChatMessage(StrictModel):
    role: Literal["system", "user"]
    content: str = Field(min_length=1)


class CapabilityInputRecord(StrictModel):
    schema_version: Literal["inheritbench.capability-input.v0.2"]
    record_id: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    group: str = Field(min_length=1)
    payload: dict[str, Any]
    messages: list[ChatMessage] = Field(min_length=1)
    coverage: dict[str, str | int | bool]
    semantic_signature: Sha256
    source_record_sha256: Sha256
    content_sha256: Sha256


class CapabilityLabeledRecord(StrictModel):
    schema_version: Literal["inheritbench.capability-labeled-record.v0.2"]
    record_id: str = Field(min_length=1)
    input_record: CapabilityInputRecord
    assistant_label: str = Field(min_length=2)
    label_origin: Literal["direct", "anchor", "teacher"]
    assistant_label_sha256: Sha256
    content_sha256: Sha256


class CapabilityOracleRecord(StrictModel):
    schema_version: Literal["inheritbench.capability-oracle.v0.2"]
    record_id: str = Field(min_length=1)
    input_content_sha256: Sha256
    expected: dict[str, Any]
    safety_context: dict[str, Any]
    coverage: dict[str, str | int | bool]
    content_sha256: Sha256


class FieldComparisonRule(StrictModel):
    name: str = Field(min_length=1)
    pointer: str = Field(pattern=r"^(/([^/~]|~[01])*)+$")
    mode: Literal["exact", "list", "set", "numeric"]
    semantic: bool
    tolerance: float | None = Field(default=None, ge=0)


class TrustedEvaluatorPluginConfig(StrictModel):
    entry_point_group: Literal["inheritbench.evaluators"]
    entry_point_name: str = Field(min_length=1)
    distribution: str = Field(min_length=1)
    version: str = Field(min_length=1)
    code_sha256: Sha256


class EvaluatorConfig(StrictModel):
    schema_version: Literal[
        "inheritbench.declarative-evaluator.v0.1",
        "inheritbench.declarative-evaluator.v0.2",
    ]
    strict_json: Literal[True]
    whole_output_json_fence: bool
    strict_requires_cross_field: bool = False
    required_pointers: list[str]
    ignored_pointers: list[str]
    comparisons: list[FieldComparisonRule] = Field(min_length=1)
    controlled_vocabularies: dict[str, str]
    trusted_plugin: TrustedEvaluatorPluginConfig | None = None

    @field_validator("controlled_vocabularies")
    @classmethod
    def validate_vocabulary_paths(cls, value: dict[str, str]) -> dict[str, str]:
        return {pointer: _safe_relative(path) for pointer, path in value.items()}


class SafetyFinding(StrictModel):
    code: str = Field(min_length=1)
    severity: Literal["info", "warning", "blocker"]
    message: str = Field(min_length=1)


class ParserFinding(StrictModel):
    code: Literal[
        "INVALID_JSON",
        "ROOT_NOT_OBJECT",
        "SCHEMA_INVALID",
        "PROSE_OR_MULTIPLE_OBJECTS",
    ]
    message: str


class GenericEvaluationResult(StrictModel):
    schema_version: Literal[
        "inheritbench.generic-evaluation.v0.1",
        "inheritbench.generic-evaluation.v0.2",
    ]
    record_id: str
    raw_output: str
    strict_candidate: str
    normalized_candidate: str | None
    parser_classification: Literal["STRICT_VALID", "NORMALIZED_VALID", "UNPARSEABLE"]
    parse_valid: bool = False
    valid_json: bool
    schema_valid: bool
    vocabulary_conformant: bool = False
    cross_field_conformant: bool = False
    historical_strict_valid: bool = False
    strict_valid: bool
    structural_exact: bool
    semantic_match: bool
    field_correctness: dict[str, bool]
    mean_field_correctness: float
    parsed_output: dict[str, Any] | None
    expected: dict[str, Any]
    parser_findings: list[ParserFinding]
    safety_findings: list[SafetyFinding]
    coverage: dict[str, str | int | bool]
    content_sha256: Sha256


class ValidationFinding(StrictModel):
    code: str
    severity: Literal["INFO", "WARNING", "ERROR"]
    file: str
    pointer: str
    record_id: str | None
    message: str
    remediation: str


class CapabilityValidationReport(StrictModel):
    schema_version: Literal["inheritbench.capability-validation.v0.1"]
    capability_id: str
    capability_version: str
    status: Literal["PASS", "FAIL"]
    findings: list[ValidationFinding]
    file_sha256s: dict[str, Sha256]
    record_counts: dict[str, int]
    content_sha256: Sha256
