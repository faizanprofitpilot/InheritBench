"""Frozen validation/test evaluation and exact replay for matched recovery."""

from __future__ import annotations

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
    sha256_text,
)
from inheritbench.artifacts.schemas import GenerationConfig
from inheritbench.artifacts.store import (
    artifact_reference,
    verify_reference,
    write_atomic_bundle,
)
from inheritbench.config import ModelConfig, load_model_config
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2.data import find_data_bundle, load_subset
from inheritbench.day2.evaluation import verify_adapter
from inheritbench.day2.schemas import AdapterReference, EvaluationBreakdown, MetricValue
from inheritbench.day3_matched.config import (
    config_sha256,
    load_experiment_config,
    load_method_config,
    resolve,
)
from inheritbench.day3_matched.distribution import _local_snapshot
from inheritbench.day3_matched.filtering import find_synthetic_dataset
from inheritbench.day3_matched.schemas import (
    MatchedEvaluationRunManifestV0_1,
    MatchedEvaluationSummaryV0_1,
    MatchedPredictionRecordV0_1,
    MatchedReplayVerificationV0_1,
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
    experiment_path: Path,
    split: Literal["validation", "test"],
    *,
    device: Literal["auto", "mps", "cpu", "cuda"] = "mps",
) -> Path:
    from inheritbench.day3_matched.training import find_checkpoint_decision

    experiment = load_experiment_config(experiment_path)
    _, decision = find_checkpoint_decision(experiment_path)
    if decision.status != "SELECTED" or decision.selected_adapter is None:
        raise ValueError("matched evaluation requires a safety-eligible selected checkpoint")
    if split == "test":
        test_root = resolve(experiment_path, experiment.artifact_root) / "test"
        if any(test_root.glob("day3-matched-target_synthetic_distillation_matched-test-*")):
            raise ValueError("the matched held-out test may run exactly once")
    return _evaluate(
        experiment_path=experiment_path,
        split=split,
        adapter=decision.selected_adapter,
        checkpoint_decision_sha256=decision.content_sha256,
        device=device,
        output_root=resolve(experiment_path, experiment.artifact_root) / split,
        compute_teacher_forced_loss=False,
    )[0]


def evaluate_checkpoint(
    experiment_path: Path,
    adapter: AdapterReference,
    checkpoint_manifest_sha256: str,
    *,
    device: Literal["mps", "cpu", "cuda"] = "mps",
) -> tuple[Path, float]:
    experiment = load_experiment_config(experiment_path)
    return _evaluate(
        experiment_path=experiment_path,
        split="validation",
        adapter=adapter,
        checkpoint_decision_sha256=checkpoint_manifest_sha256,
        device=device,
        output_root=resolve(experiment_path, experiment.artifact_root) / "validation",
        compute_teacher_forced_loss=True,
    )


def replay_evaluation(run_directory: Path, output_root: Path) -> Path:
    started = time.perf_counter()
    manifest = MatchedEvaluationRunManifestV0_1.model_validate_json(
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
            raise ValueError(f"matched evaluation replay mismatch: {prediction.prediction_id}")
    stored = evaluation_summary(run_directory)
    rebuilt = build_summary(
        predictions,
        run_id=stored.run_id,
        split=stored.split,
        created_at=stored.created_at,
        finished_at=stored.finished_at,
    )
    if rebuilt != stored:
        raise ValueError("matched evaluation summary replay mismatch")
    created_at = datetime.now(UTC)
    replay_id = f"day3-matched-replay-evaluation-{manifest.run_id}-{uuid.uuid4().hex[:8]}"
    payload = {
        "schema_version": "day3-matched-replay-verification-v0.1",
        "replay_id": replay_id,
        "kind": "evaluation",
        "original_artifact_id": manifest.run_id,
        "status": "PASSED",
        "records_verified": len(predictions),
        "byte_hashes_match": True,
        "content_matches": True,
        "duration_seconds": time.perf_counter() - started,
        "created_at": created_at,
    }
    verification = MatchedReplayVerificationV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"replay_id", "created_at", "duration_seconds"}
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
    predictions: list[MatchedPredictionRecordV0_1],
    *,
    run_id: str,
    split: Literal["validation", "test"],
    created_at: datetime,
    finished_at: datetime,
) -> MatchedEvaluationSummaryV0_1:
    completed = [item for item in predictions if item.status == "COMPLETED"]
    metrics = [item.metrics for item in completed if item.metrics is not None]
    aggregate = {
        name: MetricValue.model_validate(value, strict=True)
        for name, value in aggregate_metrics(metrics).items()
    }
    groups: dict[str, list[MatchedPredictionRecordV0_1]] = {"all": predictions}
    for prediction in predictions:
        groups.setdefault(f"family:{prediction.scenario_family}", []).append(prediction)
        groups.setdefault(f"archetype:{prediction.archetype}", []).append(prediction)
        groups.setdefault(f"expected_decision:{prediction.expected_contract.decision}", []).append(
            prediction
        )
        if prediction.expected_contract.approval_required:
            groups.setdefault("approval_required", []).append(prediction)
        if prediction.expected_contract.decision in {"ask_clarification", "refuse", "no_action"}:
            groups.setdefault("abstention", []).append(prediction)
    status: Literal["COMPLETED", "FAILED"] = (
        "FAILED" if any(item.status == "FAILED" for item in predictions) else "COMPLETED"
    )
    payload = {
        "schema_version": "day3-matched-evaluation-summary-v0.1",
        "run_id": run_id,
        "method_id": "target_synthetic_distillation_matched",
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
        "breakdowns": {
            name: _breakdown(name, values).model_dump(mode="json")
            for name, values in sorted(groups.items())
        },
        "run_errors": [error for item in predictions for error in item.errors],
        "created_at": created_at,
        "finished_at": finished_at,
    }
    return MatchedEvaluationSummaryV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )


