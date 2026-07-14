"""Bounded deterministic micro-LoRA trainability gate."""

from __future__ import annotations

import gc
import json
import math
import os
import shutil
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from inheritbench.artifacts.hashing import (
    canonical_json,
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    sha256_file,
)
from inheritbench.artifacts.schemas import GenerationConfig, ModelRole, PredictionRecord
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.blockers.subsets import SubsetManifest
from inheritbench.config import Sha256, load_model_config, load_task_config
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.evaluation.metrics import score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.inference.runner import _aggregates_by_role, _infer_one
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import build_messages, render_prompt


class MicroLoraConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["micro-lora-config-v0.1"] = "micro-lora-config-v0.1"
    rank: Literal[8] = 8
    alpha: Literal[16] = 16
    dropout: float = Field(default=0.05, ge=0, lt=1)
    learning_rate: float = Field(default=0.0002, gt=0)
    epochs: int = Field(default=2, ge=1, le=6)
    gradient_accumulation_steps: Literal[4] = 4
    target_modules: tuple[Literal["q_proj", "k_proj", "v_proj", "o_proj"], ...] = (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
    )
    seed: Literal[20260714] = 20260714
    train_dtype: Literal["float32"] = "float32"
    optimizer: Literal["AdamW"] = "AdamW"
    batch_size: Literal[1] = 1
    shuffle: Literal[False] = False


class TrainingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["micro-lora-training-v0.1"]
    run_id: str
    model_id: str
    model_revision: str
    model_role: ModelRole
    train_subset_sha256: Sha256
    validation_subset_sha256: Sha256
    training_config: MicroLoraConfig
    train_example_ids: list[str]
    validation_example_ids: list[str]
    trainable_parameters: int = Field(gt=0)
    total_parameters: int = Field(gt=0)
    trainable_fraction: float = Field(gt=0, lt=1)
    losses: list[float] = Field(min_length=1)
    initial_loss: float
    final_loss: float
    minimum_loss: float
    finite_losses: Literal[True]
    loss_decreased: bool
    optimizer_steps: int = Field(gt=0)
    duration_seconds: float = Field(ge=0)
    peak_mps_allocated_bytes: int | None = Field(default=None, ge=0)
    mps_driver_allocated_bytes_after_training: int | None = Field(default=None, ge=0)
    resolved_device: str | None = None
    resolved_dtype: str | None = None
    adapter_directory: str
    adapter_file_sha256s: dict[str, Sha256]
    content_sha256: Sha256


class TrainabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["trainability-run-v0.1"]
    run_id: str
    status: Literal["COMPLETED", "FAILED"]
    model_role: ModelRole
    training_evidence_sha256: Sha256
    predictions_byte_sha256: Sha256
    summary_byte_sha256: Sha256
    schema_valid_predictions: int = Field(ge=0)
    semantic_exact_predictions: int = Field(ge=0)
    prediction_count: int = Field(gt=0)
    aggregate_metrics: dict[str, dict[str, dict[str, float | int | None]]]
    created_at: datetime
    finished_at: datetime
    content_sha256: Sha256


class TrainabilityReplay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["trainability-replay-v0.1"]
    original_run_id: str
    status: Literal["PASSED"]
    prediction_records_verified: int
    parser_results_match: Literal[True]
    metrics_match: Literal[True]
    aggregates_match: Literal[True]
    created_at: datetime
    content_sha256: Sha256


class FailedTrainabilityAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["trainability-failure-v0.1"]
    run_id: str
    status: Literal["FAILED"]
    stage: str
    error_type: str
    error_message: str
    adapter_directory: str | None
    adapter_file_sha256s: dict[str, Sha256]
    created_at: datetime
    content_sha256: Sha256


