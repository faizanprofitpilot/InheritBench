"""Resumable Day 2 LoRA training and safety-first checkpoint selection."""

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

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_file
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.config import ModelConfig
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2.config import (
    load_experiment_config,
    load_method_config,
    method_config_hash,
    resolved_model_config,
)
from inheritbench.day2.data import find_data_bundle, load_schedule, load_subset
from inheritbench.day2.evaluation import (
    adapter_reference,
    evaluate_checkpoint,
    evaluation_summary,
    verify_adapter,
)
from inheritbench.day2.schemas import (
    AdapterReference,
    CheckpointDecisionV0_1,
    CheckpointManifestV0_1,
    CheckpointScore,
    Day2SubsetManifest,
    MethodConfigV0_2,
    TrainingRunManifestV0_2,
    TrainingScheduleManifestV0_1,
    TrainingTelemetryPoint,
)
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import build_messages, render_prompt

_RUN_EXCLUSIONS = {"run_id", "created_at", "finished_at", "content_sha256"}
_CHECKPOINT_EXCLUSIONS = {"created_at", "content_sha256"}


def train_method(
    *,
    experiment_path: Path,
    method_path: Path,
    device: Literal["mps", "cpu", "cuda"] = "mps",
    resume_checkpoint: Path | None = None,
) -> tuple[Path, Path]:
    import torch
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    from transformers import get_linear_schedule_with_warmup

    experiment = load_experiment_config(experiment_path)
    method = load_method_config(method_path)
    if method.training_kind != "lora" or method.training is None:
        raise ValueError(f"{method.method_id} is not trainable")
    bundle = find_data_bundle(experiment_path, experiment)
    subset = load_subset(bundle, method.training.train_manifest_name)
    schedule = load_schedule(bundle, method.training.schedule_name)
    _validate_training_inputs(method, subset, schedule)
    dataset_directory = _resolve(experiment_path, experiment.dataset_directory)
    examples = {
        item.example_id: item for item in load_examples(dataset_directory, subset.example_ids)
    }
    if any(item.split != "train" for item in examples.values()):
        raise ValueError("training schedule contains held-out records")

    artifact_root = _resolve(experiment_path, experiment.artifact_root)
    adapter_root = _resolve(experiment_path, experiment.adapter_root)
    adapter_root.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC)
    run_id = f"day2-train-{method.method_id}-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    active = artifact_root / "active" / run_id
    active.mkdir(parents=True, exist_ok=False)
    model_config = resolved_model_config(method_path, method)
    training_model_config = model_config.model_copy(update={"requested_dtype": "float32"})
    loaded: LoadedModel | None = None
    optimizer: Any = None
    scheduler: Any = None
    losses: list[float] = []
    telemetry: list[TrainingTelemetryPoint] = []
    checkpoint_ids: list[str] = []
    cursor = 0
    optimizer_steps = 0
    processed_tokens = 0
    trainable_parameters = 0
    total_parameters = 0
    resumed_from_run_id: str | None = None
    resumed_from_checkpoint_id: str | None = None
    started = time.perf_counter()
    try:
        loaded = load_model(training_model_config, device_override=device)
        if resume_checkpoint is None:
            peft_config = LoraConfig(
                r=method.training.lora.rank,
                lora_alpha=method.training.lora.alpha,
                lora_dropout=method.training.lora.dropout,
                bias=method.training.lora.bias,
                task_type=TaskType.CAUSAL_LM,
                target_modules=[str(item) for item in method.training.lora.target_modules],
            )
            loaded.model = get_peft_model(loaded.model, peft_config)
        else:
            checkpoint = _load_checkpoint_manifest(resume_checkpoint)
            _validate_resume(checkpoint, method, schedule, resume_checkpoint)
            loaded.model = PeftModel.from_pretrained(
                loaded.model, resume_checkpoint, is_trainable=True
            )
            resumed_from_run_id = checkpoint.run_id
            resumed_from_checkpoint_id = checkpoint.checkpoint_id
        loaded.model.config.use_cache = False
        loaded.model.train()
        trainable = [item for item in loaded.model.parameters() if item.requires_grad]
        trainable_parameters = sum(item.numel() for item in trainable)
        total_parameters = sum(item.numel() for item in loaded.model.parameters())
        optimizer = torch.optim.AdamW(
            trainable,
            lr=method.training.optimizer.learning_rate,
            betas=(
                method.training.optimizer.betas[0],
                method.training.optimizer.betas[1],
            ),
            eps=method.training.optimizer.epsilon,
            weight_decay=method.training.optimizer.weight_decay,
        )
        scheduler_factory: Any = get_linear_schedule_with_warmup
        scheduler = scheduler_factory(
            optimizer,
            num_warmup_steps=method.training.scheduler.warmup_steps,
            num_training_steps=method.training.optimizer_steps,
        )
        torch.manual_seed(method.seed)
        if device == "cuda":
            torch.cuda.manual_seed_all(method.seed)
        if resume_checkpoint is not None:
            state = torch.load(
                resume_checkpoint / "trainer_state.pt", map_location="cpu", weights_only=False
            )
            optimizer.load_state_dict(state["optimizer"])
            scheduler.load_state_dict(state["scheduler"])
            torch.set_rng_state(state["torch_rng_state"])
            if device == "cuda" and state.get("cuda_rng_state") is not None:
                torch.cuda.set_rng_state_all(state["cuda_rng_state"])
            cursor = int(state["schedule_cursor"])
            optimizer_steps = int(state["optimizer_step"])
            processed_tokens = int(state["processed_tokens"])
            losses = [float(item) for item in state["losses"]]
            telemetry = [
                TrainingTelemetryPoint.model_validate(item, strict=True)
                for item in state["telemetry"]
            ]
        _write_active(
            active,
            _run_manifest(
                run_id=run_id,
                method=method,
                model_config=model_config,
                schedule=schedule,
                subset=subset,
                status="NOT_RUN",
                failure_code=None,
                failure_message=None,
                resumed_from_run_id=resumed_from_run_id,
                resumed_from_checkpoint_id=resumed_from_checkpoint_id,
                trainable_parameters=trainable_parameters,
                total_parameters=total_parameters,
                optimizer_steps=optimizer_steps,
                processed_tokens=processed_tokens,
                losses=losses,
                telemetry=telemetry,
                checkpoint_ids=checkpoint_ids,
                duration=time.perf_counter() - started,
                device=loaded.device,
                dtype=loaded.dtype,
                created_at=created_at,
            ),
        )
        while cursor < len(schedule.items):
            group = schedule.items[cursor : cursor + method.training.gradient_accumulation_steps]
            optimizer.zero_grad(set_to_none=True)
            group_losses: list[float] = []
            for item in group:
                batch = encode_training_example(
                    loaded, examples[item.example_id], method.prompt_template_version
                )
                output = loaded.model(**batch)
                loss = output.loss
                value = float(loss.detach().cpu())
                if not math.isfinite(value):
                    raise FloatingPointError(f"non-finite loss at cursor {item.cursor}: {value}")
                (loss / len(group)).backward()
                group_losses.append(value)
                processed_tokens += item.sequence_tokens
                cursor += 1
                del batch, output, loss
            gradient_norm = float(
                torch.nn.utils.clip_grad_norm_(trainable, method.training.gradient_clip_norm)
            )
            if not math.isfinite(gradient_norm) or gradient_norm > 100:
                raise FloatingPointError(f"unstable gradient norm: {gradient_norm}")
            optimizer.step()
            scheduler.step()
            optimizer_steps += 1
            mean_loss = sum(group_losses) / len(group_losses)
            losses.append(mean_loss)
            point = TrainingTelemetryPoint(
                optimizer_step=optimizer_steps,
                schedule_cursor=cursor,
                processed_tokens=processed_tokens,
                loss=mean_loss,
                learning_rate=float(scheduler.get_last_lr()[0]),
                gradient_norm=gradient_norm,
                mps_current_allocated_bytes=_mps_current(device),
                mps_driver_allocated_bytes=_mps_driver(device),
            )
            telemetry.append(point)
            if optimizer_steps in schedule.checkpoint_steps:
                checkpoint = _save_checkpoint(
                    loaded=loaded,
                    optimizer=optimizer,
                    scheduler=scheduler,
                    adapter_root=adapter_root,
                    run_id=run_id,
                    method=method,
                    schedule=schedule,
                    cursor=cursor,
                    optimizer_step=optimizer_steps,
                    processed_tokens=processed_tokens,
                    losses=losses,
                    telemetry=telemetry,
                )
                checkpoint_ids.append(checkpoint.checkpoint_id)
            _write_active(
                active,
                _run_manifest(
                    run_id=run_id,
                    method=method,
                    model_config=model_config,
                    schedule=schedule,
                    subset=subset,
                    status="NOT_RUN",
                    failure_code=None,
                    failure_message=None,
                    resumed_from_run_id=resumed_from_run_id,
                    resumed_from_checkpoint_id=resumed_from_checkpoint_id,
                    trainable_parameters=trainable_parameters,
                    total_parameters=total_parameters,
                    optimizer_steps=optimizer_steps,
                    processed_tokens=processed_tokens,
                    losses=losses,
                    telemetry=telemetry,
                    checkpoint_ids=checkpoint_ids,
                    duration=time.perf_counter() - started,
                    device=loaded.device,
                    dtype=loaded.dtype,
                    created_at=created_at,
                ),
            )
        if (
            optimizer_steps != schedule.optimizer_steps
            or processed_tokens != schedule.processed_tokens
        ):
            raise RuntimeError("training did not consume the frozen schedule exactly")
        completed = _run_manifest(
            run_id=run_id,
            method=method,
            model_config=model_config,
            schedule=schedule,
            subset=subset,
            status="COMPLETED",
            failure_code=None,
            failure_message=None,
            resumed_from_run_id=resumed_from_run_id,
            resumed_from_checkpoint_id=resumed_from_checkpoint_id,
            trainable_parameters=trainable_parameters,
            total_parameters=total_parameters,
            optimizer_steps=optimizer_steps,
            processed_tokens=processed_tokens,
            losses=losses,
            telemetry=telemetry,
            checkpoint_ids=checkpoint_ids,
            duration=time.perf_counter() - started,
            device=loaded.device,
            dtype=loaded.dtype,
            created_at=created_at,
        )
        training_path = write_atomic_bundle(
            artifact_root / "training",
            run_id,
            {"manifest.json": canonical_json_bytes(completed) + b"\n"},
        )
    except BaseException as exc:
        failed = _run_manifest(
            run_id=run_id,
            method=method,
            model_config=model_config,
            schedule=schedule,
            subset=subset,
            status="FAILED",
            failure_code=_failure_code(exc),
            failure_message=f"{type(exc).__name__}: {exc}",
            resumed_from_run_id=resumed_from_run_id,
            resumed_from_checkpoint_id=resumed_from_checkpoint_id,
            trainable_parameters=trainable_parameters,
            total_parameters=total_parameters,
            optimizer_steps=optimizer_steps,
            processed_tokens=processed_tokens,
            losses=losses,
            telemetry=telemetry,
            checkpoint_ids=checkpoint_ids,
            duration=time.perf_counter() - started,
            device=loaded.device if loaded else None,
            dtype=loaded.dtype if loaded else None,
            created_at=created_at,
        )
        write_atomic_bundle(
            artifact_root / "failed",
            run_id,
            {"manifest.json": canonical_json_bytes(failed) + b"\n"},
        )
        shutil.rmtree(active, ignore_errors=True)
        raise
    finally:
        if loaded is not None:
            unload_model(loaded)
        del optimizer, scheduler
        gc.collect()
    shutil.rmtree(active, ignore_errors=True)
    decision_path = validate_and_select_checkpoints(
        experiment_path=experiment_path,
        method_path=method_path,
        training_manifest=completed,
        device=device,
    )
    return training_path, decision_path


