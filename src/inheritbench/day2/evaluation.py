"""Generic Day 2 model evaluation, breakdowns, and exact replay."""

from __future__ import annotations

import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json,
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    input_ids_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.schemas import GenerationConfig
from inheritbench.artifacts.store import artifact_reference, verify_reference, write_atomic_bundle
from inheritbench.config import ModelConfig
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2.config import (
    load_experiment_config,
    load_method_config,
    method_config_hash,
    resolved_model_config,
)
from inheritbench.day2.data import find_data_bundle, load_subset
from inheritbench.day2.schemas import (
    AdapterReference,
    CheckpointDecisionV0_1,
    Day2ExperimentConfig,
    Day2SubsetManifest,
    EvaluationBreakdown,
    EvaluationRunManifestV0_2,
    EvaluationSummaryV0_2,
    MethodConfigV0_2,
    MetricValue,
    PredictionRecordV0_2,
    ReplayVerificationV0_2,
    SourceCapabilityDecisionV0_1,
)
from inheritbench.evaluation.metrics import aggregate_metrics, score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import build_messages, render_prompt

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


def evaluate_method(
    *,
    experiment_path: Path,
    method_path: Path,
    split: Literal["validation", "test"],
    device: Literal["auto", "mps", "cpu", "cuda"] = "mps",
    command: list[str] | None = None,
) -> Path:
    experiment = load_experiment_config(experiment_path)
    method = load_method_config(method_path)
    bundle = find_data_bundle(experiment_path, experiment)
    subset = load_subset(bundle, "full_validation" if split == "validation" else "final_test")
    if split == "test":
        _require_final_test_freeze(experiment_path, experiment)
    adapter, decision_hash = _adapter_for_method(experiment_path, experiment, method)
    return _evaluate(
        experiment_path=experiment_path,
        experiment=experiment,
        method_path=method_path,
        method=method,
        subset=subset,
        split=split,
        adapter=adapter,
        checkpoint_decision_sha256=decision_hash,
        device=device,
        command=command or sys.argv,
        output_root=_artifact_root(experiment_path, experiment) / split,
    )[0]


def evaluate_checkpoint(
    *,
    experiment_path: Path,
    method_path: Path,
    adapter: AdapterReference,
    checkpoint_manifest_sha256: str,
    device: Literal["mps", "cpu", "cuda"] = "mps",
) -> tuple[Path, float]:
    experiment = load_experiment_config(experiment_path)
    method = load_method_config(method_path)
    bundle = find_data_bundle(experiment_path, experiment)
    subset = load_subset(bundle, "full_validation")
    return _evaluate(
        experiment_path=experiment_path,
        experiment=experiment,
        method_path=method_path,
        method=method,
        subset=subset,
        split="validation",
        adapter=adapter,
        checkpoint_decision_sha256=checkpoint_manifest_sha256,
        device=device,
        command=["inheritbench", "day2", "train", "checkpoint-validation"],
        output_root=_artifact_root(experiment_path, experiment) / "validation",
        compute_teacher_forced_loss=True,
    )


def replay_evaluation(run_directory: Path, output_root: Path) -> Path:
    manifest = EvaluationRunManifestV0_2.model_validate_json(
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
            raise ValueError(f"Day 2 replay mismatch: {prediction.prediction_id}")
    stored_summary = EvaluationSummaryV0_2.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )
    rebuilt = build_summary(
        predictions,
        run_id=stored_summary.run_id,
        method_id=stored_summary.method_id,
        split=stored_summary.split,
        created_at=stored_summary.created_at,
        finished_at=stored_summary.finished_at,
    )
    if rebuilt != stored_summary:
        raise ValueError("Day 2 summary replay mismatch")
    created_at = datetime.now(UTC)
    replay_id = f"day2-replay-{manifest.run_id}-{uuid.uuid4().hex[:8]}"
    payload = {
        "schema_version": "replay-verification-v0.2",
        "replay_id": replay_id,
        "original_run_id": manifest.run_id,
        "status": "PASSED",
        "original_prediction_byte_sha256": manifest.prediction_artifact.byte_sha256,
        "original_summary_byte_sha256": manifest.summary_artifact.byte_sha256,
        "prediction_records_verified": len(predictions),
        "parser_results_match": True,
        "metrics_match": True,
        "summary_matches": True,
        "created_at": created_at,
    }
    verification = ReplayVerificationV0_2.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys={"created_at", "replay_id"}),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        replay_id,
        {
            "predictions.jsonl": canonical_jsonl_bytes(predictions),
            "summary.json": canonical_json_bytes(stored_summary) + b"\n",
            "verification.json": canonical_json_bytes(verification) + b"\n",
        },
    )