def evaluation_summary(run_directory: Path) -> MatchedEvaluationSummaryV0_1:
    return MatchedEvaluationSummaryV0_1.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )


def find_test_run(
    experiment_path: Path,
) -> tuple[Path, MatchedEvaluationRunManifestV0_1, MatchedEvaluationSummaryV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "test"
    values = []
    for path in sorted(root.glob("*/manifest.json")):
        manifest = MatchedEvaluationRunManifestV0_1.model_validate_json(
            path.read_bytes(), strict=True
        )
        if manifest.status == "COMPLETED":
            summary = evaluation_summary(path.parent)
            values.append((path.parent, manifest, summary))
    if len(values) != 1:
        raise ValueError(f"expected one completed matched test run, found {len(values)}")
    return values[0]


def _evaluate(
    *,
    experiment_path: Path,
    split: Literal["validation", "test"],
    adapter: AdapterReference,
    checkpoint_decision_sha256: str,
    device: Literal["auto", "mps", "cpu", "cuda"],
    output_root: Path,
    compute_teacher_forced_loss: bool,
) -> tuple[Path, float]:
    experiment = load_experiment_config(experiment_path)
    method_path = resolve(experiment_path, experiment.method_config_path)
    method = load_method_config(method_path)
    day2_experiment_path = Path("configs/experiments/day2.yaml")
    from inheritbench.day2.config import load_experiment_config as load_day2_experiment

    day2_experiment = load_day2_experiment(day2_experiment_path)
    bundle = find_data_bundle(day2_experiment_path, day2_experiment)
    subset = load_subset(bundle, "full_validation" if split == "validation" else "final_test")
    if subset.source_split != split or len(subset.entries) != 32 or subset.fixture_evidence:
        raise ValueError(f"matched {split} evaluation requires all 32 frozen records")
    examples = load_examples(
        resolve(experiment_path, experiment.dataset_directory), subset.example_ids
    )
    if any(item.split != split for item in examples):
        raise ValueError(f"matched {split} evaluation includes a different split")
    _, synthetic_dataset = find_synthetic_dataset(experiment_path)
    model_config = load_model_config(resolve(method_path, method.model_config_path))
    local_snapshot = _local_snapshot(model_config.model_id, model_config.revision)
    inference_config = model_config.model_copy(
        update={
            "model_id": local_snapshot,
            "tokenizer_id": local_snapshot,
            "requested_dtype": "float16",
        }
    )
    run_id = (
        f"day3-matched-target_synthetic_distillation_matched-{split}-"
        f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    )
    created_at = datetime.now(UTC)
    generation = GenerationConfig(do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714)
    loaded = _load_with_adapter(inference_config, adapter, device)
    try:
        predictions = [
            _infer_one(
                loaded,
                model_config,
                adapter,
                checkpoint_decision_sha256,
                synthetic_dataset.content_sha256,
                example,
                generation,
                run_id,
            )
            for example in examples
        ]
        teacher_loss = (
            _teacher_forced_loss(loaded, examples) if compute_teacher_forced_loss else 0.0
        )
    finally:
        unload_model(loaded)
    predictions.sort(key=lambda item: item.example_id)
    finished_at = datetime.now(UTC)
    summary = build_summary(
        predictions,
        run_id=run_id,
        split=split,
        created_at=created_at,
        finished_at=finished_at,
    )
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
        "schema_version": "day3-matched-evaluation-run-v0.1",
        "run_id": run_id,
        "method_id": "target_synthetic_distillation_matched",
        "status": summary.status,
        "split": split,
        "method_config_sha256": config_sha256(method),
        "subset_sha256": subset.content_sha256,
        "dataset_sha256": subset.dataset_sha256,
        "synthetic_dataset_sha256": synthetic_dataset.content_sha256,
        "adapter": adapter.model_dump(mode="python"),
        "checkpoint_decision_sha256": checkpoint_decision_sha256,
        "generation": generation.model_dump(mode="json"),
        "prediction_artifact": prediction_ref.model_dump(mode="json"),
        "summary_artifact": summary_ref.model_dump(mode="json"),
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = MatchedEvaluationRunManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )
    return (
        write_atomic_bundle(
            output_root,
            run_id,
            {
                "predictions.jsonl": prediction_bytes,
                "summary.json": summary_bytes,
                "manifest.json": canonical_json_bytes(manifest) + b"\n",
            },
        ),
        teacher_loss,
    )