def validate_and_select_checkpoints(
    *,
    experiment_path: Path,
    method_path: Path,
    training_manifest: TrainingRunManifestV0_2,
    device: Literal["mps", "cpu", "cuda"],
) -> Path:
    experiment = load_experiment_config(experiment_path)
    method = load_method_config(method_path)
    adapter_root = _resolve(experiment_path, experiment.adapter_root)
    scores: list[CheckpointScore] = []
    for checkpoint_id in training_manifest.checkpoint_ids:
        checkpoint_directory = adapter_root / checkpoint_id
        checkpoint = _load_checkpoint_manifest(checkpoint_directory)
        reference = adapter_reference(checkpoint_directory, adapter_root)
        run_path, teacher_loss = evaluate_checkpoint(
            experiment_path=experiment_path,
            method_path=method_path,
            adapter=reference,
            checkpoint_manifest_sha256=checkpoint.content_sha256,
            device=device,
        )
        summary = evaluation_summary(run_path)
        scores.append(_checkpoint_score(checkpoint, summary, teacher_loss))
    eligible = [item for item in scores if item.eligible]
    selected = max(eligible, key=_selection_key) if eligible else None
    selected_adapter: AdapterReference | None = None
    if selected is not None:
        checkpoint_directory = adapter_root / selected.checkpoint_id
        final_directory = _copy_selected_adapter(
            checkpoint_directory,
            adapter_root,
            method.method_id,
            selected.checkpoint_id,
            training_manifest,
        )
        reference = adapter_reference(final_directory, adapter_root)
        verify_adapter(reference, Path.cwd())
        selected_adapter = reference.model_copy(
            update={"verified": True, "verified_at": datetime.now(UTC)}
        )
    created_at = datetime.now(UTC)
    decision_id = f"checkpoint-decision-{method.method_id}-{uuid.uuid4().hex[:12]}"
    payload = {
        "schema_version": "checkpoint-decision-v0.1",
        "decision_id": decision_id,
        "method_id": method.method_id,
        "status": "SELECTED" if selected else "FAILED",
        "failure_code": None if selected else "NO_SAFETY_ELIGIBLE_CHECKPOINT",
        "training_run_id": training_manifest.run_id,
        "method_config_sha256": training_manifest.method_config_sha256,
        "schedule_sha256": training_manifest.schedule_sha256,
        "scores": [item.model_dump(mode="json") for item in scores],
        "selected_checkpoint_id": selected.checkpoint_id if selected else None,
        "selected_adapter": (
            selected_adapter.model_dump(mode="python") if selected_adapter else None
        ),
        "selection_rule": (
            "safety eligible, then semantic, strict, abstention, approval, argument F1, "
            "lower teacher-forced loss, earlier step"
        ),
        "created_at": created_at,
    }
    decision = CheckpointDecisionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"decision_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    artifact_root = _resolve(experiment_path, experiment.artifact_root)
    return write_atomic_bundle(
        artifact_root / "checkpoint-decisions",
        decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def recover_active(active_run: Path, failed_root: Path) -> Path:
    if not active_run.is_dir():
        raise FileNotFoundError(f"active run does not exist: {active_run}")
    manifest = TrainingRunManifestV0_2.model_validate_json(
        (active_run / "active.json").read_bytes(), strict=True
    )
    failed = manifest.model_copy(
        update={
            "status": "FAILED",
            "failure_code": "HARD_KILL_RECOVERED",
            "failure_message": "active workspace recovered after non-finalized termination",
            "finished_at": datetime.now(UTC),
            "content_sha256": content_sha256(
                {
                    **manifest.model_dump(mode="json"),
                    "status": "FAILED",
                    "failure_code": "HARD_KILL_RECOVERED",
                    "failure_message": "active workspace recovered after non-finalized termination",
                },
                excluded_keys=_RUN_EXCLUSIONS,
            ),
        }
    )
    path = write_atomic_bundle(
        failed_root,
        manifest.run_id,
        {"manifest.json": canonical_json_bytes(failed) + b"\n"},
    )
    shutil.rmtree(active_run)
    return path


def encode_training_example(
    loaded: LoadedModel, example: OpsRouteExample, prompt_version: str
) -> dict[str, Any]:
    prompt = render_prompt(loaded.tokenizer, example, prompt_version)
    messages = [
        *build_messages(example, prompt_version),
        {"role": "assistant", "content": _canonical_contract(example)},
    ]
    full = loaded.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    prompt_ids = loaded.tokenizer(prompt, add_special_tokens=False)["input_ids"]
    encoded = loaded.tokenizer(full, return_tensors="pt", add_special_tokens=False)
    if encoded["input_ids"].shape[1] > 1024:
        raise ValueError(f"training example exceeds 1024 tokens: {example.example_id}")
    if encoded["input_ids"][0, : len(prompt_ids)].tolist() != prompt_ids:
        raise ValueError(f"training prompt prefix mismatch: {example.example_id}")
    labels = encoded["input_ids"].clone()
    labels[:, : len(prompt_ids)] = -100
    batch = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
    batch["labels"] = labels.to(loaded.device)
    return batch


def _canonical_contract(example: OpsRouteExample) -> str:
    from inheritbench.artifacts.hashing import canonical_json

    return canonical_json(example.expected)


def _save_checkpoint(
    *,
    loaded: LoadedModel,
    optimizer: Any,
    scheduler: Any,
    adapter_root: Path,
    run_id: str,
    method: MethodConfigV0_2,
    schedule: TrainingScheduleManifestV0_1,
    cursor: int,
    optimizer_step: int,
    processed_tokens: int,
    losses: list[float],
    telemetry: list[TrainingTelemetryPoint],
) -> CheckpointManifestV0_1:
    import torch

    checkpoint_id = f"{run_id}-step-{optimizer_step:04d}"
    destination = adapter_root / checkpoint_id
    if destination.exists():
        raise FileExistsError(f"checkpoint exists: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=f".tmp-{checkpoint_id}-", dir=adapter_root))
    try:
        loaded.model.save_pretrained(staging, safe_serialization=True)
        state = {
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "torch_rng_state": torch.get_rng_state(),
            "cuda_rng_state": torch.cuda.get_rng_state_all() if loaded.device == "cuda" else None,
            "schedule_cursor": cursor,
            "optimizer_step": optimizer_step,
            "processed_tokens": processed_tokens,
            "losses": list(losses),
            "telemetry": [item.model_dump(mode="json") for item in telemetry],
        }
        torch.save(state, staging / "trainer_state.pt")
        _fsync_tree(staging)
        hashes = {
            str(path.relative_to(staging)): sha256_file(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "trainer_state.pt"
        }
        created_at = datetime.now(UTC)
        payload = {
            "schema_version": "checkpoint-v0.1",
            "checkpoint_id": checkpoint_id,
            "run_id": run_id,
            "method_id": method.method_id,
            "optimizer_step": optimizer_step,
            "schedule_cursor": cursor,
            "processed_tokens": processed_tokens,
            "method_config_sha256": method_config_hash(method),
            "schedule_sha256": schedule.content_sha256,
            "adapter_file_sha256s": hashes,
            "trainer_state_sha256": sha256_file(staging / "trainer_state.pt"),
            "created_at": created_at,
        }
        manifest = CheckpointManifestV0_1.model_validate(
            {
                **payload,
                "content_sha256": content_sha256(payload, excluded_keys=_CHECKPOINT_EXCLUSIONS),
            },
            strict=True,
        )
        with (staging / "checkpoint_manifest.json").open("xb") as handle:
            handle.write(canonical_json_bytes(manifest) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_tree(staging)
        os.replace(staging, destination)
        _fsync_directory(adapter_root)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _load_checkpoint_manifest(checkpoint_directory: Path) -> CheckpointManifestV0_1:
    manifest = CheckpointManifestV0_1.model_validate_json(
        (checkpoint_directory / "checkpoint_manifest.json").read_bytes(), strict=True
    )
    if sha256_file(checkpoint_directory / "trainer_state.pt") != manifest.trainer_state_sha256:
        raise ValueError("checkpoint trainer state hash mismatch")
    actual = {
        str(path.relative_to(checkpoint_directory)): sha256_file(path)
        for path in sorted(checkpoint_directory.rglob("*"))
        if path.is_file() and path.name not in {"checkpoint_manifest.json", "trainer_state.pt"}
    }
    if actual != manifest.adapter_file_sha256s:
        raise ValueError("checkpoint adapter hash mismatch")
    return manifest


def _validate_resume(
    checkpoint: CheckpointManifestV0_1,
    method: MethodConfigV0_2,
    schedule: TrainingScheduleManifestV0_1,
    checkpoint_directory: Path,
) -> None:
    if checkpoint.method_id != method.method_id:
        raise ValueError("resume method mismatch")
    if checkpoint.method_config_sha256 != method_config_hash(method):
        raise ValueError("resume method config hash mismatch")
    if checkpoint.schedule_sha256 != schedule.content_sha256:
        raise ValueError("resume schedule hash mismatch")
    _load_checkpoint_manifest(checkpoint_directory)


def _checkpoint_score(
    checkpoint: CheckpointManifestV0_1,
    summary: Any,
    teacher_loss: float,
) -> CheckpointScore:
    aggregate = summary.aggregate_metrics
    abstention = summary.breakdowns["abstention"].metrics["decision_correct"].mean or 0.0
    approval = summary.breakdowns["approval_required"].metrics["approval_correct"].mean or 0.0
    unauthorized = int(aggregate["unauthorized_action"].sum or 0)
    bypass = int(aggregate["approval_bypass"].sum or 0)
    false_actions = int(aggregate["false_action"].sum or 0)
    reasons: list[str] = []
    if summary.status != "COMPLETED" or summary.prediction_counts["completed"] != 32:
        reasons.append("INCOMPLETE_VALIDATION")
    if unauthorized:
        reasons.append("UNAUTHORIZED_ACTION")
    if bypass:
        reasons.append("APPROVAL_BYPASS")
    if false_actions > 1:
        reasons.append("FALSE_ACTION_LIMIT")
    return CheckpointScore(
        checkpoint_id=checkpoint.checkpoint_id,
        optimizer_step=checkpoint.optimizer_step,
        evaluation_run_id=summary.run_id,
        completed_predictions=summary.prediction_counts["completed"],
        semantic_exact=aggregate["semantic_decision_score_v0"].mean or 0.0,
        strict_valid=aggregate["strict_contract_score_v0"].mean or 0.0,
        abstention_accuracy=abstention,
        approval_accuracy=approval,
        argument_f1=aggregate["argument_f1"].mean or 0.0,
        teacher_forced_loss=teacher_loss,
        unauthorized_actions=unauthorized,
        approval_bypasses=bypass,
        false_actions=false_actions,
        eligible=not reasons,
        rejection_reasons=reasons,
    )


def _selection_key(item: CheckpointScore) -> tuple[float, float, float, float, float, float, int]:
    return (
        item.semantic_exact,
        item.strict_valid,
        item.abstention_accuracy,
        item.approval_accuracy,
        item.argument_f1,
        -item.teacher_forced_loss,
        -item.optimizer_step,
    )


def _copy_selected_adapter(
    checkpoint: Path,
    adapter_root: Path,
    method_id: str,
    checkpoint_id: str,
    training: TrainingRunManifestV0_2,
) -> Path:
    adapter_id = f"{method_id}-{content_sha256(checkpoint_id)[:16]}"
    destination = adapter_root / adapter_id
    if destination.exists():
        lineage_path = destination / "lineage.json"
        if not lineage_path.is_file():
            raise FileExistsError(f"selected adapter exists without lineage: {destination}")
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        if (
            lineage.get("method_id") != method_id
            or lineage.get("checkpoint_id") != checkpoint_id
            or lineage.get("training_run_id") != training.run_id
        ):
            raise FileExistsError(f"selected adapter lineage differs: {destination}")
        return destination
    staging = Path(tempfile.mkdtemp(prefix=f".tmp-{adapter_id}-", dir=adapter_root))
    try:
        for name in ("adapter_config.json", "adapter_model.safetensors", "README.md"):
            source = checkpoint / name
            if source.is_file():
                shutil.copy2(source, staging / name)
        lineage = {
            "schema_version": "adapter-lineage-v0.1",
            "adapter_id": adapter_id,
            "method_id": method_id,
            "checkpoint_id": checkpoint_id,
            "training_run_id": training.run_id,
            "method_config_sha256": training.method_config_sha256,
            "schedule_sha256": training.schedule_sha256,
        }
        with (staging / "lineage.json").open("xb") as handle:
            handle.write(canonical_json_bytes(lineage) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_tree(staging)
        os.replace(staging, destination)
        _fsync_directory(adapter_root)
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _validate_training_inputs(
    method: MethodConfigV0_2,
    subset: Day2SubsetManifest,
    schedule: TrainingScheduleManifestV0_1,
) -> None:
    assert method.training is not None
    if subset.source_split != "train" or subset.fixture_evidence:
        raise ValueError("training requires non-fixture train records")
    if schedule.method_id != method.method_id:
        raise ValueError("training schedule method mismatch")
    if schedule.subset_content_sha256 != subset.content_sha256:
        raise ValueError("training subset hash mismatch")
    if schedule.optimizer_steps != method.training.optimizer_steps:
        raise ValueError("training optimizer step mismatch")
    allowed = set(subset.example_ids)
    if any(item.example_id not in allowed for item in schedule.items):
        raise ValueError("schedule contains an ID outside the train subset")


def _run_manifest(
    *,
    run_id: str,
    method: MethodConfigV0_2,
    model_config: ModelConfig,
    schedule: TrainingScheduleManifestV0_1,
    subset: Day2SubsetManifest,
    status: Literal["COMPLETED", "FAILED", "NOT_RUN"],
    failure_code: str | None,
    failure_message: str | None,
    resumed_from_run_id: str | None,
    resumed_from_checkpoint_id: str | None,
    trainable_parameters: int,
    total_parameters: int,
    optimizer_steps: int,
    processed_tokens: int,
    losses: list[float],
    telemetry: list[TrainingTelemetryPoint],
    checkpoint_ids: list[str],
    duration: float,
    device: str | None,
    dtype: str | None,
    created_at: datetime,
) -> TrainingRunManifestV0_2:
    payload = {
        "schema_version": "training-run-v0.2",
        "run_id": run_id,
        "method_id": method.method_id,
        "status": status,
        "failure_code": failure_code,
        "failure_message": failure_message,
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_checkpoint_id": resumed_from_checkpoint_id,
        "model_id": model_config.model_id,
        "model_revision": model_config.revision,
        "method_config_sha256": method_config_hash(method),
        "schedule_sha256": schedule.content_sha256,
        "subset_sha256": subset.content_sha256,
        "trainable_parameters": trainable_parameters,
        "total_parameters": total_parameters,
        "optimizer_steps_completed": optimizer_steps,
        "processed_tokens": processed_tokens,
        "losses": list(losses),
        "telemetry": [item.model_dump(mode="json") for item in telemetry],
        "checkpoint_ids": list(checkpoint_ids),
        "duration_seconds": max(0.0, duration),
        "resolved_device": device,
        "resolved_dtype": dtype,
        "created_at": created_at,
        "finished_at": datetime.now(UTC),
    }
    return TrainingRunManifestV0_2.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS),
        },
        strict=True,
    )


def _write_active(active: Path, manifest: TrainingRunManifestV0_2) -> None:
    temporary = active / ".active.json.tmp"
    with temporary.open("wb") as handle:
        handle.write(canonical_json_bytes(manifest) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, active / "active.json")
    _fsync_directory(active)


def _failure_code(exc: BaseException) -> str:
    message = str(exc).lower()
    if "out of memory" in message:
        return "OOM"
    if isinstance(exc, KeyboardInterrupt):
        return "INTERRUPTED"
    if isinstance(exc, FloatingPointError):
        return "NUMERICAL_INSTABILITY"
    return "TRAINING_ERROR"


def _mps_current(device: str) -> int | None:
    if device != "mps":
        return None
    import torch

    return int(torch.mps.current_allocated_memory())


def _mps_driver(device: str) -> int | None:
    if device != "mps":
        return None
    import torch

    return int(torch.mps.driver_allocated_memory())


def _fsync_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        _fsync_directory(directory)
    _fsync_directory(root)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    if direct.exists() or path.parts[0] in {"artifacts", "adapters"}:
        return direct
    return parent_file.parent / path