def build_summary(
    predictions: list[PredictionRecordV0_2],
    *,
    run_id: str,
    method_id: str,
    split: Literal["validation", "test"],
    created_at: datetime,
    finished_at: datetime,
) -> EvaluationSummaryV0_2:
    completed = [item for item in predictions if item.status == "COMPLETED"]
    metrics = [item.metrics for item in completed if item.metrics is not None]
    aggregate = {
        name: MetricValue.model_validate(value, strict=True)
        for name, value in aggregate_metrics(metrics).items()
    }
    groups: dict[str, list[PredictionRecordV0_2]] = {"all": predictions}
    for prediction in predictions:
        groups.setdefault(f"family:{prediction.scenario_family}", []).append(prediction)
        groups.setdefault(f"expected_decision:{prediction.expected_contract.decision}", []).append(
            prediction
        )
        if prediction.expected_contract.approval_required:
            groups.setdefault("approval_required", []).append(prediction)
        if prediction.expected_contract.decision in {
            "ask_clarification",
            "refuse",
            "no_action",
        }:
            groups.setdefault("abstention", []).append(prediction)
    breakdowns = {name: _breakdown(name, values) for name, values in sorted(groups.items())}
    status: Literal["COMPLETED", "FAILED"] = (
        "FAILED" if any(item.status == "FAILED" for item in predictions) else "COMPLETED"
    )
    errors = [error for prediction in predictions for error in prediction.errors]
    payload = {
        "schema_version": "evaluation-summary-v0.2",
        "run_id": run_id,
        "method_id": method_id,
        "status": status,
        "split": split,
        "prediction_counts": {
            "total": len(predictions),
            "completed": len(completed),
            "failed": len(predictions) - len(completed),
        },
        "aggregate_metrics": {
            name: value.model_dump(mode="json") for name, value in aggregate.items()
        },
        "parser_classifications": _parser_counts(predictions),
        "breakdowns": {name: value.model_dump(mode="json") for name, value in breakdowns.items()},
        "run_errors": errors,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    return EvaluationSummaryV0_2.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS),
        },
        strict=True,
    )


def adapter_reference(adapter_directory: Path, adapter_root: Path) -> AdapterReference:
    if not adapter_directory.is_dir():
        raise FileNotFoundError(f"adapter directory is missing: {adapter_directory}")
    hashes = {
        str(path.relative_to(adapter_directory)): sha256_file(path)
        for path in sorted(adapter_directory.rglob("*"))
        if path.is_file() and path.name != "checkpoint_manifest.json"
    }
    total = sum(
        path.stat().st_size
        for path in adapter_directory.rglob("*")
        if path.is_file() and path.name != "checkpoint_manifest.json"
    )
    return AdapterReference(
        adapter_id=adapter_directory.name,
        relative_path=str(adapter_directory.relative_to(adapter_root.parent.parent)),
        file_sha256s=hashes,
        total_bytes=total,
        verified=False,
        verified_at=None,
    )


def verify_adapter(adapter: AdapterReference, repository_root: Path) -> Path:
    path = repository_root / adapter.relative_path
    actual = {
        str(item.relative_to(path)): sha256_file(item)
        for item in sorted(path.rglob("*"))
        if item.is_file() and item.name != "checkpoint_manifest.json"
    }
    if actual != adapter.file_sha256s:
        raise ValueError(f"adapter hash mismatch: {adapter.adapter_id}")
    return path


def evaluation_summary(run_directory: Path) -> EvaluationSummaryV0_2:
    return EvaluationSummaryV0_2.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )


