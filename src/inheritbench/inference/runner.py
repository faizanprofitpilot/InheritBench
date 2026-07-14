"""Real pair inference, immutable finalization, and metric replay."""

from __future__ import annotations

import json
import platform
import subprocess
import time
import uuid
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Literal

import psutil

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    input_ids_sha256,
    sha256_bytes,
    sha256_text,
)
from inheritbench.artifacts.schemas import (
    EnvironmentState,
    GenerationConfig,
    GitState,
    ModelRole,
    PredictionRecord,
    ReplayVerification,
    RunSummary,
    SmokeRunManifest,
)
from inheritbench.artifacts.store import artifact_reference, verify_reference, write_atomic_bundle
from inheritbench.config import ModelConfig, OpsRouteTaskConfig, load_model_config, load_task_config
from inheritbench.data.opsroute.generate import is_fixture_evidence, load_examples
from inheritbench.data.opsroute.schemas import DatasetManifest, OpsRouteExample, SmokeIdsManifest
from inheritbench.evaluation.metrics import aggregate_metrics, score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.models.inspection import PairInspectionResult, inspect_pair, write_inspection
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import render_prompt

_PREDICTION_CONTENT_EXCLUSIONS = {
    "prediction_id",
    "run_id",
    "started_at",
    "finished_at",
    "latency_ms",
    "content_sha256",
}
_RUN_CONTENT_EXCLUSIONS = {
    "run_id",
    "created_at",
    "finished_at",
    "relative_path",
    "byte_sha256",
    "bytes",
    "content_sha256",
}


