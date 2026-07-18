"""Pinned Hugging Face causal-LM adapter with explicit LoRA mappings."""

from __future__ import annotations

import gc
import hashlib
import math
import os
import pickle
import random
import time
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json,
    input_ids_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    TrainingProfile,
)
from inheritbench.config import ModelConfig
from inheritbench.model_adapters.schemas import (
    CheckpointArtifact,
    GenerationOutput,
    ModelRuntimeIdentity,
    TrainingInitialization,
    TrainingResult,
    TrainingSchedule,
    TrainingTelemetry,
)
from inheritbench.models.loader import LoadedModel, load_model, unload_model


class HuggingFaceCausalLMAdapter:
    def __init__(
        self,
        registry_id: str,
        *,
        expected_model_id: str,
        expected_revision: str,
        architecture_class: str,
        lora_targets: tuple[str, ...],
    ) -> None:
        self.registry_id = registry_id
        self.expected_model_id = expected_model_id
        self.expected_revision = expected_revision
        self.architecture_class = architecture_class
        self.lora_targets = lora_targets

    def probe(
        self,
        config: ModelConfig,
        *,
        device: str,
        adapter_directory: Path | None = None,
    ) -> ModelRuntimeIdentity:
        loaded = self._load(config, device, "float16", adapter_directory)
        try:
            return self._identity(config, loaded, adapter_directory)
        finally:
            unload_model(loaded)

    def generate(
        self,
        config: ModelConfig,
        records: list[CapabilityInputRecord],
        *,
        device: str,
        maximum_new_tokens: int,
        seed: int,
        adapter_directory: Path | None = None,
    ) -> tuple[ModelRuntimeIdentity, list[GenerationOutput]]:
        import torch

        loaded = self._load(config, device, "float16", adapter_directory)
        identity = self._identity(config, loaded, adapter_directory)
        outputs: list[GenerationOutput] = []
        try:
            torch.manual_seed(seed)
            if device == "cuda":
                torch.cuda.manual_seed_all(seed)
            for record in records:
                started = time.perf_counter()
                try:
                    rendered = self._render(loaded, record)
                    encoded = loaded.tokenizer(
                        rendered,
                        return_tensors="pt",
                        add_special_tokens=False,
                    )
                    input_ids = encoded["input_ids"].to(loaded.device)
                    attention_mask = encoded["attention_mask"].to(loaded.device)
                    if int(input_ids.shape[-1]) > config.maximum_sequence_length:
                        raise ValueError("prompt exceeds model maximum sequence length")
                    with torch.inference_mode():
                        generated = loaded.model.generate(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                            do_sample=False,
                            num_beams=1,
                            max_new_tokens=maximum_new_tokens,
                            pad_token_id=loaded.tokenizer.pad_token_id,
                            eos_token_id=_eos_ids(loaded),
                            use_cache=True,
                        )
                    completion = generated[0, input_ids.shape[-1] :].tolist()
                    raw = loaded.tokenizer.decode(completion, skip_special_tokens=True)
                    outputs.append(
                        GenerationOutput(
                            record_id=record.record_id,
                            status="COMPLETED",
                            raw_output=raw,
                            prompt_sha256=sha256_text(rendered),
                            input_ids_sha256=input_ids_sha256(input_ids[0].tolist()),
                            prompt_tokens=int(input_ids.shape[-1]),
                            completion_tokens=len(completion),
                            error=None,
                            latency_ms=int((time.perf_counter() - started) * 1000),
                        )
                    )
                    del encoded, input_ids, attention_mask, generated
                except BaseException as exc:
                    outputs.append(
                        GenerationOutput(
                            record_id=record.record_id,
                            status="FAILED",
                            raw_output="",
                            prompt_sha256=sha256_text(canonical_json(record.messages)),
                            input_ids_sha256=input_ids_sha256([]),
                            prompt_tokens=0,
                            completion_tokens=0,
                            error=f"{type(exc).__name__}: {exc}",
                            latency_ms=int((time.perf_counter() - started) * 1000),
                        )
                    )
            return identity, outputs
        finally:
            unload_model(loaded)

    def sequence_lengths(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
    ) -> dict[str, int]:
        loaded = self._load_tokenizer(config)
        lengths: dict[str, int] = {}
        for record in records:
            prompt = loaded.apply_chat_template(
                [message.model_dump() for message in record.input_record.messages],
                tokenize=False,
                add_generation_prompt=True,
            )
            prompt_ids = loaded(prompt, add_special_tokens=False)["input_ids"]
            label_ids = loaded(record.assistant_label, add_special_tokens=False)["input_ids"]
            eos = [loaded.eos_token_id] if loaded.eos_token_id is not None else []
            length = len(prompt_ids) + len(label_ids) + len(eos)
            if length > config.maximum_sequence_length:
                raise ValueError(
                    f"training record {record.record_id} exceeds maximum sequence length"
                )
            lengths[record.record_id] = length
        return lengths

    def training_encoding_manifest(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
    ) -> list[dict[str, Any]]:
        tokenizer = self._load_tokenizer(config)
        manifest: list[dict[str, Any]] = []
        for record in sorted(records, key=lambda item: item.record_id):
            prompt = tokenizer.apply_chat_template(
                [message.model_dump() for message in record.input_record.messages],
                tokenize=False,
                add_generation_prompt=True,
            )
            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            label_ids = tokenizer(record.assistant_label, add_special_tokens=False)["input_ids"]
            eos = [tokenizer.eos_token_id] if tokenizer.eos_token_id is not None else []
            full_ids = [*prompt_ids, *label_ids, *eos]
            labels = [-100] * len(prompt_ids) + [*label_ids, *eos]
            attention_mask = [1] * len(full_ids)
            if len(full_ids) > config.maximum_sequence_length:
                raise ValueError(
                    f"training record {record.record_id} exceeds maximum sequence length"
                )
            manifest.append(
                {
                    "record_id": record.record_id,
                    "prompt_sha256": sha256_text(prompt),
                    "assistant_label_sha256": record.assistant_label_sha256,
                    "prompt_input_ids_sha256": input_ids_sha256(prompt_ids),
                    "assistant_input_ids_sha256": input_ids_sha256(label_ids),
                    "input_ids_sha256": input_ids_sha256(full_ids),
                    "labels_sha256": input_ids_sha256(labels),
                    "attention_mask_sha256": input_ids_sha256(attention_mask),
                    "prompt_tokens": len(prompt_ids),
                    "supervised_tokens": len(label_ids) + len(eos),
                    "sequence_tokens": len(full_ids),
                }
            )
        return manifest

    def training_initialization(
        self,
        config: ModelConfig,
        profile: TrainingProfile,
        *,
        device: str,
        seed: int,
    ) -> TrainingInitialization:
        from peft import LoraConfig, TaskType, get_peft_model

        seed_all(seed, device)
        rng_before_model_load = rng_state_sha256(device)
        loaded = self._load(config, device, "float32", None)
        try:
            rng_before_lora = rng_state_sha256(device)
            loaded.model = get_peft_model(
                loaded.model,
                LoraConfig(
                    r=profile.lora_rank,
                    lora_alpha=profile.lora_alpha,
                    lora_dropout=profile.lora_dropout,
                    bias="none",
                    task_type=TaskType.CAUSAL_LM,
                    target_modules=list(self.lora_targets),
                ),
            )
            names = [
                name
                for name, parameter in loaded.model.named_parameters()
                if parameter.requires_grad
            ]
            shapes = {
                name: list(parameter.shape)
                for name, parameter in loaded.model.named_parameters()
                if parameter.requires_grad
            }
            return TrainingInitialization(
                seed=seed,
                initial_adapter_sha256=_trainable_state_sha256(loaded.model),
                trainable_parameter_names=names,
                trainable_parameter_shapes=shapes,
                trainable_parameters=sum(
                    parameter.numel()
                    for parameter in loaded.model.parameters()
                    if parameter.requires_grad
                ),
                total_parameters=sum(parameter.numel() for parameter in loaded.model.parameters()),
                rng_before_model_load_sha256=rng_before_model_load,
                rng_before_lora_sha256=rng_before_lora,
                rng_after_lora_sha256=rng_state_sha256(device),
            )
        finally:
            unload_model(loaded)

    def train(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
        schedule: TrainingSchedule,
        profile: TrainingProfile,
        *,
        device: str,
        run_id: str,
        output_root: Path,
        seed: int,
        resume_checkpoint: Path | None = None,
    ) -> TrainingResult:
        import torch
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model
        from transformers import get_linear_schedule_with_warmup

        started = time.perf_counter()
        record_map = {record.record_id: record for record in records}
        seed_all(seed, device)
        rng_before_model_load = rng_state_sha256(device)
        loaded = self._load(config, device, "float32", None)
        optimizer: Any = None
        scheduler: Any = None
        telemetry: list[TrainingTelemetry] = []
        losses: list[float] = []
        checkpoints: list[CheckpointArtifact] = []
        cursor = 0
        optimizer_step = 0
        processed_tokens = 0
        optimizer_step_one_sha256: str | None = None
        try:
            rng_before_lora = rng_state_sha256(device)
            if resume_checkpoint is None:
                peft_config = LoraConfig(
                    r=profile.lora_rank,
                    lora_alpha=profile.lora_alpha,
                    lora_dropout=profile.lora_dropout,
                    bias="none",
                    task_type=TaskType.CAUSAL_LM,
                    target_modules=list(self.lora_targets),
                )
                loaded.model = get_peft_model(loaded.model, peft_config)
            else:
                loaded.model = PeftModel.from_pretrained(
                    loaded.model, resume_checkpoint, is_trainable=True
                )
            loaded.model.config.use_cache = False
            loaded.model.train()
            trainable = [
                parameter for parameter in loaded.model.parameters() if parameter.requires_grad
            ]
            trainable_names = [
                name
                for name, parameter in loaded.model.named_parameters()
                if parameter.requires_grad
            ]
            trainable_shapes = {
                name: list(parameter.shape)
                for name, parameter in loaded.model.named_parameters()
                if parameter.requires_grad
            }
            initial_adapter_sha256 = _trainable_state_sha256(loaded.model)
            rng_after_lora = rng_state_sha256(device)
            trainable_parameters = sum(parameter.numel() for parameter in trainable)
            total_parameters = sum(parameter.numel() for parameter in loaded.model.parameters())
            optimizer = torch.optim.AdamW(
                trainable,
                lr=profile.learning_rate,
                betas=(profile.betas[0], profile.betas[1]),
                eps=profile.epsilon,
                weight_decay=profile.weight_decay,
            )
            scheduler_factory: Any = get_linear_schedule_with_warmup
            scheduler = scheduler_factory(
                optimizer,
                num_warmup_steps=schedule.warmup_steps,
                num_training_steps=schedule.optimizer_steps,
            )
            if resume_checkpoint is None:
                seed_training_rng(seed, device)
            rng_training_start = rng_state_sha256(device)
            if resume_checkpoint is not None:
                state = torch.load(
                    resume_checkpoint / "trainer_state.pt",
                    map_location="cpu",
                    weights_only=False,
                )
                if state["schedule_id"] != schedule.schedule_id:
                    raise ValueError("resume checkpoint schedule mismatch")
                optimizer.load_state_dict(state["optimizer"])
                scheduler.load_state_dict(state["scheduler"])
                restore_rng_state(state, device)
                cursor = int(state["schedule_cursor"])
                optimizer_step = int(state["optimizer_step"])
                processed_tokens = int(state["processed_tokens"])
                losses = [float(item) for item in state["losses"]]
                telemetry = [
                    TrainingTelemetry.model_validate(item, strict=True)
                    for item in state["telemetry"]
                ]
                checkpoints = _existing_checkpoints(output_root, optimizer_step)
                optimizer_step_one_sha256 = state.get("optimizer_step_one_sha256")
            while cursor < len(schedule.items):
                group = schedule.items[cursor : cursor + profile.gradient_accumulation_steps]
                optimizer.zero_grad(set_to_none=True)
                group_losses: list[float] = []
                for item in group:
                    batch = self._training_batch(loaded, record_map[item.record_id])
                    output = loaded.model(**batch)
                    loss = output.loss
                    value = float(loss.detach().cpu())
                    if not math.isfinite(value):
                        raise FloatingPointError(f"non-finite loss at cursor {item.cursor}")
                    (loss / len(group)).backward()
                    group_losses.append(value)
                    processed_tokens += item.sequence_tokens
                    cursor += 1
                    del batch, output, loss
                pre_clip_gradient_norm, post_clip_gradient_norm = _clip_and_validate_gradients(
                    trainable,
                    profile.gradient_clip_norm,
                )
                _require_finite_parameters(trainable, "before optimizer step")
                _require_finite_optimizer_state(optimizer, "before optimizer step")
                optimizer.step()
                _require_finite_parameters(trainable, "after optimizer step")
                _require_finite_optimizer_state(optimizer, "after optimizer step")
                scheduler.step()
                optimizer_step += 1
                if optimizer_step == 1:
                    optimizer_step_one_sha256 = optimizer_state_sha256(optimizer)
                loss_value = sum(group_losses) / len(group_losses)
                losses.append(loss_value)
                telemetry.append(
                    TrainingTelemetry(
                        optimizer_step=optimizer_step,
                        schedule_cursor=cursor,
                        processed_tokens=processed_tokens,
                        loss=loss_value,
                        learning_rate=float(scheduler.get_last_lr()[0]),
                        gradient_norm=pre_clip_gradient_norm,
                        pre_clip_gradient_norm=pre_clip_gradient_norm,
                        post_clip_gradient_norm=post_clip_gradient_norm,
                        mps_current_allocated_bytes=_mps_current(device),
                        mps_driver_allocated_bytes=_mps_driver(device),
                    )
                )
                if optimizer_step in schedule.checkpoint_steps:
                    checkpoints.append(
                        self._save_checkpoint(
                            loaded=loaded,
                            optimizer=optimizer,
                            scheduler=scheduler,
                            output_root=output_root,
                            run_id=run_id,
                            schedule=schedule,
                            cursor=cursor,
                            optimizer_step=optimizer_step,
                            processed_tokens=processed_tokens,
                            losses=losses,
                            telemetry=telemetry,
                            optimizer_step_one_sha256=optimizer_step_one_sha256,
                        )
                    )
            if optimizer_step != schedule.optimizer_steps:
                raise RuntimeError("training optimizer-step count does not match schedule")
            if processed_tokens != schedule.processed_tokens:
                raise RuntimeError("training token count does not match schedule")
            return TrainingResult(
                status="COMPLETED",
                run_id=run_id,
                model=self._identity(config, loaded, None),
                trainable_parameters=trainable_parameters,
                total_parameters=total_parameters,
                seed=seed,
                initial_adapter_sha256=initial_adapter_sha256,
                trainable_parameter_names=trainable_names,
                trainable_parameter_shapes=trainable_shapes,
                rng_before_model_load_sha256=rng_before_model_load,
                rng_before_lora_sha256=rng_before_lora,
                rng_after_lora_sha256=rng_after_lora,
                rng_training_start_sha256=rng_training_start,
                optimizer_step_one_sha256=optimizer_step_one_sha256,
                processed_tokens=processed_tokens,
                optimizer_steps_completed=optimizer_step,
                duration_seconds=time.perf_counter() - started,
                losses=losses,
                telemetry=telemetry,
                checkpoints=checkpoints,
                error=None,
            )
        finally:
            unload_model(loaded)
            del optimizer, scheduler
            gc.collect()

    def validation_loss(
        self,
        config: ModelConfig,
        records: list[CapabilityLabeledRecord],
        *,
        device: str,
        adapter_directory: Path,
    ) -> float:
        import torch

        loaded = self._load(config, device, "float16", adapter_directory)
        losses: list[float] = []
        try:
            loaded.model.eval()
            with torch.inference_mode():
                for record in records:
                    output = loaded.model(**self._training_batch(loaded, record))
                    losses.append(float(output.loss.detach().cpu()))
            return sum(losses) / len(losses)
        finally:
            unload_model(loaded)

    def verify_adapter(
        self,
        config: ModelConfig,
        adapter_directory: Path,
        *,
        device: str,
    ) -> ModelRuntimeIdentity:
        loaded = self._load(config, device, "float16", adapter_directory)
        try:
            return self._identity(config, loaded, adapter_directory)
        finally:
            unload_model(loaded)

    def _load(
        self,
        config: ModelConfig,
        device: str,
        dtype: str,
        adapter_directory: Path | None,
    ) -> LoadedModel:
        self._validate_config(config)
        loaded = load_model(
            config.model_copy(update={"requested_dtype": dtype}),
            device_override=device,
        )
        if loaded.model.__class__.__name__ != self.architecture_class:
            unload_model(loaded)
            raise RuntimeError("UNSUPPORTED_MODEL_ARCHITECTURE")
        if adapter_directory is not None:
            from peft import PeftModel

            loaded.model = PeftModel.from_pretrained(loaded.model, adapter_directory)
            loaded.model.to(device)
            loaded.model.eval()
        return loaded

    def _load_tokenizer(self, config: ModelConfig) -> Any:
        from transformers import AutoTokenizer

        self._validate_config(config)
        auto_tokenizer: Any = AutoTokenizer
        tokenizer = auto_tokenizer.from_pretrained(
            config.tokenizer_id,
            revision=config.tokenizer_revision,
            trust_remote_code=False,
        )
        if not tokenizer.chat_template:
            raise RuntimeError("tokenizer has no native chat template")
        if (
            tokenizer.pad_token_id is None
            and config.special_tokens.pad_strategy == "eos_if_missing"
        ):
            tokenizer.pad_token = tokenizer.eos_token
        return tokenizer

    def _validate_config(self, config: ModelConfig) -> None:
        if config.model_id != self.expected_model_id or config.revision != self.expected_revision:
            raise ValueError("model identity or revision is not registered")
        if config.trust_remote_code:
            raise ValueError("trust_remote_code must remain false")
        if tuple(config.intended_lora_target_modules) != self.lora_targets:
            raise ValueError("configured LoRA targets do not match explicit registry mapping")

    def _render(self, loaded: LoadedModel, record: CapabilityInputRecord) -> str:
        rendered = loaded.tokenizer.apply_chat_template(
            [message.model_dump() for message in record.messages],
            tokenize=False,
            add_generation_prompt=True,
        )
        if not isinstance(rendered, str) or not rendered:
            raise RuntimeError("native chat template returned an empty prompt")
        return rendered

    def _training_batch(
        self,
        loaded: LoadedModel,
        record: CapabilityLabeledRecord,
    ) -> dict[str, Any]:
        import torch

        prompt = self._render(loaded, record.input_record)
        prompt_ids = loaded.tokenizer(prompt, add_special_tokens=False)["input_ids"]
        label_ids = loaded.tokenizer(record.assistant_label, add_special_tokens=False)["input_ids"]
        eos = [loaded.tokenizer.eos_token_id] if loaded.tokenizer.eos_token_id is not None else []
        input_ids = prompt_ids + label_ids + eos
        labels = [-100] * len(prompt_ids) + label_ids + eos
        return {
            "input_ids": torch.tensor([input_ids], dtype=torch.long, device=loaded.device),
            "attention_mask": torch.ones(
                (1, len(input_ids)), dtype=torch.long, device=loaded.device
            ),
            "labels": torch.tensor([labels], dtype=torch.long, device=loaded.device),
        }

    def _save_checkpoint(
        self,
        *,
        loaded: LoadedModel,
        optimizer: Any,
        scheduler: Any,
        output_root: Path,
        run_id: str,
        schedule: TrainingSchedule,
        cursor: int,
        optimizer_step: int,
        processed_tokens: int,
        losses: list[float],
        telemetry: list[TrainingTelemetry],
        optimizer_step_one_sha256: str | None,
    ) -> CheckpointArtifact:
        import torch

        checkpoint_id = f"{run_id}-step-{optimizer_step:04d}"
        destination = output_root / checkpoint_id
        if destination.exists():
            raise FileExistsError(destination)
        staging = output_root / f".tmp-{checkpoint_id}"
        staging.mkdir(parents=True, exist_ok=False)
        try:
            loaded.model.save_pretrained(staging, safe_serialization=True)
            state = {
                "schedule_id": schedule.schedule_id,
                "schedule_cursor": cursor,
                "optimizer_step": optimizer_step,
                "processed_tokens": processed_tokens,
                "losses": losses,
                "telemetry": [item.model_dump(mode="json") for item in telemetry],
                "optimizer_step_one_sha256": optimizer_step_one_sha256,
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
            }
            state.update(capture_rng_state(loaded.device))
            torch.save(state, staging / "trainer_state.pt")
            _fsync_tree(staging)
            os.replace(staging, destination)
        except BaseException:
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
            raise
        adapter_path = destination / "adapter_model.safetensors"
        trainer_path = destination / "trainer_state.pt"
        return CheckpointArtifact(
            checkpoint_id=checkpoint_id,
            optimizer_step=optimizer_step,
            adapter_directory=str(destination),
            adapter_sha256=sha256_file(adapter_path),
            trainer_state_sha256=sha256_file(trainer_path),
            validation_loss=None,
        )

    def _identity(
        self,
        config: ModelConfig,
        loaded: LoadedModel,
        adapter_directory: Path | None,
    ) -> ModelRuntimeIdentity:
        adapter_hash = None
        if adapter_directory is not None:
            candidate = adapter_directory / "adapter_model.safetensors"
            if candidate.is_file():
                adapter_hash = sha256_file(candidate)
        return ModelRuntimeIdentity(
            registry_id=self.registry_id,
            model_id=config.model_id,
            revision=config.revision,
            architecture_class=self.architecture_class,
            tokenizer_id=config.tokenizer_id,
            tokenizer_revision=config.tokenizer_revision,
            device=loaded.device,
            dtype=loaded.dtype,
            adapter_sha256=adapter_hash,
        )


