"""Controlled validation-only inference and exact replay."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
)
from inheritbench.artifacts.schemas import (
    ArtifactReference,
    GenerationConfig,
    PredictionRecord,
    RunSummary,
)
from inheritbench.artifacts.store import artifact_reference, verify_reference, write_atomic_bundle
from inheritbench.blockers.subsets import SubsetManifest
from inheritbench.config import Sha256, load_model_config, load_task_config
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.evaluation.metrics import score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.inference.runner import _aggregates_by_role, _infer_model

_RUN_EXCLUSIONS = {"content_sha256", "created_at", "finished_at", "run_id"}


class DiagnosticManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["diagnostic-run-v0.1"]
    run_id: str
    run_type: Literal["untouched_validation_diagnostic"]
    status: Literal["COMPLETED", "FAILED"]
    model_config_sha256: Sha256
    task_config_sha256: Sha256
    subset_content_sha256: Sha256
    command: list[str]
    generation_config: GenerationConfig
    prediction_artifact: ArtifactReference
    summary_artifact: ArtifactReference
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class DiagnosticReplay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["diagnostic-replay-v0.1"]
    original_run_id: str
    status: Literal["PASSED"]
    prediction_records_verified: int
    parser_results_match: Literal[True]
    metrics_match: Literal[True]
    aggregates_match: Literal[True]
    created_at: datetime
    content_sha256: Sha256


def run_untouched_diagnostic(
    *,
    model_path: Path,
    task_path: Path,
    subset_path: Path,
    dataset_directory: Path,
    device: Literal["auto", "mps", "cpu", "cuda"],
    output_root: Path,
    role: Literal["source_base", "target_base"] = "target_base",
    command: list[str] | None = None,
) -> Path:
    model_config = load_model_config(model_path)
    task_config = load_task_config(task_path)
    subset = SubsetManifest.model_validate_json(subset_path.read_bytes(), strict=True)
    if subset.source_split != "validation" or subset.fixture_evidence:
        raise ValueError("untouched diagnostics require non-fixture validation records")
    examples = load_examples(dataset_directory, subset.example_ids)
    if any(example.split != "validation" for example in examples):
        raise ValueError("diagnostic subset contains non-validation records")

    created_at = datetime.now(UTC)
    run_id = f"diagnostic-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    generation = GenerationConfig(
        do_sample=False,
        num_beams=1,
        max_new_tokens=task_config.maximum_new_tokens,
        seed=task_config.seed,
    )
    predictions = _infer_model(
        config=model_config,
        role=role,
        examples=examples,
        task_config=task_config,
        generation=generation,
        run_id=run_id,
        device=device,
    )
    return _write_run(
        predictions=predictions,
        run_id=run_id,
        model_config_sha256=content_sha256(model_config),
        task_config_sha256=content_sha256(task_config),
        subset_content_sha256=subset.content_sha256,
        generation=generation,
        created_at=created_at,
        output_root=output_root,
        command=command or sys.argv,
    )


def replay_diagnostic(run_directory: Path, output_root: Path) -> Path:
    manifest = DiagnosticManifest.model_validate_json(
        (run_directory / "manifest.json").read_bytes(), strict=True
    )
    verify_reference(run_directory, manifest.prediction_artifact)
    verify_reference(run_directory, manifest.summary_artifact)
    predictions = _read_predictions(run_directory / "predictions.jsonl")
    for prediction in predictions:
        if prediction.status == "FAILED":
            continue
        parser_result = parse_action_contract(prediction.raw_output)
        metrics = score_prediction(
            parser_result, prediction.expected_contract, prediction.evaluation_metadata
        )
        if parser_result != prediction.parser_result or metrics != prediction.metrics:
            raise ValueError(f"replay mismatch for {prediction.prediction_id}")
    summary = RunSummary.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )
    if _aggregates_by_role(predictions) != summary.aggregate_metrics:
        raise ValueError("diagnostic aggregate replay mismatch")
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "diagnostic-replay-v0.1",
        "original_run_id": manifest.run_id,
        "status": "PASSED",
        "prediction_records_verified": len(predictions),
        "parser_results_match": True,
        "metrics_match": True,
        "aggregates_match": True,
        "created_at": created_at,
    }
    replay = DiagnosticReplay.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
    return write_atomic_bundle(
        output_root,
        f"replay-{manifest.run_id}",
        {"verification.json": canonical_json_bytes(replay) + b"\n"},
    )


def _write_run(
    *,
    predictions: list[PredictionRecord],
    run_id: str,
    model_config_sha256: str,
    task_config_sha256: str,
    subset_content_sha256: str,
    generation: GenerationConfig,
    created_at: datetime,
    output_root: Path,
    command: list[str],
) -> Path:
    finished_at = datetime.now(UTC)
    failed = [prediction for prediction in predictions if prediction.status == "FAILED"]
    status: Literal["COMPLETED", "FAILED"] = "FAILED" if failed else "COMPLETED"
    aggregates = _aggregates_by_role(predictions)
    summary_payload = {
        "schema_version": "run-summary-v0.1",
        "run_id": run_id,
        "status": status,
        "prediction_counts": {
            "total": len(predictions),
            "completed": len(predictions) - len(failed),
            "failed": len(failed),
        },
        "aggregate_metrics": aggregates,
        "model_valid_contract_counts": {
            predictions[0].model_role: sum(
                prediction.parser_result is not None
                and prediction.parser_result.classification in {"STRICT_VALID", "NORMALIZED_VALID"}
                for prediction in predictions
            )
        },
        "run_errors": [error for prediction in failed for error in prediction.errors],
        "created_at": created_at,
        "finished_at": finished_at,
    }
    summary = RunSummary.model_validate(
        {
            **summary_payload,
            "content_sha256": content_sha256(summary_payload, excluded_keys=_RUN_EXCLUSIONS),
        },
        strict=True,
    )
    predictions_bytes = canonical_jsonl_bytes(predictions)
    summary_bytes = canonical_json_bytes(summary) + b"\n"
    prediction_reference = artifact_reference(
        "predictions.jsonl",
        predictions_bytes,
        content_sha256=content_sha256([prediction.content_sha256 for prediction in predictions]),
    )
    summary_reference = artifact_reference(
        "summary.json", summary_bytes, content_sha256=summary.content_sha256
    )
    manifest_payload = {
        "schema_version": "diagnostic-run-v0.1",
        "run_id": run_id,
        "run_type": "untouched_validation_diagnostic",
        "status": status,
        "model_config_sha256": model_config_sha256,
        "task_config_sha256": task_config_sha256,
        "subset_content_sha256": subset_content_sha256,
        "command": command,
        "generation_config": generation.model_dump(mode="json"),
        "prediction_artifact": prediction_reference.model_dump(mode="json"),
        "summary_artifact": summary_reference.model_dump(mode="json"),
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = DiagnosticManifest.model_validate(
        {
            **manifest_payload,
            "content_sha256": content_sha256(manifest_payload, excluded_keys=_RUN_EXCLUSIONS),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        run_id,
        {
            "predictions.jsonl": predictions_bytes,
            "summary.json": summary_bytes,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def _read_predictions(path: Path) -> list[PredictionRecord]:
    import json

    return [
        PredictionRecord.model_validate(json.loads(line), strict=False)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
