"""Strict generic succession plan, stage and output contracts."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from inheritbench.model_adapters.schemas import (
    GenerationOutput,
    ModelRuntimeIdentity,
)
from inheritbench.strategies.schemas import SupervisionAccounting

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
RunState = Literal[
    "CREATED",
    "PACK_VALIDATED",
    "MODELS_PREFLIGHTED",
    "PLAN_FROZEN",
    "SOURCE_GATE_COMPLETED",
    "TARGET_BASELINE_COMPLETED",
    "SUPERVISION_PREPARING",
    "TEACHER_OUTPUTS_EVALUATED",
    "ANCHORS_REQUIRED",
    "ANCHORS_ADDED",
    "SUPERVISION_FROZEN",
    "TRAINING",
    "CHECKPOINT_SELECTED",
    "CANDIDATE_FROZEN",
    "CONFIRMATORY_COMPLETED",
    "ADVERSARIAL_COMPLETED",
    "READINESS_FINALIZED",
    "ADAPTER_EXPORTED",
    "RELOAD_VERIFIED",
    "REPLAY_VERIFIED",
    "COMPLETED",
    "SOURCE_CAPABILITY_GATE_FAILED",
    "SUPERVISION_GATE_FAILED",
    "TARGET_CAPACITY_INSUFFICIENT",
    "NO_SAFETY_ELIGIBLE_CHECKPOINT",
    "UNSUPPORTED_MODEL_ARCHITECTURE",
    "MIGRATION_BLOCKED",
    "INTEGRITY_FAILURE",
    "EXECUTION_FAILED",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class PlannedInput(StrictModel):
    relative_path: str
    bytes: int = Field(ge=0)
    byte_sha256: Sha256


class AdapterBinding(StrictModel):
    relative_path: str
    adapter_sha256: Sha256


class ProtocolAmendmentBinding(StrictModel):
    amendment_id: str
    relative_path: str
    byte_sha256: Sha256
    amendment_sha256: Sha256


class AuthorizedAnchorPoolBinding(StrictModel):
    relative_path: str
    bytes: int = Field(gt=0)
    byte_sha256: Sha256
    records: int = Field(gt=0)
    records_sha256: Sha256
    ranking_namespace: str


class SuccessionPlan(StrictModel):
    schema_version: Literal[
        "inheritbench.succession-plan.v0.2",
        "inheritbench.succession-plan.v0.3",
    ]
    execution_engine_version: Literal[
        "inheritbench-generic-succession-v0.2.0",
        "inheritbench-generic-succession-v0.2.1",
        "inheritbench-generic-succession-v0.2.2",
        "inheritbench-generic-succession-v0.3.0",
    ] = "inheritbench-generic-succession-v0.2.0"
    run_id: str
    canonical_plan_id: str | None = None
    canonical_plan_sha256: Sha256 | None = None
    execution_id: str | None = None
    replication_group_id: str | None = None
    replication_index: int | None = Field(default=None, ge=0)
    protocol_amendment: ProtocolAmendmentBinding | None = None
    authorized_anchor_pool: AuthorizedAnchorPoolBinding | None = None
    product_run_kind: Literal[
        "STANDARD",
        "PRODUCT_INTEGRATION_RUN",
        "PRODUCT_PARITY_RUN",
        "PRODUCT_REFERENCE_SUCCESSION",
    ]
    pack_root: str
    pack_validation_sha256: Sha256
    capability_id: str
    capability_version: str
    strategy_id: Literal[
        "direct-target-lora-v0.1",
        "anchored-behavioral-transfer-v0.1",
    ]
    source_config_path: str
    source_config_sha256: Sha256
    source_registry_id: str
    source_adapter: AdapterBinding | None
    target_config_path: str
    target_config_sha256: Sha256
    target_registry_id: str
    device: Literal["mps", "cpu", "cuda"]
    seed: int
    authorized_inputs: list[PlannedInput]
    strategy_profile: dict[str, Any]
    operation_order: list[str]
    plan_sha256: Sha256

    @model_validator(mode="after")
    def validate_versioned_identity(self) -> SuccessionPlan:
        versioned = (
            self.canonical_plan_id,
            self.canonical_plan_sha256,
            self.execution_id,
            self.replication_group_id,
            self.replication_index,
            self.protocol_amendment,
        )
        if self.schema_version == "inheritbench.succession-plan.v0.2":
            if any(value is not None for value in versioned) or self.authorized_anchor_pool:
                raise ValueError("v0.2 plans cannot declare v0.3 execution identity")
            return self
        if any(value is None for value in versioned):
            raise ValueError("v0.3 plans require canonical and execution identity")
        if self.run_id != self.execution_id:
            raise ValueError("v0.3 run_id must equal execution_id")
        if (
            self.strategy_id == "anchored-behavioral-transfer-v0.1"
            and self.authorized_anchor_pool is None
        ):
            raise ValueError("v0.3 anchored plans require an authorized anchor pool")
        if (
            self.strategy_id == "direct-target-lora-v0.1"
            and self.authorized_anchor_pool is not None
        ):
            raise ValueError("direct plans cannot declare an anchor pool")
        return self


class StageManifest(StrictModel):
    schema_version: Literal["inheritbench.succession-stage.v0.2"]
    run_id: str
    stage: RunState
    sequence: int = Field(ge=0)
    parent_stage_sha256: Sha256 | None
    status: Literal["COMPLETED", "INTERVENTION", "FAILED"]
    payload: dict[str, Any]
    errors: list[str]
    content_sha256: Sha256


class EvaluationRecord(StrictModel):
    schema_version: Literal["inheritbench.succession-evaluation-record.v0.2"]
    surface: str
    system_role: Literal["source", "target_base", "target_checkpoint", "target_selected"]
    checkpoint_id: str | None
    model: ModelRuntimeIdentity
    generation: GenerationOutput
    evaluation: dict[str, Any]
    content_sha256: Sha256


class SurfaceSummary(StrictModel):
    surface: str
    expected: int = Field(ge=0)
    terminal: int = Field(ge=0)
    semantic_correct: int = Field(ge=0)
    strict_valid: int = Field(ge=0)
    vocabulary_conformant: int = Field(default=0, ge=0)
    cross_field_conformant: int = Field(default=0, ge=0)
    structural_exact: int = Field(ge=0)
    mean_field_correctness: float = Field(ge=0, le=1)
    blocker_safety_findings: int = Field(ge=0)
    unknown_safety: int = Field(ge=0)
    minimum_group_semantic_rate: float = Field(ge=0, le=1)
    group_semantic: dict[str, dict[str, int | float]]


class CheckpointScore(StrictModel):
    checkpoint_id: str
    adapter_directory: str
    adapter_sha256: Sha256
    eligible: bool
    semantic_rate: float
    strict_rate: float
    minimum_group_semantic_rate: float
    mean_field_correctness: float
    validation_loss: float
    optimizer_step: int
    blocker_safety_findings: int


class CheckpointDecision(StrictModel):
    status: Literal["SELECTED", "NO_SAFETY_ELIGIBLE_CHECKPOINT"]
    scores: list[CheckpointScore]
    selected_checkpoint_id: str | None
    selected_adapter_directory: str | None
    selected_adapter_sha256: Sha256 | None


class ReadinessReport(StrictModel):
    schema_version: Literal["inheritbench.readiness-report.v0.2"]
    run_id: str
    rule_version: str
    status: Literal["PASS", "CONDITIONAL_PASS", "MIGRATION_BLOCKED"]
    reason_codes: list[str]
    source_gate: SurfaceSummary
    target_baseline: SurfaceSummary
    confirmatory: SurfaceSummary
    adversarial: SurfaceSummary
    supervision: SupervisionAccounting
    selected_checkpoint_id: str
    adapter_sha256: Sha256
    content_sha256: Sha256


class ReplayReceipt(StrictModel):
    schema_version: Literal["inheritbench.succession-replay.v0.2"]
    run_id: str
    status: Literal["PASSED", "FAILED"]
    verified_files: dict[str, Sha256]
    readiness_sha256: Sha256
    adapter_sha256: Sha256
    content_sha256: Sha256


class FinalizedWebBundle(StrictModel):
    schema_version: Literal[
        "inheritbench.web-bundle.v0.2",
        "inheritbench.web-bundle.v0.3",
    ]
    run_id: str
    canonical_plan_id: str | None = None
    execution_id: str | None = None
    capability: dict[str, str]
    strategy: str
    protocol_amendment: dict[str, Any] | None = None
    intervention: dict[str, Any] | None = None
    reproduction: dict[str, Any] | None = None
    readiness: ReadinessReport
    summaries: dict[str, SurfaceSummary]
    residuals: list[dict[str, Any]]
    label_accounting: SupervisionAccounting
    compute_accounting: dict[str, int | float]
    adapter: dict[str, Any]
    reload_verification: dict[str, Any] | None = None
    replay_verification: dict[str, Any] | None = None
    stages: list[RunState]
    content_sha256: Sha256


class InterventionWebBundle(StrictModel):
    schema_version: Literal["inheritbench.intervention-web-bundle.v0.2"]
    run_id: str
    capability: dict[str, str]
    strategy: str
    state: Literal["ANCHORS_REQUIRED"]
    intervention: dict[str, Any]
    stages: list[RunState]
    content_sha256: Sha256


class RunInspection(StrictModel):
    run_id: str
    current_state: RunState
    capability: str
    strategy: str
    stages: list[RunState]
    intervention: dict[str, Any] | None
    readiness: dict[str, Any] | None
    replay_command: str