def _existing_checkpoints(output_root: Path, through_step: int) -> list[CheckpointArtifact]:
    checkpoints: list[CheckpointArtifact] = []
    for directory in sorted(path for path in output_root.glob("*-step-*") if path.is_dir()):
        try:
            step = int(directory.name.rsplit("-step-", 1)[1])
        except (IndexError, ValueError):
            continue
        if step > through_step:
            continue
        adapter_path = directory / "adapter_model.safetensors"
        trainer_path = directory / "trainer_state.pt"
        if not adapter_path.is_file() or not trainer_path.is_file():
            raise ValueError(f"incomplete resume checkpoint {directory}")
        checkpoints.append(
            CheckpointArtifact(
                checkpoint_id=directory.name,
                optimizer_step=step,
                adapter_directory=str(directory),
                adapter_sha256=sha256_file(adapter_path),
                trainer_state_sha256=sha256_file(trainer_path),
                validation_loss=None,
            )
        )
    return checkpoints


def _eos_ids(loaded: LoadedModel) -> int | list[int] | None:
    value = loaded.tokenizer.eos_token_id
    if value is None:
        return None
    return int(value)


def _clip_and_validate_gradients(
    parameters: list[Any],
    maximum_norm: float,
) -> tuple[float, float]:
    """Clip finite gradients and retain distinct pre/post clipping telemetry.

    ``clip_grad_norm_`` returns the norm measured before it mutates gradients.  A
    large finite return value is therefore expected to be recoverable when the
    declared clip policy is active; only non-finite values are numerical failures.
    """

    import torch

    pre_clip = float(torch.nn.utils.clip_grad_norm_(parameters, maximum_norm))
    if not math.isfinite(pre_clip):
        raise FloatingPointError(f"non-finite pre-clip gradient norm {pre_clip}")
    post_clip = _global_gradient_norm(parameters)
    if not math.isfinite(post_clip):
        raise FloatingPointError(f"non-finite post-clip gradient norm {post_clip}")
    return pre_clip, post_clip