def run_pair_inference(
    *,
    source_path: Path,
    target_path: Path,
    task_path: Path,
    examples_path: Path,
    device: Literal["auto", "mps", "cpu", "cuda"],
    output_root: Path,
    command: list[str],
) -> Path:
    source_config = load_model_config(source_path)
    target_config = load_model_config(target_path)
    task_config = load_task_config(task_path)
    smoke = SmokeIdsManifest.model_validate_json(examples_path.read_bytes(), strict=True)
    if any(is_fixture_evidence(example_id) for example_id in smoke.example_ids):
        raise ValueError("fixture examples cannot be used as benchmark evidence")
    dataset_directory = examples_path.parent
    dataset_manifest = DatasetManifest.model_validate_json(
        (dataset_directory / "manifest.json").read_bytes(), strict=True
    )
    examples = load_examples(dataset_directory, smoke.example_ids)
    if any(example.split not in {"test", "adversarial"} for example in examples):
        raise ValueError("smoke inference requires held-out test or adversarial examples")

    inspection = _loaded_inspection(
        source_config,
        target_config,
        output_root.parent / "inspections",
        device,
    )
    if inspection.heterogeneity_verdict != "CONFIRMED":
        raise ValueError("pair inspection did not confirm model heterogeneity")

    created_at = datetime.now(UTC)
    run_id = f"day1-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    generation = GenerationConfig(
        do_sample=False,
        num_beams=1,
        max_new_tokens=task_config.maximum_new_tokens,
        seed=task_config.seed,
    )
    predictions: list[PredictionRecord] = []
    run_errors: list[str] = []
    model_specs: list[tuple[Literal["source_base", "target_base"], ModelConfig]] = [
        ("source_base", source_config),
        ("target_base", target_config),
    ]
    for role, config in model_specs:
        model_predictions = _infer_model(
            config=config,
            role=role,
            examples=examples,
            task_config=task_config,
            generation=generation,
            run_id=run_id,
            device=device,
        )
        predictions.extend(model_predictions)
        run_errors.extend(
            f"{prediction.model_role}:{prediction.example_id}:{message}"
            for prediction in model_predictions
            for message in prediction.errors
        )

    predictions.sort(key=lambda prediction: (prediction.model_role, prediction.example_id))
    status: Literal["COMPLETED", "FAILED"] = (
        "FAILED"
        if any(prediction.status == "FAILED" for prediction in predictions)
        else "COMPLETED"
    )
    finished_at = datetime.now(UTC)
    counts = {
        "total": len(predictions),
        "completed": sum(prediction.status == "COMPLETED" for prediction in predictions),
        "failed": sum(prediction.status == "FAILED" for prediction in predictions),
    }
    aggregates = _aggregates_by_role(predictions)
    valid_counts = {
        role: sum(
            prediction.parser_result is not None
            and prediction.parser_result.classification in {"STRICT_VALID", "NORMALIZED_VALID"}
            for prediction in predictions
            if prediction.model_role == role
        )
        for role in ("source_base", "target_base")
    }
    summary_payload = {
        "schema_version": "run-summary-v0.1",
        "run_id": run_id,
        "status": status,
        "prediction_counts": counts,
        "aggregate_metrics": aggregates,
        "model_valid_contract_counts": valid_counts,
        "run_errors": run_errors,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    summary = RunSummary.model_validate(
        {
            **summary_payload,
            "content_sha256": content_sha256(
                summary_payload, excluded_keys=_RUN_CONTENT_EXCLUSIONS
            ),
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
    environment = _environment_state()
    git_state = _git_state()
    manifest_payload = {
        "schema_version": "smoke-run-v0.1",
        "run_id": run_id,
        "run_type": "day1_pair_smoke",
        "status": status,
        "git": git_state.model_dump(mode="json"),
        "environment": environment.model_dump(mode="json"),
        "source_config_sha256": content_sha256(source_config),
        "target_config_sha256": content_sha256(target_config),
        "pair_inspection_sha256": inspection.content_sha256,
        "task_config_sha256": content_sha256(task_config),
        "dataset_sha256": dataset_manifest.dataset_sha256,
        "split_manifest_sha256": dataset_manifest.split_manifest_sha256,
        "smoke_ids_sha256": smoke.content_sha256,
        "command": command,
        "generation_config": generation.model_dump(mode="json"),
        "seed": task_config.seed,
        "prediction_artifact": prediction_reference.model_dump(mode="json"),
        "summary_artifact": summary_reference.model_dump(mode="json"),
        "aggregate_metrics": aggregates,
        "prediction_counts": counts,
        "run_errors": run_errors,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = SmokeRunManifest.model_validate(
        {
            **manifest_payload,
            "content_sha256": content_sha256(
                manifest_payload, excluded_keys=_RUN_CONTENT_EXCLUSIONS
            ),
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


def _infer_model(
    *,
    config: ModelConfig,
    role: Literal["source_base", "target_base"],
    examples: list[OpsRouteExample],
    task_config: OpsRouteTaskConfig,
    generation: GenerationConfig,
    run_id: str,
    device: str,
) -> list[PredictionRecord]:
    try:
        loaded = load_model(config, device_override=device)
    except Exception as exc:
        now = datetime.now(UTC)
        return [
            _failed_prediction(
                config=config,
                role=role,
                example=example,
                task_config=task_config,
                generation=generation,
                run_id=run_id,
                started_at=now,
                finished_at=datetime.now(UTC),
                error=exc,
                loaded=None,
            )
            for example in examples
        ]
    try:
        return [
            _infer_one(
                loaded=loaded,
                config=config,
                role=role,
                example=example,
                task_config=task_config,
                generation=generation,
                run_id=run_id,
            )
            for example in examples
        ]
    finally:
        unload_model(loaded)


def _infer_one(
    *,
    loaded: LoadedModel,
    config: ModelConfig,
    role: ModelRole,
    example: OpsRouteExample,
    task_config: OpsRouteTaskConfig,
    generation: GenerationConfig,
    run_id: str,
) -> PredictionRecord:
    import torch

    started_at = datetime.now(UTC)
    monotonic_start = time.perf_counter()
    prompt_hash: str | None = None
    ids_hash: str | None = None
    prompt_token_count: int | None = None
    try:
        prompt = render_prompt(
            loaded.tokenizer,
            example,
            task_config.prompt_template_version,
        )
        prompt_hash = sha256_text(prompt)
        encoded = loaded.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        token_ids = encoded["input_ids"][0].tolist()
        prompt_token_count = len(token_ids)
        ids_hash = input_ids_sha256(token_ids)
        if len(token_ids) > task_config.maximum_prompt_tokens:
            raise ValueError(
                f"prompt has {len(token_ids)} tokens; limit is {task_config.maximum_prompt_tokens}"
            )
        encoded = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
        torch.manual_seed(generation.seed)
        if loaded.device == "cuda":
            torch.cuda.manual_seed_all(generation.seed)
        with torch.inference_mode():
            generated = loaded.model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=generation.max_new_tokens,
                pad_token_id=loaded.tokenizer.pad_token_id,
            )
        if loaded.device == "mps":
            torch.mps.synchronize()
        if loaded.device == "cuda":
            torch.cuda.synchronize()
        completion_ids = generated[0, encoded["input_ids"].shape[1] :]
        generated_token_count = int(completion_ids.shape[0])
        eos_token_ids = _generation_eos_token_ids(loaded)
        finish_condition: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"]
        if generated_token_count and int(completion_ids[-1]) in eos_token_ids:
            finish_condition = "EOS"
        elif generated_token_count >= generation.max_new_tokens:
            finish_condition = "MAX_NEW_TOKENS"
        else:
            finish_condition = "OTHER"
        raw_output = loaded.tokenizer.decode(completion_ids, skip_special_tokens=True)
        parser_result = parse_action_contract(raw_output)
        metrics = score_prediction(parser_result, example.expected, example.evaluation)
        finished_at = datetime.now(UTC)
        payload = {
            "schema_version": "prediction-v0.1",
            "prediction_id": f"pred-{uuid.uuid4().hex}",
            "run_id": run_id,
            "status": "COMPLETED",
            "error_type": None,
            "example_id": example.example_id,
            "split": example.split,
            "model_role": role,
            "model_id": config.model_id,
            "model_revision": config.revision,
            "model_config_sha256": content_sha256(config),
            "architecture_class": type(loaded.model).__name__,
            "resolved_device": loaded.device,
            "resolved_dtype": loaded.dtype,
            "task_version": task_config.task_version,
            "template_version": task_config.template_version,
            "prompt_template_version": task_config.prompt_template_version,
            "prompt_sha256": prompt_hash,
            "input_ids_sha256": ids_hash,
            "generation": generation.model_dump(mode="json"),
            "prompt_token_count": prompt_token_count,
            "generated_token_count": generated_token_count,
            "finish_condition": finish_condition,
            "generation_eos_token_ids": eos_token_ids,
            "decoded_special_tokens_skipped": True,
            "raw_output": raw_output,
            "parser_result": parser_result.model_dump(mode="json"),
            "expected_contract": example.expected.model_dump(mode="json"),
            "expected_contract_sha256": content_sha256(example.expected),
            "evaluation_metadata": example.evaluation.model_dump(mode="json"),
            "metrics": metrics.model_dump(mode="json"),
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_ms": max(0, round((time.perf_counter() - monotonic_start) * 1000)),
            "errors": [],
        }
        return PredictionRecord.model_validate(
            {
                **payload,
                "content_sha256": content_sha256(
                    payload, excluded_keys=_PREDICTION_CONTENT_EXCLUSIONS
                ),
            },
            strict=True,
        )
    except Exception as exc:
        return _failed_prediction(
            config=config,
            role=role,
            example=example,
            task_config=task_config,
            generation=generation,
            run_id=run_id,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            error=exc,
            loaded=loaded,
            prompt_sha256=prompt_hash,
            ids_sha256=ids_hash,
            prompt_token_count=prompt_token_count,
            latency_ms=max(0, round((time.perf_counter() - monotonic_start) * 1000)),
        )


def _failed_prediction(
    *,
    config: ModelConfig,
    role: ModelRole,
    example: OpsRouteExample,
    task_config: OpsRouteTaskConfig,
    generation: GenerationConfig,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    error: Exception,
    loaded: LoadedModel | None,
    prompt_sha256: str | None = None,
    ids_sha256: str | None = None,
    prompt_token_count: int | None = None,
    latency_ms: int = 0,
) -> PredictionRecord:
    message = f"{type(error).__name__}: {error}"
    lower = message.lower()
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] = (
        "OOM" if "out of memory" in lower else "TIMEOUT" if "timeout" in lower else "MODEL_ERROR"
    )
    payload = {
        "schema_version": "prediction-v0.1",
        "prediction_id": f"pred-{uuid.uuid4().hex}",
        "run_id": run_id,
        "status": "FAILED",
        "error_type": error_type,
        "example_id": example.example_id,
        "split": example.split,
        "model_role": role,
        "model_id": config.model_id,
        "model_revision": config.revision,
        "model_config_sha256": content_sha256(config),
        "architecture_class": type(loaded.model).__name__ if loaded is not None else None,
        "resolved_device": loaded.device if loaded is not None else None,
        "resolved_dtype": loaded.dtype if loaded is not None else None,
        "task_version": task_config.task_version,
        "template_version": task_config.template_version,
        "prompt_template_version": task_config.prompt_template_version,
        "prompt_sha256": prompt_sha256,
        "input_ids_sha256": ids_sha256,
        "generation": generation.model_dump(mode="json"),
        "prompt_token_count": prompt_token_count,
        "generated_token_count": None,
        "finish_condition": None,
        "generation_eos_token_ids": (
            _generation_eos_token_ids(loaded) if loaded is not None else []
        ),
        "decoded_special_tokens_skipped": None,
        "raw_output": "",
        "parser_result": None,
        "expected_contract": example.expected.model_dump(mode="json"),
        "expected_contract_sha256": content_sha256(example.expected),
        "evaluation_metadata": example.evaluation.model_dump(mode="json"),
        "metrics": None,
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": latency_ms,
        "errors": [message],
    }
    return PredictionRecord.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_CONTENT_EXCLUSIONS),
        },
        strict=True,
    )


def replay_run(*, run_directory: Path, output_root: Path, verify_stored: bool) -> Path:
    manifest = SmokeRunManifest.model_validate_json(
        (run_directory / "manifest.json").read_bytes(), strict=True
    )
    if verify_stored:
        verify_reference(run_directory, manifest.prediction_artifact)
        verify_reference(run_directory, manifest.summary_artifact)
    predictions = _read_predictions(run_directory / "predictions.jsonl")
    rebuilt: list[PredictionRecord] = []
    parser_match = True
    metrics_match = True
    for prediction in predictions:
        if prediction.status == "FAILED":
            rebuilt.append(prediction)
            continue
        parser_result = parse_action_contract(prediction.raw_output)
        metrics = score_prediction(
            parser_result, prediction.expected_contract, prediction.evaluation_metadata
        )
        parser_match = parser_match and parser_result == prediction.parser_result
        metrics_match = metrics_match and metrics == prediction.metrics
        raw = prediction.model_dump(mode="python")
        raw["parser_result"] = parser_result
        raw["metrics"] = metrics
        rebuilt.append(PredictionRecord.model_validate(raw, strict=True))
    if not parser_match or not metrics_match:
        raise ValueError(
            f"replay mismatch: parser_match={parser_match}, metrics_match={metrics_match}"
        )
    original_summary = RunSummary.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )
    summary_matches = _aggregates_by_role(
        rebuilt
    ) == original_summary.aggregate_metrics and original_summary.prediction_counts["total"] == len(
        rebuilt
    )
    if not summary_matches:
        raise ValueError("recomputed aggregate summary differs from stored summary")
    replay_id = f"replay-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    verification_payload = {
        "schema_version": "replay-verification-v0.1",
        "replay_id": replay_id,
        "original_run_id": manifest.run_id,
        "status": "PASSED",
        "original_prediction_byte_sha256": manifest.prediction_artifact.byte_sha256,
        "original_summary_byte_sha256": manifest.summary_artifact.byte_sha256,
        "prediction_records_verified": len(rebuilt),
        "parser_results_match": parser_match,
        "metrics_match": metrics_match,
        "summary_matches": summary_matches,
        "created_at": datetime.now(UTC),
    }
    verification = ReplayVerification.model_validate(
        {
            **verification_payload,
            "content_sha256": content_sha256(
                verification_payload, excluded_keys=_RUN_CONTENT_EXCLUSIONS
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        replay_id,
        {
            "predictions.jsonl": canonical_jsonl_bytes(rebuilt),
            "summary.json": canonical_json_bytes(original_summary) + b"\n",
            "verification.json": canonical_json_bytes(verification) + b"\n",
        },
    )


def _read_predictions(path: Path) -> list[PredictionRecord]:
    records: list[PredictionRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            records.append(PredictionRecord.model_validate(json.loads(line), strict=False))
    return records


def _aggregates_by_role(
    predictions: list[PredictionRecord],
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    roles = sorted({prediction.model_role for prediction in predictions})
    return {
        role: aggregate_metrics(
            [
                prediction.metrics
                for prediction in predictions
                if prediction.model_role == role and prediction.metrics is not None
            ]
        )
        for role in roles
    }


def _generation_eos_token_ids(loaded: LoadedModel) -> list[int]:
    generation_config = getattr(loaded.model, "generation_config", None)
    configured = getattr(generation_config, "eos_token_id", None)
    if configured is None:
        configured = getattr(loaded.tokenizer, "eos_token_id", None)
    if configured is None:
        return []
    if isinstance(configured, int):
        return [configured]
    return [int(token_id) for token_id in configured]


def _loaded_inspection(
    source: ModelConfig,
    target: ModelConfig,
    inspection_root: Path,
    device: str,
) -> PairInspectionResult:
    if inspection_root.is_dir():
        for path in sorted(inspection_root.glob("*.json"), reverse=True):
            try:
                result = PairInspectionResult.model_validate_json(path.read_bytes(), strict=True)
            except Exception:
                continue
            if (
                result.inspection_mode == "loaded"
                and result.source.model_id == source.model_id
                and result.source.revision == source.revision
                and result.target.model_id == target.model_id
                and result.target.revision == target.revision
            ):
                return result
    result = inspect_pair(source, target, mode="loaded", device_override=device)
    write_inspection(result, inspection_root)
    return result


def _environment_state() -> EnvironmentState:
    package_names = [
        "inheritbench",
        "torch",
        "transformers",
        "accelerate",
        "pydantic",
        "PyYAML",
    ]
    packages: dict[str, str] = {}
    for name in package_names:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = "unavailable"
    hardware = {
        "machine": platform.machine(),
        "cpu_logical": psutil.cpu_count(),
        "ram_bytes": psutil.virtual_memory().total,
    }
    python_version = platform.python_version()
    os_name = platform.platform()
    payload = {
        "python": python_version,
        "packages": packages,
        "os": os_name,
        "hardware": hardware,
    }
    return EnvironmentState(
        fingerprint_sha256=content_sha256(payload),
        python=python_version,
        packages=packages,
        os=os_name,
        hardware=hardware,
    )


def _git_state() -> GitState:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
    ).stdout
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], check=True, capture_output=True
    ).stdout
    return GitState(
        commit=commit,
        worktree_dirty=bool(status),
        tracked_diff_sha256=sha256_bytes(diff) if diff else None,
    )