def run_micro_lora(
    *,
    model_path: Path,
    task_path: Path,
    train_subset_path: Path,
    validation_subset_path: Path,
    dataset_directory: Path,
    device: Literal["mps", "cpu", "cuda"],
    output_root: Path,
    adapter_root: Path,
    role: Literal["source_micro_lora", "target_micro_lora"],
    training_config: MicroLoraConfig | None = None,
) -> Path:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model

    config = training_config or MicroLoraConfig()
    model_config = load_model_config(model_path)
    task_config = load_task_config(task_path)
    train_subset = _load_subset(train_subset_path, "train")
    validation_subset = _load_subset(validation_subset_path, "validation")
    train_examples = load_examples(dataset_directory, train_subset.example_ids)
    validation_examples = load_examples(dataset_directory, validation_subset.example_ids)
    _assert_split(train_examples, "train")
    _assert_split(validation_examples, "validation")

    created_at = datetime.now(UTC)
    run_id = f"micro-lora-{role}-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    training_model_config = model_config.model_copy(update={"requested_dtype": "float32"})
    loaded = load_model(training_model_config, device_override=device)
    try:
        peft_config = LoraConfig(
            r=config.rank,
            lora_alpha=config.alpha,
            lora_dropout=config.dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=list(config.target_modules),
        )
        loaded.model = get_peft_model(loaded.model, peft_config)
        loaded.model.config.use_cache = False
        loaded.model.train()
        trainable = [
            parameter for parameter in loaded.model.parameters() if parameter.requires_grad
        ]
        trainable_parameters = sum(parameter.numel() for parameter in trainable)
        total_parameters = sum(parameter.numel() for parameter in loaded.model.parameters())
        optimizer = torch.optim.AdamW(trainable, lr=config.learning_rate)
        torch.manual_seed(config.seed)
        if device == "cuda":
            torch.cuda.manual_seed_all(config.seed)
        if device == "mps":
            torch.mps.empty_cache()

        batches = [
            _encode_training_example(loaded, example, task_config.prompt_template_version)
            for example in train_examples
        ]
        losses: list[float] = []
        optimizer_steps = 0
        optimizer.zero_grad(set_to_none=True)
        started = time.perf_counter()
        for _epoch in range(config.epochs):
            for index, batch in enumerate(batches, start=1):
                outputs = loaded.model(**batch)
                loss = outputs.loss
                loss_value = float(loss.detach().cpu())
                if not math.isfinite(loss_value):
                    raise RuntimeError(f"non-finite training loss: {loss_value}")
                losses.append(loss_value)
                (loss / config.gradient_accumulation_steps).backward()
                if index % config.gradient_accumulation_steps == 0:
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_steps += 1
        if len(batches) % config.gradient_accumulation_steps:
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            optimizer_steps += 1
        if device == "mps":
            torch.mps.synchronize()
        duration = time.perf_counter() - started
        mps_driver_allocated = (
            int(torch.mps.driver_allocated_memory())
            if device == "mps" and hasattr(torch.mps, "driver_allocated_memory")
            else None
        )

        adapter_directory = _save_adapter(loaded.model, adapter_root, run_id)
        adapter_hashes = {
            str(path.relative_to(adapter_directory)): sha256_file(path)
            for path in sorted(adapter_directory.rglob("*"))
            if path.is_file()
        }
        del optimizer, batches, outputs, loss, trainable
        gc.collect()
        if device == "mps":
            torch.mps.empty_cache()
        loaded.model.eval()
        loaded.dtype = "float32"
        generation = GenerationConfig(
            do_sample=False,
            num_beams=1,
            max_new_tokens=task_config.maximum_new_tokens,
            seed=task_config.seed,
        )
        predictions = [
            _infer_one(
                loaded=loaded,
                config=model_config,
                role=role,
                example=example,
                task_config=task_config,
                generation=generation,
                run_id=run_id,
            )
            for example in validation_examples
        ]
        evidence = _training_evidence(
            run_id=run_id,
            role=role,
            model_id=model_config.model_id,
            model_revision=model_config.revision,
            train_subset=train_subset,
            validation_subset=validation_subset,
            config=config,
            losses=losses,
            optimizer_steps=optimizer_steps,
            trainable_parameters=trainable_parameters,
            total_parameters=total_parameters,
            duration=duration,
            peak_mps=None,
            mps_driver_allocated=mps_driver_allocated,
            resolved_device=loaded.device,
            resolved_dtype=loaded.dtype,
            adapter_directory=adapter_directory,
            adapter_hashes=adapter_hashes,
        )
        return _write_artifacts(
            output_root=output_root,
            evidence=evidence,
            predictions=predictions,
            created_at=created_at,
        )
    finally:
        unload_model(loaded)