def _global_gradient_norm(parameters: list[Any]) -> float:
    import torch

    norms = [
        torch.linalg.vector_norm(parameter.grad.detach(), ord=2)
        for parameter in parameters
        if parameter.grad is not None
    ]
    if not norms:
        return 0.0
    return float(torch.linalg.vector_norm(torch.stack(norms), ord=2))


def _require_finite_parameters(parameters: list[Any], location: str) -> None:
    import torch

    if any(not bool(torch.isfinite(parameter.detach()).all()) for parameter in parameters):
        raise FloatingPointError(f"non-finite trainable parameter {location}")


def _require_finite_optimizer_state(optimizer: Any, location: str) -> None:
    import torch

    def finite(value: Any) -> bool:
        if isinstance(value, torch.Tensor):
            return bool(torch.isfinite(value.detach()).all())
        if isinstance(value, dict):
            return all(finite(item) for item in value.values())
        if isinstance(value, list | tuple):
            return all(finite(item) for item in value)
        if isinstance(value, float):
            return math.isfinite(value)
        return True

    if not finite(optimizer.state_dict()):
        raise FloatingPointError(f"non-finite optimizer state {location}")


def seed_all(seed: int, device: str) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if device == "mps" and hasattr(torch.mps, "manual_seed"):
        torch.mps.manual_seed(seed)


