"""Strict schemas for the Phase 5 display projection and product status."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inheritbench.config import Sha256

EvaluationSurface = Literal["confirmatory", "adversarial", "exploratory"]
CaseStatus = Literal["SELECTED", "NO_ELIGIBLE_CASE"]


class Phase5Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Phase5SourceReferenceV0_1(Phase5Model):
    schema_version: Literal["phase5-source-reference-v0.1"]
    source_id: str
    relative_path: str
    byte_sha256: Sha256
    content_sha256: Sha256 | None
    json_path: str
    evaluation_surface: EvaluationSurface | Literal["cross_surface", "not_applicable"]


class Phase5StoryFactV0_1(Phase5Model):
    fact_id: str
    label: str
    value: Any
    display_value: str
    source_ids: list[str] = Field(min_length=1)


class Phase5StoryStageV0_1(Phase5Model):
    stage_id: str
    eyebrow: str
    title: str
    summary: str
    fact_ids: list[str] = Field(min_length=1)


class Phase5StoryV0_1(Phase5Model):
    schema_version: Literal["phase5-story-v0.1"]
    projection_id: Literal["inheritbench-web-v0.1"]
    thesis: str
    product_labels: list[str] = Field(min_length=3, max_length=3)
    confirmatory_denominator: Literal[64]
    adversarial_denominator: Literal[32]
    stages: list[Phase5StoryStageV0_1] = Field(min_length=5)
    facts: list[Phase5StoryFactV0_1] = Field(min_length=10)
    prohibited_blended_score: Literal[True]
    content_sha256: Sha256


class Phase5CasePredictionV0_1(Phase5Model):
    system_id: str
    split: str
    run_id: str
    prediction_id: str
    raw_output: str
    parser_result: dict[str, Any]
    expected_contract: dict[str, Any]
    metrics: dict[str, Any]
    primary_failure: str
    failure_tags: list[str]
    prediction_content_sha256: Sha256
    run_content_sha256: Sha256
    split_sha256: Sha256
    oracle_sha256: Sha256
    prediction_artifact_byte_sha256: Sha256


class Phase5RepresentativeCaseDetailV0_1(Phase5Model):
    schema_version: Literal["phase5-representative-case-v0.1"]
    slot: str
    status: CaseStatus
    eligibility_reason: str
    selection_rank: Sha256 | None
    evaluation_surface: EvaluationSurface | None
    example_id: str | None
    scenario_family: str | None
    archetype: str | None
    input: dict[str, Any] | None
    expected_contract: dict[str, Any] | None
    system_predictions: list[Phase5CasePredictionV0_1]
    selection_parent_sha256: Sha256
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_case_status(self) -> Phase5RepresentativeCaseDetailV0_1:
        if self.status == "NO_ELIGIBLE_CASE":
            if (
                any(
                    value is not None
                    for value in (
                        self.selection_rank,
                        self.evaluation_surface,
                        self.example_id,
                        self.input,
                        self.expected_contract,
                    )
                )
                or self.system_predictions
            ):
                raise ValueError("NO_ELIGIBLE_CASE must remain empty")
        elif (
            self.selection_rank is None
            or self.evaluation_surface is None
            or self.example_id is None
            or self.input is None
            or self.expected_contract is None
            or not self.system_predictions
        ):
            raise ValueError("selected cases require complete immutable evidence")
        return self


class Phase5CaseDetailsV0_1(Phase5Model):
    schema_version: Literal["phase5-case-details-v0.1"]
    projection_id: Literal["inheritbench-web-v0.1"]
    case_selection_sha256: Sha256
    selection_parent_sha256: Sha256
    cases: list[Phase5RepresentativeCaseDetailV0_1] = Field(min_length=8, max_length=8)
    selected_count: Literal[6]
    no_eligible_count: Literal[2]
    content_sha256: Sha256


class Phase5SourceIndexV0_1(Phase5Model):
    schema_version: Literal["phase5-source-index-v0.1"]
    projection_id: Literal["inheritbench-web-v0.1"]
    sources: list[Phase5SourceReferenceV0_1] = Field(min_length=10)
    content_sha256: Sha256


class Phase5ProjectionFileV0_1(Phase5Model):
    relative_path: str
    byte_sha256: Sha256
    content_sha256: Sha256
    bytes: int = Field(ge=1)


class Phase5WebProjectionManifestV0_1(Phase5Model):
    schema_version: Literal["phase5-web-projection-manifest-v0.1"]
    projection_id: Literal["inheritbench-web-v0.1"]
    status: Literal["FROZEN"]
    source_showcase_content_sha256: Literal[
        "85f6c02dcc430992a277d0cb500373a1b491893915f450b4523699b7b7d3e5cc"
    ]
    phase4_decision_content_sha256: Literal[
        "2db9baa4cf266cbccaf8ff4ce8948973a6c8175e5212e3b7336f29d616d434af"
    ]
    files: list[Phase5ProjectionFileV0_1] = Field(min_length=3, max_length=3)
    historical_artifacts_modified: Literal[False]
    display_only: Literal[True]
    content_sha256: Sha256


class Phase5WebBuildManifestV0_1(Phase5Model):
    schema_version: Literal["phase5-web-build-manifest-v0.1"]
    build_id: str
    projection_content_sha256: Sha256
    showcase_content_sha256: Sha256
    node_version: Literal["22.14.0"]
    pnpm_version: Literal["10.7.1"]
    node_only_ingestion_passed: Literal[True]
    lint_passed: Literal[True]
    typecheck_passed: Literal[True]
    unit_tests_passed: Literal[True]
    static_export_passed: Literal[True]
    browser_tests_passed: Literal[True]
    output_files_sha256: Sha256
    content_sha256: Sha256


class Phase5ProductDecisionV0_1(Phase5Model):
    schema_version: Literal["phase5-product-decision-v0.1"]
    decision_id: str
    product_status: Literal[
        "PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY",
        "PHASE5_PRODUCT_COMPLETED",
        "PHASE5_PRODUCT_BLOCKED",
    ]
    deployment_status: Literal["DEPLOYMENT_REQUIRED", "DEPLOYED_VERIFIED", "DEPLOYMENT_BLOCKED"]
    projection_content_sha256: Sha256
    showcase_content_sha256: Sha256
    phase4_decision_content_sha256: Sha256
    web_build_manifest_sha256: Sha256
    deployment_verification_sha256: Sha256 | None
    public_url: str | None
    historical_artifacts_modified: Literal[False]
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_status_pair(self) -> Phase5ProductDecisionV0_1:
        if self.product_status == "PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY" and (
            self.deployment_status != "DEPLOYMENT_REQUIRED" or self.public_url is not None
        ):
            raise ValueError("local completion requires deployment with no public URL claim")
        if self.product_status == "PHASE5_PRODUCT_COMPLETED" and (
            self.deployment_status != "DEPLOYED_VERIFIED"
            or self.public_url is None
            or self.deployment_verification_sha256 is None
        ):
            raise ValueError("public completion requires immutable deployment verification")
        return self


class Phase5DeploymentVerificationV0_1(Phase5Model):
    schema_version: Literal["phase5-deployment-verification-v0.1"]
    verification_id: str
    public_url: str
    stable_public_url: Literal[True]
    incognito_access_passed: Literal[True]
    deep_links_passed: Literal[True]
    no_auth_or_secret_required: Literal[True]
    browser_integrity_passed: Literal[True]
    core_flow_passed: Literal[True]
    desktop_passed: Literal[True]
    mobile_passed: Literal[True]
    console_errors: list[str] = Field(max_length=0)
    hydration_errors: list[str] = Field(max_length=0)
    accessibility_errors: list[str] = Field(max_length=0)
    content_sha256: Sha256
