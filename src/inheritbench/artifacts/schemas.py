"""Schemas for predictions, summaries, runs, replays, and inspection references."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from inheritbench.config import FullCommitSha, Sha256
from inheritbench.data.opsroute.schemas import EvaluationMetadata
from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.metrics import AtomicMetrics
from inheritbench.evaluation.parser import ParserResult


class ArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class GenerationConfig(ArtifactModel):
    do_sample: Literal[False]
    num_beams: Literal[1]
    max_new_tokens: Literal[256]
    seed: Literal[20260714]


class PredictionRecord(ArtifactModel):
    schema_version: Literal["prediction-v0.1"]
    prediction_id: str
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None
    example_id: str
    split: str
    model_role: Literal["source_base", "target_base"]
    model_id: str
    model_revision: FullCommitSha
    model_config_sha256: Sha256
    architecture_class: str | None
    resolved_device: str | None
    resolved_dtype: str | None
    task_version: str
    template_version: str
    prompt_template_version: str
    prompt_sha256: Sha256 | None
    input_ids_sha256: Sha256 | None
    generation: GenerationConfig
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


class RunSummary(ArtifactModel):
    schema_version: Literal["run-summary-v0.1"]
    run_id: str
    status: Literal["COMPLETED", "FAILED", "BLOCKED", "NOT_RUN"]
    prediction_counts: dict[str, int]
    aggregate_metrics: dict[str, dict[str, dict[str, float | int | None]]]
    model_valid_contract_counts: dict[str, int]
    run_errors: list[str]
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class ArtifactReference(ArtifactModel):
    relative_path: str
    byte_sha256: Sha256
    content_sha256: Sha256
    bytes: int = Field(ge=0)


class GitState(ArtifactModel):
    commit: FullCommitSha
    worktree_dirty: bool
    tracked_diff_sha256: Sha256 | None


class EnvironmentState(ArtifactModel):
    fingerprint_sha256: Sha256
    python: str
    packages: dict[str, str]
    os: str
    hardware: dict[str, Any]


class SmokeRunManifest(ArtifactModel):
    schema_version: Literal["smoke-run-v0.1"]
    run_id: str
    run_type: Literal["day1_pair_smoke"]
    status: Literal["COMPLETED", "FAILED", "BLOCKED", "NOT_RUN"]
    git: GitState
    environment: EnvironmentState
    source_config_sha256: Sha256
    target_config_sha256: Sha256
    pair_inspection_sha256: Sha256
    task_config_sha256: Sha256
    dataset_sha256: Sha256
    split_manifest_sha256: Sha256
    smoke_ids_sha256: Sha256
    command: list[str]
    generation_config: GenerationConfig
    seed: Literal[20260714]
    prediction_artifact: ArtifactReference
    summary_artifact: ArtifactReference
    aggregate_metrics: dict[str, dict[str, dict[str, float | int | None]]]
    prediction_counts: dict[str, int]
    run_errors: list[str]
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class ReplayVerification(ArtifactModel):
    schema_version: Literal["replay-verification-v0.1"]
    replay_id: str
    original_run_id: str
    status: Literal["PASSED", "FAILED"]
    original_prediction_byte_sha256: Sha256
    original_summary_byte_sha256: Sha256
    prediction_records_verified: int = Field(ge=0)
    parser_results_match: bool
    metrics_match: bool
    summary_matches: bool
    created_at: datetime
    content_sha256: Sha256
