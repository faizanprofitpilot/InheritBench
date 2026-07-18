"""Strategy result contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from inheritbench.capability.schemas import CapabilityLabeledRecord


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class SupervisionAccounting(StrictModel):
    direct_labels: int = Field(ge=0)
    anchor_labels: int = Field(ge=0)
    teacher_labels: int = Field(ge=0)
    upstream_original_labels: int = Field(ge=0)
    candidate_inputs: int = Field(ge=0)
    accepted_teacher_outputs: int = Field(ge=0)
    rejected_teacher_outputs: int = Field(ge=0)
    selected_training_records: int = Field(ge=0)


class GroupDeficit(StrictModel):
    group: str
    required: int = Field(gt=0)
    accepted_teacher: int = Field(ge=0)
    accepted_anchors: int = Field(ge=0)
    deficit: int = Field(gt=0)


class SupervisionResult(StrictModel):
    status: Literal["FROZEN", "ANCHORS_REQUIRED", "FAILED"]
    strategy_id: str
    records: list[CapabilityLabeledRecord]
    deficits: list[GroupDeficit]
    accounting: SupervisionAccounting
    rejected_record_ids: list[str]
    teacher_stage_sha256: str | None


class TeacherEvaluationResult(StrictModel):
    schema_version: Literal["inheritbench.teacher-evaluation.v0.1"]
    strategy_id: Literal["anchored-behavioral-transfer-v0.1"]
    accepted_records: list[CapabilityLabeledRecord]
    rejected_record_ids: list[str]
    teacher_stage_sha256: Sha256
    content_sha256: Sha256