def replay_trainability(run_directory: Path, output_root: Path) -> Path:
    manifest = TrainabilityManifest.model_validate_json(
        (run_directory / "manifest.json").read_bytes(), strict=True
    )
    if sha256_file(run_directory / "predictions.jsonl") != manifest.predictions_byte_sha256:
        raise ValueError("trainability prediction byte hash mismatch")
    if sha256_file(run_directory / "summary.json") != manifest.summary_byte_sha256:
        raise ValueError("trainability summary byte hash mismatch")
    predictions = _read_predictions(run_directory / "predictions.jsonl")
    for prediction in predictions:
        parser_result = parse_action_contract(prediction.raw_output)
        metrics = score_prediction(
            parser_result, prediction.expected_contract, prediction.evaluation_metadata
        )
        if parser_result != prediction.parser_result or metrics != prediction.metrics:
            raise ValueError(f"trainability replay mismatch: {prediction.prediction_id}")
    if _aggregates_by_role(predictions) != manifest.aggregate_metrics:
        raise ValueError("trainability aggregate replay mismatch")
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "trainability-replay-v0.1",
        "original_run_id": manifest.run_id,
        "status": "PASSED",
        "prediction_records_verified": len(predictions),
        "parser_results_match": True,
        "metrics_match": True,
        "aggregates_match": True,
        "created_at": created_at,
    }
    replay = TrainabilityReplay.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
    return write_atomic_bundle(
        output_root,
        f"replay-{manifest.run_id}",
        {"verification.json": canonical_json_bytes(replay) + b"\n"},
    )


def record_failed_attempt(
    *,
    run_id: str,
    stage: str,
    error_type: str,
    error_message: str,
    adapter_directory: Path | None,
    output_root: Path,
) -> Path:
    adapter_hashes = (
        {
            str(path.relative_to(adapter_directory)): sha256_file(path)
            for path in sorted(adapter_directory.rglob("*"))
            if path.is_file()
        }
        if adapter_directory is not None
        else {}
    )
    payload = {
        "schema_version": "trainability-failure-v0.1",
        "run_id": run_id,
        "status": "FAILED",
        "stage": stage,
        "error_type": error_type,
        "error_message": error_message,
        "adapter_directory": str(adapter_directory) if adapter_directory else None,
        "adapter_file_sha256s": adapter_hashes,
        "created_at": datetime.now(UTC),
    }
    failure = FailedTrainabilityAttempt.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
    return write_atomic_bundle(
        output_root,
        run_id,
        {"failure.json": canonical_json_bytes(failure) + b"\n"},
    )


def _encode_training_example(
    loaded: LoadedModel, example: OpsRouteExample, prompt_version: str
) -> dict[str, Any]:
    prompt = render_prompt(loaded.tokenizer, example, prompt_version)
    answer = canonical_json(example.expected)
    messages = [
        *build_messages(example, prompt_version),
        {"role": "assistant", "content": answer},
    ]
    full = loaded.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    prompt_ids = loaded.tokenizer(prompt, add_special_tokens=False)["input_ids"]
    encoded = loaded.tokenizer(full, return_tensors="pt", add_special_tokens=False)
    if encoded["input_ids"].shape[1] > 1024:
        raise ValueError(f"training example exceeds 1024 tokens: {example.example_id}")
    if encoded["input_ids"][0, : len(prompt_ids)].tolist() != prompt_ids:
        raise ValueError(
            f"assistant template does not preserve prompt prefix: {example.example_id}"
        )
    labels = encoded["input_ids"].clone()
    labels[:, : len(prompt_ids)] = -100
    batch = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
    batch["labels"] = labels.to(loaded.device)
    return batch