def _evaluate(
    *,
    experiment_path: Path,
    experiment: Day2ExperimentConfig,
    method_path: Path,
    method: MethodConfigV0_2,
    subset: Day2SubsetManifest,
    split: Literal["validation", "test"],
    adapter: AdapterReference | None,
    checkpoint_decision_sha256: str | None,
    device: Literal["auto", "mps", "cpu", "cuda"],
    command: list[str],
    output_root: Path,
    compute_teacher_forced_loss: bool = False,
) -> tuple[Path, float]:
    if subset.source_split != split or len(subset.entries) != 32 or subset.fixture_evidence:
        raise ValueError(f"Day 2 {split} evaluation requires all 32 frozen records")
    dataset_directory = _resolve(experiment_path, experiment.dataset_directory)
    examples = load_examples(dataset_directory, subset.example_ids)
    if any(example.split != split for example in examples):
        raise ValueError(f"{split} evaluation includes a different split")
    model_config = resolved_model_config(method_path, method)
    inference_config = model_config.model_copy(update={"requested_dtype": "float16"})
    run_id = (
        f"day2-{method.method_id}-{split}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    )
    created_at = datetime.now(UTC)
    generation = GenerationConfig(do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714)
    repository_root = Path.cwd()
    loaded = _load_with_adapter(inference_config, adapter, repository_root, device)
    try:
        predictions = [
            _infer_one(
                loaded=loaded,
                model_config=model_config,
                method=method,
                adapter=adapter,
                checkpoint_decision_sha256=checkpoint_decision_sha256,
                example=example,
                generation=generation,
                run_id=run_id,
            )
            for example in examples
        ]
        teacher_loss = (
            _teacher_forced_loss(loaded, examples, method.prompt_template_version)
            if compute_teacher_forced_loss
            else 0.0
        )
    finally:
        unload_model(loaded)
    predictions.sort(key=lambda item: item.example_id)
    finished_at = datetime.now(UTC)
    summary = build_summary(
        predictions,
        run_id=run_id,
        method_id=method.method_id,
        split=split,
        created_at=created_at,
        finished_at=finished_at,
    )
    prediction_bytes = canonical_jsonl_bytes(predictions)
    summary_bytes = canonical_json_bytes(summary) + b"\n"
    prediction_reference = artifact_reference(
        "predictions.jsonl",
        prediction_bytes,
        content_sha256=content_sha256([item.content_sha256 for item in predictions]),
    )
    summary_reference = artifact_reference(
        "summary.json", summary_bytes, content_sha256=summary.content_sha256
    )
    payload = {
        "schema_version": "evaluation-run-v0.2",
        "run_id": run_id,
        "method_id": method.method_id,
        "status": summary.status,
        "split": split,
        "method_config_sha256": method_config_hash(method),
        "subset_sha256": subset.content_sha256,
        "dataset_sha256": subset.dataset_sha256,
        "adapter": adapter.model_dump(mode="python") if adapter else None,
        "checkpoint_decision_sha256": checkpoint_decision_sha256,
        "generation": generation.model_dump(mode="json"),
        "command": command,
        "prediction_artifact": prediction_reference.model_dump(mode="json"),
        "summary_artifact": summary_reference.model_dump(mode="json"),
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = EvaluationRunManifestV0_2.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS),
        },
        strict=True,
    )
    path = write_atomic_bundle(
        output_root,
        run_id,
        {
            "predictions.jsonl": prediction_bytes,
            "summary.json": summary_bytes,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )
    return path, teacher_loss


def _load_with_adapter(
    config: ModelConfig,
    adapter: AdapterReference | None,
    repository_root: Path,
    device: str,
) -> LoadedModel:
    loaded = load_model(config, device_override=device)
    if adapter is None:
        return loaded
    from peft import PeftModel

    path = verify_adapter(adapter, repository_root)
    loaded.model = PeftModel.from_pretrained(loaded.model, path, is_trainable=False)
    loaded.model.eval()
    return loaded


def _infer_one(
    *,
    loaded: LoadedModel,
    model_config: ModelConfig,
    method: MethodConfigV0_2,
    adapter: AdapterReference | None,
    checkpoint_decision_sha256: str | None,
    example: OpsRouteExample,
    generation: GenerationConfig,
    run_id: str,
) -> PredictionRecordV0_2:
    import torch

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    prompt_hash: str | None = None
    ids_hash: str | None = None
    prompt_tokens: int | None = None
    try:
        prompt = render_prompt(loaded.tokenizer, example, method.prompt_template_version)
        prompt_hash = sha256_text(prompt)
        encoded = loaded.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        token_ids = encoded["input_ids"][0].tolist()
        prompt_tokens = len(token_ids)
        ids_hash = input_ids_sha256(token_ids)
        if prompt_tokens > 1024:
            raise ValueError(f"prompt exceeds 1024 tokens: {example.example_id}")
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
        raw_output = loaded.tokenizer.decode(completion, skip_special_tokens=True)
        eos_ids = _eos_ids(loaded)
        generated_count = int(completion.shape[0])
        finish: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"]
        if generated_count and int(completion[-1]) in eos_ids:
            finish = "EOS"
        elif generated_count >= generation.max_new_tokens:
            finish = "MAX_NEW_TOKENS"
        else:
            finish = "OTHER"
        parser = parse_action_contract(raw_output)
        metrics = score_prediction(parser, example.expected, example.evaluation)
        return _prediction(
            run_id=run_id,
            method=method,
            adapter=adapter,
            checkpoint_decision_sha256=checkpoint_decision_sha256,
            example=example,
            model_config=model_config,
            loaded=loaded,
            generation=generation,
            started_at=started_at,
            latency_ms=round((time.perf_counter() - started) * 1000),
            prompt_hash=prompt_hash,
            ids_hash=ids_hash,
            prompt_tokens=prompt_tokens,
            generated_tokens=generated_count,
            finish=finish,
            raw_output=raw_output,
            parser=parser,
            metrics=metrics,
            error=None,
        )
    except Exception as exc:
        return _prediction(
            run_id=run_id,
            method=method,
            adapter=adapter,
            checkpoint_decision_sha256=checkpoint_decision_sha256,
            example=example,
            model_config=model_config,
            loaded=loaded,
            generation=generation,
            started_at=started_at,
            latency_ms=round((time.perf_counter() - started) * 1000),
            prompt_hash=prompt_hash,
            ids_hash=ids_hash,
            prompt_tokens=prompt_tokens,
            generated_tokens=None,
            finish=None,
            raw_output="",
            parser=None,
            metrics=None,
            error=exc,
        )


def _prediction(
    *,
    run_id: str,
    method: MethodConfigV0_2,
    adapter: AdapterReference | None,
    checkpoint_decision_sha256: str | None,
    example: OpsRouteExample,
    model_config: ModelConfig,
    loaded: LoadedModel,
    generation: GenerationConfig,
    started_at: datetime,
    latency_ms: int,
    prompt_hash: str | None,
    ids_hash: str | None,
    prompt_tokens: int | None,
    generated_tokens: int | None,
    finish: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"] | None,
    raw_output: str,
    parser: Any,
    metrics: Any,
    error: Exception | None,
) -> PredictionRecordV0_2:
    message = f"{type(error).__name__}: {error}" if error else None
    lower = message.lower() if message else ""
    error_type = (
        ("OOM" if "out of memory" in lower else "TIMEOUT" if "timeout" in lower else "MODEL_ERROR")
        if error
        else None
    )
    payload = {
        "schema_version": "prediction-v0.2",
        "prediction_id": f"pred2-{uuid.uuid4().hex}",
        "run_id": run_id,
        "status": "FAILED" if error else "COMPLETED",
        "error_type": error_type,
        "method_id": method.method_id,
        "adapter_id": adapter.adapter_id if adapter else None,
        "checkpoint_decision_sha256": checkpoint_decision_sha256,
        "example_id": example.example_id,
        "split": example.split,
        "scenario_family": example.scenario_family,
        "archetype": example.archetype,
        "model_id": model_config.model_id,
        "model_revision": model_config.revision,
        "model_config_sha256": content_sha256(model_config),
        "architecture_class": type(loaded.model).__name__,
        "resolved_device": loaded.device,
        "resolved_dtype": loaded.dtype,
        "task_version": example.task_version,
        "template_version": example.template_version,
        "prompt_template_version": method.prompt_template_version,
        "parser_version": method.parser_version,
        "evaluator_version": method.evaluator_version,
        "prompt_sha256": prompt_hash,
        "input_ids_sha256": ids_hash,
        "generation": generation.model_dump(mode="json"),
        "prompt_token_count": prompt_tokens,
        "generated_token_count": generated_tokens,
        "finish_condition": finish,
        "raw_output": raw_output,
        "parser_result": parser.model_dump(mode="json") if parser else None,
        "expected_contract": example.expected.model_dump(mode="json"),
        "expected_contract_sha256": content_sha256(example.expected),
        "evaluation_metadata": example.evaluation.model_dump(mode="json"),
        "metrics": metrics.model_dump(mode="json") if metrics else None,
        "started_at": started_at,
        "finished_at": datetime.now(UTC),
        "latency_ms": max(0, latency_ms),
        "errors": [message] if message else [],
    }
    return PredictionRecordV0_2.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_EXCLUSIONS),
        },
        strict=True,
    )