def seed_training_rng(seed: int, device: str) -> None:
    import torch

    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)


def capture_rng_state(device: str) -> dict[str, Any]:
    import numpy as np
    import torch

    return {
        "python_rng_state": random.getstate(),
        "numpy_rng_state": np.random.get_state(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_state_all": (
            torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
        ),
        "mps_rng_state": (
            torch.mps.get_rng_state()
            if device == "mps"
            and hasattr(torch.mps, "get_rng_state")
            and torch.backends.mps.is_available()
            else None
        ),
    }


def rng_state_sha256(device: str) -> str:
    return hashlib.sha256(pickle.dumps(capture_rng_state(device), protocol=5)).hexdigest()


def optimizer_state_sha256(optimizer: Any) -> str:
    digest = hashlib.sha256()
    _update_state_digest(digest, optimizer.state_dict())
    return digest.hexdigest()


def _update_state_digest(digest: Any, value: Any) -> None:
    import torch

    if isinstance(value, torch.Tensor):
        tensor = value.detach().cpu().contiguous()
        digest.update(b"tensor")
        digest.update(str(tensor.dtype).encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(tensor.numpy().tobytes())
        return
    if isinstance(value, dict):
        digest.update(b"dict")
        for key in sorted(value, key=lambda item: str(item)):
            digest.update(str(key).encode())
            _update_state_digest(digest, value[key])
        return
    if isinstance(value, list | tuple):
        digest.update(type(value).__name__.encode())
        for item in value:
            _update_state_digest(digest, item)
        return
    digest.update(repr(value).encode())


def restore_rng_state(state: dict[str, Any], device: str) -> None:
    import numpy as np
    import torch

    random.setstate(state["python_rng_state"])
    np.random.set_state(state["numpy_rng_state"])
    torch.set_rng_state(state["torch_rng_state"])
    if device == "cuda" and state.get("cuda_rng_state_all") is not None:
        torch.cuda.set_rng_state_all(state["cuda_rng_state_all"])
    if (
        device == "mps"
        and state.get("mps_rng_state") is not None
        and hasattr(torch.mps, "set_rng_state")
    ):
        torch.mps.set_rng_state(state["mps_rng_state"])


def _trainable_state_sha256(model: Any) -> str:
    digest = hashlib.sha256()
    for name, parameter in sorted(model.named_parameters()):
        if not parameter.requires_grad:
            continue
        value = parameter.detach().cpu().contiguous()
        digest.update(name.encode())
        digest.update(str(value.dtype).encode())
        digest.update(str(tuple(value.shape)).encode())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


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
    for path in sorted(root.rglob("*")):
        if path.is_file():
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