def _training_evidence(
    *,
    run_id: str,
    role: ModelRole,
    model_id: str,
    model_revision: str,
    train_subset: SubsetManifest,
    validation_subset: SubsetManifest,
    config: MicroLoraConfig,
    losses: list[float],
    optimizer_steps: int,
    trainable_parameters: int,
    total_parameters: int,
    duration: float,
    peak_mps: int | None,
    mps_driver_allocated: int | None,
    resolved_device: str,
    resolved_dtype: str,
    adapter_directory: Path,
    adapter_hashes: dict[str, str],
) -> TrainingEvidence:
    payload = {
        "schema_version": "micro-lora-training-v0.1",
        "run_id": run_id,
        "model_id": model_id,
        "model_revision": model_revision,
        "model_role": role,
        "train_subset_sha256": train_subset.content_sha256,
        "validation_subset_sha256": validation_subset.content_sha256,
        "training_config": config,
        "train_example_ids": train_subset.example_ids,
        "validation_example_ids": validation_subset.example_ids,
        "trainable_parameters": trainable_parameters,
        "total_parameters": total_parameters,
        "trainable_fraction": trainable_parameters / total_parameters,
        "losses": losses,
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "minimum_loss": min(losses),
        "finite_losses": True,
        "loss_decreased": losses[-1] < losses[0],
        "optimizer_steps": optimizer_steps,
        "duration_seconds": duration,
        "peak_mps_allocated_bytes": peak_mps,
        "mps_driver_allocated_bytes_after_training": mps_driver_allocated,
        "resolved_device": resolved_device,
        "resolved_dtype": resolved_dtype,
        "adapter_directory": str(adapter_directory),
        "adapter_file_sha256s": adapter_hashes,
    }
    return TrainingEvidence.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _write_artifacts(
    *,
    output_root: Path,
    evidence: TrainingEvidence,
    predictions: list[PredictionRecord],
    created_at: datetime,
) -> Path:
    finished_at = datetime.now(UTC)
    predictions_bytes = canonical_jsonl_bytes(predictions)
    aggregates = _aggregates_by_role(predictions)
    schema_valid = sum(
        prediction.parser_result is not None
        and prediction.parser_result.classification in {"STRICT_VALID", "NORMALIZED_VALID"}
        for prediction in predictions
    )
    semantic_exact = sum(
        prediction.metrics is not None and prediction.metrics.semantic_decision_score_v0 == 1
        for prediction in predictions
    )
    summary = {
        "schema_version": "trainability-summary-v0.1",
        "run_id": evidence.run_id,
        "model_role": evidence.model_role,
        "schema_valid_predictions": schema_valid,
        "semantic_exact_predictions": semantic_exact,
        "prediction_count": len(predictions),
        "loss_decreased": evidence.loss_decreased,
        "initial_loss": evidence.initial_loss,
        "final_loss": evidence.final_loss,
        "aggregate_metrics": aggregates,
    }
    summary_bytes = canonical_json_bytes(summary) + b"\n"
    manifest_payload = {
        "schema_version": "trainability-run-v0.1",
        "run_id": evidence.run_id,
        "status": (
            "FAILED"
            if any(prediction.status == "FAILED" for prediction in predictions)
            else "COMPLETED"
        ),
        "model_role": evidence.model_role,
        "training_evidence_sha256": evidence.content_sha256,
        "predictions_byte_sha256": _sha256_bytes(predictions_bytes),
        "summary_byte_sha256": _sha256_bytes(summary_bytes),
        "schema_valid_predictions": schema_valid,
        "semantic_exact_predictions": semantic_exact,
        "prediction_count": len(predictions),
        "aggregate_metrics": aggregates,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = TrainabilityManifest.model_validate(
        {
            **manifest_payload,
            "content_sha256": content_sha256(
                manifest_payload,
                excluded_keys={"content_sha256", "created_at", "finished_at", "run_id"},
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        evidence.run_id,
        {
            "training.json": canonical_json_bytes(evidence) + b"\n",
            "predictions.jsonl": predictions_bytes,
            "summary.json": summary_bytes,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def _save_adapter(model: Any, adapter_root: Path, run_id: str) -> Path:
    adapter_root.mkdir(parents=True, exist_ok=True)
    destination = adapter_root / run_id
    if destination.exists():
        raise FileExistsError(f"adapter directory already exists: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=f".tmp-{run_id}-", dir=adapter_root))
    try:
        model.save_pretrained(staging, safe_serialization=True)
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def _load_subset(path: Path, split: Literal["train", "validation"]) -> SubsetManifest:
    subset = SubsetManifest.model_validate_json(path.read_bytes(), strict=True)
    if subset.source_split != split or subset.fixture_evidence:
        raise ValueError(f"expected a non-fixture {split} subset")
    return subset


def _assert_split(examples: list[OpsRouteExample], split: Literal["train", "validation"]) -> None:
    if any(example.split != split for example in examples):
        raise ValueError(f"loaded examples include records outside {split}")


def _read_predictions(path: Path) -> list[PredictionRecord]:
    return [
        PredictionRecord.model_validate(json.loads(line), strict=False)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _sha256_bytes(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()