def _teacher_forced_loss(
    loaded: LoadedModel, examples: list[OpsRouteExample], prompt_version: str
) -> float:
    import torch

    total_loss = 0.0
    total_tokens = 0
    loaded.model.eval()
    for example in examples:
        batch, supervised_tokens = _supervised_batch(loaded, example, prompt_version)
        with torch.inference_mode():
            loss = loaded.model(**batch).loss
        total_loss += float(loss.detach().cpu()) * supervised_tokens
        total_tokens += supervised_tokens
    return total_loss / total_tokens


def _supervised_batch(
    loaded: LoadedModel, example: OpsRouteExample, prompt_version: str
) -> tuple[dict[str, Any], int]:
    prompt = render_prompt(loaded.tokenizer, example, prompt_version)
    messages = [
        *build_messages(example, prompt_version),
        {"role": "assistant", "content": canonical_json(example.expected)},
    ]
    full = loaded.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    prompt_ids = loaded.tokenizer(prompt, add_special_tokens=False)["input_ids"]
    encoded = loaded.tokenizer(full, return_tensors="pt", add_special_tokens=False)
    if encoded["input_ids"].shape[1] > 1024:
        raise ValueError(f"validation sequence exceeds 1024 tokens: {example.example_id}")
    labels = encoded["input_ids"].clone()
    labels[:, : len(prompt_ids)] = -100
    supervised = int((labels != -100).sum())
    batch = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
    batch["labels"] = labels.to(loaded.device)
    return batch, supervised