def _load_with_adapter(config: ModelConfig, adapter: AdapterReference, device: str) -> LoadedModel:
    loaded = load_model(config, device_override=device)
    from peft import PeftModel

    path = verify_adapter(adapter, Path.cwd())
    peft_model: Any = PeftModel
    loaded.model = peft_model.from_pretrained(loaded.model, path, is_trainable=False)
    loaded.model.eval()
    return loaded


def _infer_one(
    loaded: LoadedModel,
    model_config: ModelConfig,
    adapter: AdapterReference,
    decision_sha256: str,
    synthetic_dataset_sha256: str,
    example: OpsRouteExample,
    generation: GenerationConfig,
    run_id: str,
) -> MatchedPredictionRecordV0_1:
    import torch

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    prompt_hash = None
    ids_hash = None
    prompt_tokens = None
    finish: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"] | None
    try:
        prompt = render_prompt(loaded.tokenizer, example, "0.1.0")
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
        count = int(completion.shape[0])
        eos_ids = _eos_ids(loaded)
        finish = (
            "EOS"
            if count and int(completion[-1]) in eos_ids
            else "MAX_NEW_TOKENS"
            if count >= generation.max_new_tokens
            else "OTHER"
        )
        parser = parse_action_contract(raw_output)
        metrics = score_prediction(parser, example.expected, example.evaluation)
        error = None
    except Exception as exc:
        raw_output = ""
        count = None
        finish = None
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
    payload = {
        "schema_version": "day3-matched-prediction-v0.1",
        "prediction_id": f"matched-prediction-{uuid.uuid4().hex}",
        "run_id": run_id,
        "status": "FAILED" if error else "COMPLETED",
        "error_type": error_type,
        "method_id": "target_synthetic_distillation_matched",
        "adapter_id": adapter.adapter_id,
        "checkpoint_decision_sha256": decision_sha256,
        "synthetic_dataset_sha256": synthetic_dataset_sha256,
        "example_id": example.example_id,
        "split": example.split,
        "scenario_family": example.scenario_family,
        "archetype": example.archetype,
        "model_id": model_config.model_id,
        "model_revision": model_config.revision,
        "resolved_device": loaded.device,
        "resolved_dtype": loaded.dtype,
        "prompt_sha256": prompt_hash,
        "input_ids_sha256": ids_hash,
        "generation": generation.model_dump(mode="json"),
        "prompt_token_count": prompt_tokens,
        "generated_token_count": count,
        "finish_condition": finish,
        "raw_output": raw_output,
        "parser_result": parser.model_dump(mode="json") if parser else None,
        "expected_contract": example.expected.model_dump(mode="json"),
        "evaluation_metadata": example.evaluation.model_dump(mode="json"),
        "metrics": metrics.model_dump(mode="json") if metrics else None,
        "started_at": started_at,
        "finished_at": datetime.now(UTC),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "errors": [message] if message else [],
    }
    return MatchedPredictionRecordV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_EXCLUSIONS),
        },
        strict=True,
    )


def _teacher_forced_loss(loaded: LoadedModel, examples: list[OpsRouteExample]) -> float:
    import torch

    total_loss = 0.0
    total_tokens = 0
    loaded.model.eval()
    for example in examples:
        prompt = render_prompt(loaded.tokenizer, example, "0.1.0")
        messages = [
            *build_messages(example, "0.1.0"),
            {"role": "assistant", "content": canonical_json(example.expected)},
        ]
        full = loaded.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        prompt_ids = loaded.tokenizer(prompt, add_special_tokens=False)["input_ids"]
        encoded = loaded.tokenizer(full, return_tensors="pt", add_special_tokens=False)
        labels = encoded["input_ids"].clone()
        labels[:, : len(prompt_ids)] = -100
        supervised = int((labels != -100).sum())
        batch = {name: tensor.to(loaded.device) for name, tensor in encoded.items()}
        batch["labels"] = labels.to(loaded.device)
        with torch.inference_mode():
            loss = loaded.model(**batch).loss
        total_loss += float(loss.detach().cpu()) * supervised
        total_tokens += supervised
    return total_loss / total_tokens


def _breakdown(key: str, predictions: list[MatchedPredictionRecordV0_1]) -> EvaluationBreakdown:
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


def _parser_counts(predictions: list[MatchedPredictionRecordV0_1]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        item.parser_result.classification for item in predictions if item.parser_result is not None
    )
    counts["FAILED"] = sum(item.status == "FAILED" for item in predictions)
    return dict(sorted(counts.items()))


def _read_predictions(path: Path) -> list[MatchedPredictionRecordV0_1]:
    with path.open(encoding="utf-8") as handle:
        return [
            MatchedPredictionRecordV0_1.model_validate_json(line, strict=True) for line in handle
        ]


def _eos_ids(loaded: LoadedModel) -> list[int]:
    value = loaded.model.generation_config.eos_token_id
    if value is None:
        value = loaded.tokenizer.eos_token_id
    if value is None:
        return []
    return [value] if isinstance(value, int) else [int(item) for item in value]


def _synchronize(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()
