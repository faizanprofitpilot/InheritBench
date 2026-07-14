"""Typed OpsRoute records and manifests."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from inheritbench.config import ScenarioFamily, Sha256
from inheritbench.evaluation.contracts import ActionContract, StrictJsonScalar, ToolName

SplitName = Literal["train", "validation", "test", "adversarial"]


class FrozenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OpsRouteInput(FrozenRecord):
    request: str
    context: dict[str, JsonValue]
    available_tools: list[ToolName]
    policy: dict[str, JsonValue]


class EvaluationMetadata(FrozenRecord):
    authorized_tools: list[ToolName]
    allowed_argument_values: dict[str, list[StrictJsonScalar]]
    tags: list[str]


class OpsRouteExample(FrozenRecord):
    schema_version: Literal["opsroute-example-v0.1"]
    example_id: str
    task_id: Literal["opsroute"]
    task_version: Literal["0.1.0"]
    scenario_family: ScenarioFamily
    archetype: str
    split: SplitName
    template_version: str
    template_id: str
    seed: int
    input: OpsRouteInput
    expected: ActionContract
    evaluation: EvaluationMetadata
    semantic_signature: Sha256
    surface_sha256: Sha256
    record_sha256: Sha256


class ArtifactDigest(FrozenRecord):
    path: str
    byte_sha256: Sha256
    bytes: int = Field(ge=0)
    records: int = Field(ge=0)


class DatasetManifest(FrozenRecord):
    schema_version: Literal["opsroute-manifest-v0.1"]
    task_id: Literal["opsroute"]
    task_version: Literal["0.1.0"]
    generator_version: Literal["0.1.0"]
    template_version: Literal["0.1.0"]
    seed: Literal[20260714]
    fixture_evidence: Literal[False]
    total_records: Literal[320]
    split_counts: dict[SplitName, int]
    family_counts: dict[ScenarioFamily, int]
    archetype_counts: dict[str, int]
    files: dict[SplitName, ArtifactDigest]
    dataset_sha256: Sha256
    split_manifest_sha256: Sha256
    content_sha256: Sha256


class SmokeIdsManifest(FrozenRecord):
    schema_version: Literal["opsroute-smoke-ids-v0.1"]
    task_version: Literal["0.1.0"]
    split: Literal["test"]
    example_ids: list[str] = Field(min_length=4, max_length=4)
    selection_rule: str
    content_sha256: Sha256


class RefundFacts(FrozenRecord):
    requested_action: Literal["refund", "none"]
    requester_authorized: bool
    action_authorized: bool
    customer_id: str
    payment_id: str | None
    amount_minor: int = Field(ge=0)
    currency: Literal["USD"]
    payment_status: Literal["settled", "pending"]
    payment_age_days: int = Field(ge=0)
    duplicate_evidence: Literal["confirmed", "incomplete", "none"]
    fraud_indicator: bool


class SubscriptionFacts(FrozenRecord):
    requested_action: Literal["cancel", "pause", "retention", "none"]
    requester_authorized: bool
    action_authorized: bool
    subscription_id: str | None
    cancellation_confirmed: bool
    contract_locked: bool
    balance_minor: int = Field(ge=0)
    effective_mode: Literal["immediate", "period_end"]
    pause_days: Literal[30, 60, 90]
    pause_eligible: bool
    retention_eligible: bool


def context_as_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