def _breakdown(key: str, predictions: list[PredictionRecordV0_2]) -> EvaluationBreakdown:
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


def _parser_counts(predictions: list[PredictionRecordV0_2]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        item.parser_result.classification for item in predictions if item.parser_result is not None
    )
    counts["FAILED"] = sum(item.status == "FAILED" for item in predictions)
    return dict(sorted(counts.items()))


def _adapter_for_method(
    experiment_path: Path,
    experiment: Day2ExperimentConfig,
    method: MethodConfigV0_2,
) -> tuple[AdapterReference | None, str | None]:
    if method.training_kind == "none":
        return None, None
    decisions = _checkpoint_decisions(experiment_path, experiment, method.method_id)
    selected = [item for item in decisions if item.status == "SELECTED"]
    if len(selected) != 1 or selected[0].selected_adapter is None:
        raise ValueError(f"{method.method_id} requires exactly one frozen selected checkpoint")
    adapter = selected[0].selected_adapter
    verify_adapter(adapter, Path.cwd())
    return adapter, selected[0].content_sha256


def _checkpoint_decisions(
    experiment_path: Path, experiment: Day2ExperimentConfig, method_id: str
) -> list[CheckpointDecisionV0_1]:
    root = _artifact_root(experiment_path, experiment) / "checkpoint-decisions"
    results: list[CheckpointDecisionV0_1] = []
    for path in sorted(root.glob("*/decision.json")):
        item = CheckpointDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        if item.method_id == method_id:
            results.append(item)
    return results


def _require_final_test_freeze(
    experiment_path: Path, experiment: Day2ExperimentConfig
) -> SourceCapabilityDecisionV0_1:
    gate_root = _artifact_root(experiment_path, experiment) / "source-gates"
    gates = [
        SourceCapabilityDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(gate_root.glob("*/decision.json"))
    ]
    confirmed = [item for item in gates if item.status == "SOURCE_CAPABILITY_CONFIRMED"]
    if len(confirmed) != 1:
        raise ValueError("test evaluation requires exactly one confirmed source gate")
    for method_id in (
        "source_adapted_full",
        "target_full_retrain",
        "target_limited_retrain_10pct",
    ):
        selected = [
            item
            for item in _checkpoint_decisions(experiment_path, experiment, method_id)
            if item.status == "SELECTED"
        ]
        if len(selected) != 1:
            raise ValueError(f"test evaluation requires a frozen checkpoint for {method_id}")
    return confirmed[0]


def _read_predictions(path: Path) -> list[PredictionRecordV0_2]:
    with path.open("r", encoding="utf-8") as handle:
        return [PredictionRecordV0_2.model_validate_json(line, strict=True) for line in handle]


def _eos_ids(loaded: LoadedModel) -> list[int]:
    value = loaded.model.generation_config.eos_token_id
    if value is None:
        value = loaded.tokenizer.eos_token_id
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    return [int(item) for item in value]


def _synchronize(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()


def _artifact_root(experiment_path: Path, experiment: Day2ExperimentConfig) -> Path:
    return _resolve(experiment_path, experiment.artifact_root)


def _resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    if direct.exists() or path.parts[0] in {"artifacts", "adapters"}:
        return direct
    return parent_file.parent / path
