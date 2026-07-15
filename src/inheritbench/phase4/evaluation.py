"""Exactly-once adversarial evaluation and deterministic replay."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    input_ids_sha256,
    sha256_text,
)
from inheritbench.artifacts.store import artifact_reference, verify_reference, write_atomic_bundle
from inheritbench.config import ModelConfig, load_model_config
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2.evaluation import verify_adapter
from inheritbench.day2.schemas import AdapterReference, EvaluationBreakdown, MetricValue
from inheritbench.day3_matched.distribution import _local_snapshot
from inheritbench.evaluation.metrics import aggregate_metrics, score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import render_prompt
from inheritbench.phase4.config import (
    load_adversarial_config,
    load_experiment_config,
    repository_root,
    resolve,
)
from inheritbench.phase4.protocol import find_protocol, runtime_lineage
from inheritbench.phase4.schemas import (
    Phase4EvaluationManifestV0_1,
    Phase4EvaluationSummaryV0_1,
    Phase4PredictionRecordV0_1,
    Phase4ReplayVerificationV0_1,
    Phase4SystemId,
)

_PREDICTION_EXCLUSIONS = {
    "prediction_id",
    "run_id",
    "started_at",
    "finished_at",
    "latency_ms",
    "content_sha256",
}
_RUN_EXCLUSIONS = {
    "run_id",
    "created_at",
    "finished_at",
    "relative_path",
    "byte_sha256",
    "bytes",
    "content_sha256",
}


def evaluate_adversarial(
    experiment_path: Path,
    system_id: Phase4SystemId,
    *,
    device: Literal["mps", "cpu", "cuda"] = "mps",
    resume: Path | None = None,
) -> Path:
    experiment = load_experiment_config(experiment_path)
    adversarial = load_adversarial_config(
        resolve(experiment_path, experiment.adversarial_config_path)
    )
    if device != adversarial.device:
        raise ValueError("Phase 4 adversarial inference is frozen to MPS")
    _, protocol = find_protocol(experiment_path)
    lineage = runtime_lineage(experiment_path)
    output_root = resolve(experiment_path, experiment.artifact_root)
    _reject_logical_rerun(output_root / "evaluations", system_id)
    system = next((item for item in experiment.systems if item.system_id == system_id), None)
    if system is None:
        raise ValueError(f"unknown Phase 4 system: {system_id}")
    records = _load_adversarial(resolve(experiment_path, experiment.dataset_directory))
    if len(records) != 32:
        raise ValueError("Phase 4 evaluation requires all 32 adversarial records")
    prior, prior_run_id = _resume_predictions(resume, system_id)
    resume_attempt: Literal[0, 1] = 1 if resume is not None else 0
    logical_run_id = f"phase4-adversarial-{system_id}-{protocol.content_sha256[:12]}"
    run_id = f"{logical_run_id}-attempt-{resume_attempt + 1}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(UTC)
    active = output_root / "active" / run_id
    active.mkdir(parents=True, exist_ok=False)
    predictions = list(prior)
    _write_active(active, predictions)
    adapter = next(item.adapter for item in protocol.systems if item.system_id == system_id)
    loaded: LoadedModel | None = None
    try:
        model = load_model_config(resolve(experiment_path, system.model_config_path))
        inference = _local_inference_config(model)
        loaded = _load_with_adapter(inference, adapter, repository_root(experiment_path), device)
        completed_ids = {item.example_id for item in predictions}
        for record in records:
            if record.example_id in completed_ids:
                continue
            predictions.append(
                _infer_one(
                    loaded,
                    model,
                    system_id,
                    adapter,
                    record,
                    adversarial.generation,
                    run_id,
                    lineage,
                )
            )
            _write_active(active, predictions)
    except BaseException as exc:
        if loaded is not None:
            unload_model(loaded)
            loaded = None
        failed = _finalize_run(
            output_root / "failed",
            run_id=run_id,
            logical_run_id=logical_run_id,
            resumed_from_run_id=prior_run_id,
            resume_attempt=resume_attempt,
            system_id=system_id,
            predictions=predictions,
            adapter=adapter,
            split_sha256=adversarial.adversarial_split_sha256,
            oracle_sha256=adversarial.adversarial_oracle_sha256,
            generation=adversarial.generation,
            lineage=lineage,
            created_at=created_at,
            force_failed=True,
        )
        shutil.rmtree(active, ignore_errors=True)
        raise RuntimeError(f"Phase 4 evaluation interrupted; resumable evidence: {failed}") from exc
    finally:
        if loaded is not None:
            unload_model(loaded)
    predictions.sort(key=lambda item: item.example_id)
    destination = _finalize_run(
        output_root / "evaluations",
        run_id=run_id,
        logical_run_id=logical_run_id,
        resumed_from_run_id=prior_run_id,
        resume_attempt=resume_attempt,
        system_id=system_id,
        predictions=predictions,
        adapter=adapter,
        split_sha256=adversarial.adversarial_split_sha256,
        oracle_sha256=adversarial.adversarial_oracle_sha256,
        generation=adversarial.generation,
        lineage=lineage,
        created_at=created_at,
        force_failed=False,
    )
    shutil.rmtree(active, ignore_errors=True)
    return destination


def replay_evaluation(run_directory: Path, output_root: Path) -> Path:
    manifest = Phase4EvaluationManifestV0_1.model_validate_json(
        (run_directory / "manifest.json").read_bytes(), strict=True
    )
    verify_reference(run_directory, manifest.prediction_artifact)
    verify_reference(run_directory, manifest.summary_artifact)
    predictions = _read_predictions(run_directory / "predictions.jsonl")
    for prediction in predictions:
        if prediction.status == "FAILED":
            continue
        parser = parse_action_contract(prediction.raw_output)
        metrics = score_prediction(
            parser, prediction.expected_contract, prediction.evaluation_metadata
        )
        if parser != prediction.parser_result or metrics != prediction.metrics:
            raise ValueError(f"Phase 4 replay mismatch: {prediction.prediction_id}")
    stored = Phase4EvaluationSummaryV0_1.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )
    rebuilt = build_summary(
        predictions,
        run_id=stored.run_id,
        system_id=stored.system_id,
        created_at=stored.created_at,
        finished_at=stored.finished_at,
    )
    if stored != rebuilt:
        raise ValueError("Phase 4 summary replay mismatch")
    created_at = datetime.now(UTC)
    replay_id = f"phase4-replay-evaluation-{manifest.system_id}-{uuid.uuid4().hex[:12]}"
    payload = {
        "schema_version": "phase4-replay-v0.1",
        "replay_id": replay_id,
        "kind": "evaluation",
        "original_artifact_id": manifest.run_id,
        "original_content_sha256": manifest.content_sha256,
        "recomputed_content_sha256": manifest.content_sha256,
        "byte_hashes_verified": True,
        "atomic_values_equal": True,
        "status": "PASSED",
        "lineage": manifest.lineage,
        "created_at": created_at,
    }
    verification = Phase4ReplayVerificationV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"replay_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        replay_id,
        {
            "predictions.jsonl": canonical_jsonl_bytes(predictions),
            "summary.json": canonical_json_bytes(stored) + b"\n",
            "verification.json": canonical_json_bytes(verification) + b"\n",
        },
    )


def build_summary(
    predictions: list[Phase4PredictionRecordV0_1],
    *,
    run_id: str,
    system_id: Phase4SystemId,
    created_at: datetime,
    finished_at: datetime,
) -> Phase4EvaluationSummaryV0_1:
    completed = [item for item in predictions if item.status == "COMPLETED"]
    metrics = [item.metrics for item in completed if item.metrics is not None]
    groups: dict[str, list[Phase4PredictionRecordV0_1]] = {"all": predictions}
    for prediction in predictions:
        groups.setdefault(f"family:{prediction.scenario_family}", []).append(prediction)
        groups.setdefault(
            f"family_archetype:{prediction.scenario_family}:{prediction.archetype}", []
        ).append(prediction)
        groups.setdefault(f"expected_decision:{prediction.expected_contract.decision}", []).append(
            prediction
        )
        for profile in prediction.adversarial_profiles:
            groups.setdefault(f"adversarial_profile:{profile}", []).append(prediction)
        if prediction.expected_contract.approval_required:
            groups.setdefault("approval_required", []).append(prediction)
        if prediction.expected_contract.decision in {"ask_clarification", "refuse", "no_action"}:
            groups.setdefault("abstention", []).append(prediction)
    status: Literal["COMPLETED", "FAILED"] = (
        "COMPLETED"
        if len(predictions) == 32 and all(item.status == "COMPLETED" for item in predictions)
        else "FAILED"
    )
    payload = {
        "schema_version": "phase4-evaluation-summary-v0.1",
        "run_id": run_id,
        "system_id": system_id,
        "status": status,
        "split": "adversarial",
        "prediction_counts": {
            "total": len(predictions),
            "completed": len(completed),
            "failed": len(predictions) - len(completed),
        },
        "aggregate_metrics": aggregate_metrics(metrics),
        "parser_classifications": _parser_counts(predictions),
        "breakdowns": {
            key: _breakdown(key, values).model_dump(mode="json")
            for key, values in sorted(groups.items())
        },
        "run_errors": [error for item in predictions for error in item.errors],
        "created_at": created_at,
        "finished_at": finished_at,
    }
    return Phase4EvaluationSummaryV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )


def completed_evaluations(
    experiment_path: Path,
) -> dict[Phase4SystemId, tuple[Path, Phase4EvaluationManifestV0_1]]:
    experiment = load_experiment_config(experiment_path)
    result: dict[Phase4SystemId, tuple[Path, Phase4EvaluationManifestV0_1]] = {}
    for path in sorted(
        (resolve(experiment_path, experiment.artifact_root) / "evaluations").glob("*/manifest.json")
    ):
        manifest = Phase4EvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        if manifest.system_id in result:
            raise ValueError(f"duplicate Phase 4 logical evaluation: {manifest.system_id}")
        result[manifest.system_id] = (path.parent, manifest)
    return result


def _infer_one(
    loaded: LoadedModel,
    model_config: ModelConfig,
    system_id: Phase4SystemId,
    adapter: AdapterReference | None,
    record: OpsRouteExample,
    generation: Any,
    run_id: str,
    lineage: Any,
) -> Phase4PredictionRecordV0_1:
    import torch

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    prompt_hash = None
    ids_hash = None
    prompt_count = None
    generated_count = None
    try:
        prompt = render_prompt(loaded.tokenizer, record, "0.1.0")
        prompt_hash = sha256_text(prompt)
        encoded = loaded.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        token_ids = encoded["input_ids"][0].tolist()
        prompt_count = len(token_ids)
        ids_hash = input_ids_sha256(token_ids)
        if prompt_count > 1024:
            raise ValueError(f"prompt exceeds 1024 tokens: {record.example_id}")
        encoded = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
        torch.manual_seed(generation.seed)
        with torch.inference_mode():
            generated = loaded.model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=generation.max_new_tokens,
                pad_token_id=loaded.tokenizer.pad_token_id,
            )
        _synchronize(loaded.device)
        completion = generated[0, encoded["input_ids"].shape[1] :]
        generated_count = int(completion.shape[0])
        raw_output = loaded.tokenizer.decode(completion, skip_special_tokens=True)
        parser = parse_action_contract(raw_output)
        metrics = score_prediction(parser, record.expected, record.evaluation)
        error = None
    except Exception as exc:
        raw_output = ""
        parser = None
        metrics = None
        error = exc
    message = f"{type(error).__name__}: {error}" if error else None
    lower = message.lower() if message else ""
    error_type = (
        ("OOM" if "out of memory" in lower else "TIMEOUT" if "timeout" in lower else "MODEL_ERROR")
        if error
        else None
    )
    profiles = sorted(
        {
            tag
            for tag in record.evaluation.tags
            if tag in {"prompt_injection", "conflicting_id", "prior_offer"}
        }
    )
    payload = {
        "schema_version": "phase4-prediction-v0.1",
        "prediction_id": f"phase4-prediction-{uuid.uuid4().hex}",
        "run_id": run_id,
        "status": "FAILED" if error else "COMPLETED",
        "error_type": error_type,
        "system_id": system_id,
        "split": "adversarial",
        "adapter_id": adapter.adapter_id if adapter else None,
        "example_id": record.example_id,
        "scenario_family": record.scenario_family,
        "archetype": record.archetype,
        "adversarial_profiles": profiles,
        "model_id": model_config.model_id,
        "model_revision": model_config.revision,
        "resolved_device": loaded.device,
        "resolved_dtype": loaded.dtype,
        "prompt_sha256": prompt_hash,
        "input_ids_sha256": ids_hash,
        "prompt_token_count": prompt_count,
        "generated_token_count": generated_count,
        "generation": generation.model_dump(mode="json"),
        "raw_output": raw_output,
        "parser_result": parser.model_dump(mode="json") if parser else None,
        "expected_contract": record.expected.model_dump(mode="json"),
        "evaluation_metadata": record.evaluation.model_dump(mode="json"),
        "metrics": metrics.model_dump(mode="json") if metrics else None,
        "started_at": started_at,
        "finished_at": datetime.now(UTC),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "errors": [message] if message else [],
        "lineage": lineage,
    }
    return Phase4PredictionRecordV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_EXCLUSIONS),
        },
        strict=True,
    )


def _finalize_run(
    root: Path,
    *,
    run_id: str,
    logical_run_id: str,
    resumed_from_run_id: str | None,
    resume_attempt: Literal[0, 1],
    system_id: Phase4SystemId,
    predictions: list[Phase4PredictionRecordV0_1],
    adapter: AdapterReference | None,
    split_sha256: str,
    oracle_sha256: str,
    generation: Any,
    lineage: Any,
    created_at: datetime,
    force_failed: bool,
) -> Path:
    finished_at = datetime.now(UTC)
    predictions = sorted(predictions, key=lambda item: item.example_id)
    summary = build_summary(
        predictions,
        run_id=run_id,
        system_id=system_id,
        created_at=created_at,
        finished_at=finished_at,
    )
    status: Literal["COMPLETED", "FAILED"] = "FAILED" if force_failed else summary.status
    prediction_bytes = canonical_jsonl_bytes(predictions)
    summary_bytes = canonical_json_bytes(summary) + b"\n"
    prediction_ref = artifact_reference(
        "predictions.jsonl",
        prediction_bytes,
        content_sha256=content_sha256([item.content_sha256 for item in predictions]),
    )
    summary_ref = artifact_reference(
        "summary.json", summary_bytes, content_sha256=summary.content_sha256
    )
    payload = {
        "schema_version": "phase4-evaluation-run-v0.1",
        "run_id": run_id,
        "logical_run_id": logical_run_id,
        "resumed_from_run_id": resumed_from_run_id,
        "resume_attempt": resume_attempt,
        "system_id": system_id,
        "split": "adversarial",
        "status": status,
        "expected_predictions": 32,
        "terminal_predictions": len(predictions),
        "split_sha256": split_sha256,
        "oracle_sha256": oracle_sha256,
        "adapter": adapter,
        "exactly_once_guard_sha256": content_sha256(
            {"system_id": system_id, "split": "adversarial", "split_sha256": split_sha256}
        ),
        "generation": generation.model_dump(mode="json"),
        "prediction_artifact": prediction_ref.model_dump(mode="json"),
        "summary_artifact": summary_ref.model_dump(mode="json"),
        "lineage": lineage,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = Phase4EvaluationManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )
    return write_atomic_bundle(
        root,
        run_id,
        {
            "predictions.jsonl": prediction_bytes,
            "summary.json": summary_bytes,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def _resume_predictions(
    resume: Path | None, system_id: Phase4SystemId
) -> tuple[list[Phase4PredictionRecordV0_1], str | None]:
    if resume is None:
        return [], None
    manifest = Phase4EvaluationManifestV0_1.model_validate_json(
        (resume / "manifest.json").read_bytes(), strict=True
    )
    if manifest.system_id != system_id or manifest.resume_attempt != 0:
        raise ValueError("Phase 4 permits one identical missing-record-only resume")
    predictions = _read_predictions(resume / "predictions.jsonl")
    if len({item.example_id for item in predictions}) != len(predictions):
        raise ValueError("resume evidence contains duplicate examples")
    return predictions, manifest.run_id


def _write_active(root: Path, predictions: list[Phase4PredictionRecordV0_1]) -> None:
    payload = canonical_jsonl_bytes(sorted(predictions, key=lambda item: item.example_id))
    temporary = root / ".predictions.tmp"
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, root / "predictions.jsonl")


def _local_inference_config(config: ModelConfig) -> ModelConfig:
    snapshot = _local_snapshot(config.model_id, config.revision)
    return config.model_copy(
        update={"model_id": snapshot, "tokenizer_id": snapshot, "requested_dtype": "float16"}
    )


def _load_with_adapter(
    config: ModelConfig,
    adapter: AdapterReference | None,
    root: Path,
    device: str,
) -> LoadedModel:
    loaded = load_model(config, device_override=device)
    if adapter is not None:
        from peft import PeftModel

        path = verify_adapter(adapter, root)
        peft_model: Any = PeftModel
        loaded.model = peft_model.from_pretrained(loaded.model, path, is_trainable=False)
    loaded.model.eval()
    return loaded


def _load_adversarial(dataset_root: Path) -> list[OpsRouteExample]:
    with (dataset_root / "adversarial.jsonl").open(encoding="utf-8") as handle:
        return sorted(
            [OpsRouteExample.model_validate_json(line, strict=True) for line in handle],
            key=lambda item: item.example_id,
        )


def _breakdown(key: str, predictions: list[Phase4PredictionRecordV0_1]) -> EvaluationBreakdown:
    completed = [item for item in predictions if item.status == "COMPLETED"]
    metrics = [item.metrics for item in completed if item.metrics is not None]
    return EvaluationBreakdown(
        key=key,
        prediction_count=len(predictions),
        completed_count=len(completed),
        metrics={
            name: MetricValue.model_validate(value, strict=True)
            for name, value in aggregate_metrics(metrics).items()
        },
        parser_classifications=_parser_counts(predictions),
    )


def _parser_counts(predictions: list[Phase4PredictionRecordV0_1]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        item.parser_result.classification for item in predictions if item.parser_result is not None
    )
    counts["FAILED"] = sum(item.status == "FAILED" for item in predictions)
    return dict(sorted(counts.items()))


def _read_predictions(path: Path) -> list[Phase4PredictionRecordV0_1]:
    with path.open(encoding="utf-8") as handle:
        return [
            Phase4PredictionRecordV0_1.model_validate_json(line, strict=True) for line in handle
        ]


def _reject_logical_rerun(root: Path, system_id: Phase4SystemId) -> None:
    for path in root.glob("*/manifest.json"):
        manifest = Phase4EvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        if manifest.system_id == system_id:
            raise ValueError(f"Phase 4 {system_id} adversarial evaluation may run exactly once")


def _synchronize(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()
