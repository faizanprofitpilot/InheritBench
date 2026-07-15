"""Phase 3B confirmatory evaluation, checkpoint selection, and exact replay."""

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
from inheritbench.config import ModelConfig, ScenarioFamily, load_model_config
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.data.opsroute.schemas import EvaluationMetadata, OpsRouteExample, OpsRouteInput
from inheritbench.day2.evaluation import adapter_reference, verify_adapter
from inheritbench.day2.schemas import AdapterReference, EvaluationBreakdown, MetricValue
from inheritbench.day3_matched.distribution import _local_snapshot
from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.metrics import aggregate_metrics, score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import build_messages, render_prompt
from inheritbench.phase3b.baseline import runtime_lineage
from inheritbench.phase3b.config import (
    config_sha256,
    load_experiment_config,
    load_method_config,
    resolve,
)
from inheritbench.phase3b.confirmatory import find_confirmatory_bundle
from inheritbench.phase3b.schemas import (
    ConfirmatoryExampleV0_1,
    ConfirmatoryOracleRecordV0_1,
    Phase3BCheckpointDecisionV0_1,
    Phase3BEvaluationManifestV0_1,
    Phase3BEvaluationSummaryV0_1,
    Phase3BPredictionRecordV0_1,
    Phase3BReplayVerificationV0_1,
    Phase3BSplit,
    Phase3BSystemId,
)
from inheritbench.phase3b.training import (
    checkpoint_score,
    copy_selected_adapter,
    find_checkpoint_decision,
    find_completed_training,
    load_checkpoint_manifest,
    selection_key,
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
_DECISION_EXCLUSIONS = {"decision_id", "created_at", "content_sha256"}


class _EvaluationRecord:
    def __init__(
        self,
        *,
        example_id: str,
        scenario_family: ScenarioFamily,
        archetype: str,
        input_value: OpsRouteInput,
        expected: ActionContract,
        evaluation: EvaluationMetadata,
    ) -> None:
        self.example_id = example_id
        self.scenario_family = scenario_family
        self.archetype = archetype
        self.input = input_value
        self.expected = expected
        self.evaluation = evaluation


def evaluate_checkpoints(
    experiment_path: Path,
    *,
    device: Literal["mps", "cpu", "cuda"] = "mps",
) -> list[Path]:
    experiment = load_experiment_config(experiment_path)
    _, training = find_completed_training(experiment_path)
    adapter_root = resolve(experiment_path, experiment.adapter_root)
    existing = list(
        (resolve(experiment_path, experiment.artifact_root) / "validation").glob("*/manifest.json")
    )
    if existing:
        raise ValueError("Phase 3B checkpoint validation already exists")
    outputs = []
    for checkpoint_id in training.checkpoint_ids:
        checkpoint_path = adapter_root / checkpoint_id
        checkpoint = load_checkpoint_manifest(checkpoint_path)
        reference = adapter_reference(checkpoint_path, adapter_root)
        run, _ = _evaluate(
            experiment_path=experiment_path,
            system_id="target_hybrid_anchored_distillation_10",
            split="confirmatory_validation",
            adapter=reference,
            checkpoint_decision_sha256=checkpoint.content_sha256,
            device=device,
            output_root=resolve(experiment_path, experiment.artifact_root) / "validation",
            compute_teacher_forced_loss=True,
        )
        outputs.append(run)
    return outputs


def select_checkpoint(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    _, training = find_completed_training(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if any((root / "checkpoint-decisions").glob("*/decision.json")):
        raise ValueError("Phase 3B checkpoint decision already exists")
    summaries = {}
    losses = {}
    for path in sorted((root / "validation").glob("*/manifest.json")):
        manifest = Phase3BEvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        summaries[manifest.checkpoint_decision_sha256] = evaluation_summary(path.parent)
        losses[manifest.checkpoint_decision_sha256] = _read_validation_loss(path.parent)
    adapter_root = resolve(experiment_path, experiment.adapter_root)
    scores = []
    for checkpoint_id in training.checkpoint_ids:
        checkpoint = load_checkpoint_manifest(adapter_root / checkpoint_id)
        summary = summaries.get(checkpoint.content_sha256)
        if summary is None:
            raise ValueError(f"checkpoint lacks confirmatory validation: {checkpoint_id}")
        scores.append(checkpoint_score(checkpoint, summary, losses[checkpoint.content_sha256]))
    eligible = [item for item in scores if item.eligible]
    selected = max(eligible, key=selection_key) if eligible else None
    selected_adapter = None
    if selected is not None:
        selected_adapter = copy_selected_adapter(
            adapter_root / selected.checkpoint_id,
            adapter_root,
            selected.checkpoint_id,
            training,
        )
        model_config = load_model_config(
            resolve(experiment_path, experiment.target_model_config_path)
        )
        local = model_config.model_copy(
            update={
                "model_id": _local_snapshot(model_config.model_id, model_config.revision),
                "tokenizer_id": _local_snapshot(
                    model_config.tokenizer_id, model_config.tokenizer_revision
                ),
                "requested_dtype": "float16",
            }
        )
        loaded = _load_with_adapter(local, selected_adapter, "mps")
        unload_model(loaded)
    method = load_method_config(resolve(experiment_path, experiment.method_config_path))
    _, validation_manifest, _ = find_confirmatory_bundle(experiment_path)
    created_at = datetime.now(UTC)
    decision_id = f"phase3b-checkpoint-decision-{uuid.uuid4().hex[:16]}"
    lineage = runtime_lineage(experiment_path)
    payload = {
        "schema_version": "phase3b-checkpoint-decision-v0.1",
        "decision_id": decision_id,
        "method_id": "target_hybrid_anchored_distillation_10",
        "status": "SELECTED" if selected else "NO_SAFETY_ELIGIBLE_CHECKPOINT",
        "failure_code": None if selected else "NO_SAFETY_ELIGIBLE_CHECKPOINT",
        "training_run_id": training.run_id,
        "confirmatory_validation_sha256": validation_manifest.content_sha256,
        "method_config_sha256": config_sha256(method),
        "schedule_sha256": training.schedule_sha256,
        "hybrid_dataset_sha256": training.hybrid_dataset_sha256,
        "scores": [item.model_dump(mode="json") for item in scores],
        "selected_checkpoint_id": selected.checkpoint_id if selected else None,
        "selected_adapter": (
            selected_adapter.model_dump(mode="python") if selected_adapter else None
        ),
        "fresh_base_reload_verified": selected_adapter is not None,
        "selection_rule": ("semantic,strict,abstention,approval,argument_f1,loss,earliest"),
        "lineage": lineage,
        "created_at": created_at,
    }
    decision = Phase3BCheckpointDecisionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_DECISION_EXCLUSIONS),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "checkpoint-decisions",
        decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def evaluate_hybrid(
    experiment_path: Path,
    split: Literal["confirmatory_test", "exploratory_legacy_test"],
    *,
    device: Literal["auto", "mps", "cpu", "cuda"] = "mps",
) -> Path:
    experiment = load_experiment_config(experiment_path)
    _, decision = find_checkpoint_decision(experiment_path)
    if decision.status != "SELECTED" or decision.selected_adapter is None:
        raise ValueError("Phase 3B evaluation requires a selected safety-eligible checkpoint")
    if split == "exploratory_legacy_test":
        _require_hybrid_primary_replay(experiment_path)
    output = resolve(experiment_path, experiment.artifact_root) / (
        "test" if split == "confirmatory_test" else "legacy-test"
    )
    _reject_logical_rerun(output, "target_hybrid_anchored_distillation_10", split)
    return _evaluate(
        experiment_path=experiment_path,
        system_id="target_hybrid_anchored_distillation_10",
        split=split,
        adapter=decision.selected_adapter,
        checkpoint_decision_sha256=decision.content_sha256,
        device=device,
        output_root=output,
        compute_teacher_forced_loss=False,
    )[0]


def evaluate_confirmatory_matrix(
    experiment_path: Path,
    *,
    device: Literal["auto", "mps", "cpu", "cuda"] = "mps",
) -> list[Path]:
    experiment = load_experiment_config(experiment_path)
    _require_hybrid_primary_replay(experiment_path)
    output = resolve(experiment_path, experiment.artifact_root) / "test"
    systems: list[Phase3BSystemId] = [
        "source_base_supporting",
        "source_adapted_full",
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
    ]
    outputs = []
    for system_id in systems:
        _reject_logical_rerun(output, system_id, "confirmatory_test")
        adapter = _historical_adapter(system_id)
        outputs.append(
            _evaluate(
                experiment_path=experiment_path,
                system_id=system_id,
                split="confirmatory_test",
                adapter=adapter,
                checkpoint_decision_sha256=None,
                device=device,
                output_root=output,
                compute_teacher_forced_loss=False,
            )[0]
        )
    return outputs


def replay_evaluation(run_directory: Path, output_root: Path) -> Path:
    manifest = Phase3BEvaluationManifestV0_1.model_validate_json(
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
            raise ValueError(f"Phase 3B replay mismatch: {prediction.prediction_id}")
    stored = evaluation_summary(run_directory)
    rebuilt = build_summary(
        predictions,
        run_id=stored.run_id,
        system_id=stored.system_id,
        split=stored.split,
        created_at=stored.created_at,
        finished_at=stored.finished_at,
    )
    if rebuilt != stored:
        raise ValueError("Phase 3B evaluation summary replay mismatch")
    created_at = datetime.now(UTC)
    replay_id = f"phase3b-replay-evaluation-{manifest.run_id}-{uuid.uuid4().hex[:8]}"
    payload = {
        "schema_version": "phase3b-replay-v0.1",
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
    verification = Phase3BReplayVerificationV0_1.model_validate(
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
    predictions: list[Phase3BPredictionRecordV0_1],
    *,
    run_id: str,
    system_id: Phase3BSystemId,
    split: Phase3BSplit,
    created_at: datetime,
    finished_at: datetime,
) -> Phase3BEvaluationSummaryV0_1:
    completed = [item for item in predictions if item.status == "COMPLETED"]
    metrics = [item.metrics for item in completed if item.metrics is not None]
    aggregate = {
        name: MetricValue.model_validate(value, strict=True)
        for name, value in aggregate_metrics(metrics).items()
    }
    groups: dict[str, list[Phase3BPredictionRecordV0_1]] = {"all": predictions}
    for prediction in predictions:
        groups.setdefault(f"family:{prediction.scenario_family}", []).append(prediction)
        groups.setdefault(f"archetype:{prediction.archetype}", []).append(prediction)
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
    status: Literal["COMPLETED", "FAILED"] = (
        "FAILED" if any(item.status == "FAILED" for item in predictions) else "COMPLETED"
    )
    payload = {
        "schema_version": "phase3b-evaluation-summary-v0.1",
        "run_id": run_id,
        "system_id": system_id,
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
    return Phase3BEvaluationSummaryV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )


def evaluation_summary(run_directory: Path) -> Phase3BEvaluationSummaryV0_1:
    return Phase3BEvaluationSummaryV0_1.model_validate_json(
        (run_directory / "summary.json").read_bytes(), strict=True
    )


def _evaluate(
    *,
    experiment_path: Path,
    system_id: Phase3BSystemId,
    split: Phase3BSplit,
    adapter: AdapterReference | None,
    checkpoint_decision_sha256: str | None,
    device: Literal["auto", "mps", "cpu", "cuda"],
    output_root: Path,
    compute_teacher_forced_loss: bool,
) -> tuple[Path, float]:
    records, split_sha256, oracle_sha256 = _load_records(experiment_path, split)
    expected = 64 if split == "confirmatory_test" else 32
    if len(records) != expected:
        raise ValueError(f"Phase 3B {split} requires exactly {expected} records")
    model_config = _system_model_config(experiment_path, system_id)
    snapshot = _local_snapshot(model_config.model_id, model_config.revision)
    inference_config = model_config.model_copy(
        update={
            "model_id": snapshot,
            "tokenizer_id": snapshot,
            "requested_dtype": "float16",
        }
    )
    run_id = f"phase3b-{system_id}-{split}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(UTC)
    generation = GenerationConfig(do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714)
    lineage = runtime_lineage(experiment_path, checkpoint_decision_sha256)
    loaded = _load_with_adapter(inference_config, adapter, device)
    try:
        predictions = [
            _infer_one(
                loaded,
                model_config,
                system_id,
                split,
                adapter,
                checkpoint_decision_sha256,
                record,
                generation,
                run_id,
                lineage,
            )
            for record in records
        ]
        validation_loss = (
            _teacher_forced_loss(loaded, records) if compute_teacher_forced_loss else 0.0
        )
    finally:
        unload_model(loaded)
    predictions.sort(key=lambda item: item.example_id)
    finished_at = datetime.now(UTC)
    summary = build_summary(
        predictions,
        run_id=run_id,
        system_id=system_id,
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
    guard = content_sha256(
        {
            "system_id": system_id,
            "split": split,
            "split_sha256": split_sha256,
            "checkpoint": checkpoint_decision_sha256,
        }
    )
    payload = {
        "schema_version": "phase3b-evaluation-run-v0.1",
        "run_id": run_id,
        "system_id": system_id,
        "split": split,
        "status": summary.status,
        "expected_predictions": expected,
        "terminal_predictions": len(predictions),
        "split_sha256": split_sha256,
        "oracle_sha256": oracle_sha256,
        "adapter": adapter.model_dump(mode="python") if adapter else None,
        "checkpoint_decision_sha256": checkpoint_decision_sha256,
        "exactly_once_guard_sha256": guard if split != "confirmatory_validation" else None,
        "generation": generation.model_dump(mode="json"),
        "prediction_artifact": prediction_ref.model_dump(mode="json"),
        "summary_artifact": summary_ref.model_dump(mode="json"),
        "lineage": lineage,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    manifest = Phase3BEvaluationManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )
    files = {
        "predictions.jsonl": prediction_bytes,
        "summary.json": summary_bytes,
        "manifest.json": canonical_json_bytes(manifest) + b"\n",
    }
    if compute_teacher_forced_loss:
        files["validation_loss.json"] = (
            canonical_json_bytes({"teacher_forced_loss": validation_loss}) + b"\n"
        )
    return write_atomic_bundle(output_root, run_id, files), validation_loss


def _infer_one(
    loaded: LoadedModel,
    model_config: ModelConfig,
    system_id: Phase3BSystemId,
    split: Phase3BSplit,
    adapter: AdapterReference | None,
    decision_sha256: str | None,
    record: _EvaluationRecord,
    generation: GenerationConfig,
    run_id: str,
    lineage: Any,
) -> Phase3BPredictionRecordV0_1:
    import torch

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    prompt_hash = None
    ids_hash = None
    try:
        prompt = render_prompt(loaded.tokenizer, record, "0.1.0")
        prompt_hash = sha256_text(prompt)
        encoded = loaded.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        token_ids = encoded["input_ids"][0].tolist()
        ids_hash = input_ids_sha256(token_ids)
        if len(token_ids) > 1024:
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
    payload = {
        "schema_version": "phase3b-prediction-v0.1",
        "prediction_id": f"phase3b-prediction-{uuid.uuid4().hex}",
        "run_id": run_id,
        "status": "FAILED" if error else "COMPLETED",
        "error_type": error_type,
        "system_id": system_id,
        "split": split,
        "adapter_id": adapter.adapter_id if adapter else None,
        "checkpoint_decision_sha256": decision_sha256,
        "example_id": record.example_id,
        "scenario_family": record.scenario_family,
        "archetype": record.archetype,
        "model_id": model_config.model_id,
        "model_revision": model_config.revision,
        "resolved_device": loaded.device,
        "resolved_dtype": loaded.dtype,
        "prompt_sha256": prompt_hash,
        "input_ids_sha256": ids_hash,
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
    return Phase3BPredictionRecordV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_EXCLUSIONS),
        },
        strict=True,
    )


def _load_records(
    experiment_path: Path, split: Phase3BSplit
) -> tuple[list[_EvaluationRecord], str, str]:
    experiment = load_experiment_config(experiment_path)
    if split == "exploratory_legacy_test":
        examples = load_examples(
            resolve(experiment_path, experiment.dataset_directory),
            _legacy_test_ids(experiment_path),
        )
        records = [
            _EvaluationRecord(
                example_id=item.example_id,
                scenario_family=item.scenario_family,
                archetype=item.archetype,
                input_value=item.input,
                expected=item.expected,
                evaluation=item.evaluation,
            )
            for item in examples
        ]
        split_hash = content_sha256([item.record_sha256 for item in examples])
        oracle_hash = content_sha256([content_sha256(item.expected) for item in examples])
        return records, split_hash, oracle_hash
    bundle, validation, test = find_confirmatory_bundle(experiment_path)
    directory = "validation" if split == "confirmatory_validation" else "test"
    manifest = validation if split == "confirmatory_validation" else test
    examples = _read_jsonl(bundle / directory / "inputs.jsonl", ConfirmatoryExampleV0_1)
    oracles = {
        item.example_id: item
        for item in _read_jsonl(bundle / directory / "oracle.jsonl", ConfirmatoryOracleRecordV0_1)
    }
    records = []
    for item in examples:
        oracle = oracles[item.example_id]
        if oracle.example_record_sha256 != item.record_sha256:
            raise ValueError(f"confirmatory oracle mismatch: {item.example_id}")
        records.append(
            _EvaluationRecord(
                example_id=item.example_id,
                scenario_family=item.scenario_family,
                archetype=item.archetype,
                input_value=item.input,
                expected=oracle.expected_contract,
                evaluation=oracle.evaluation_metadata,
            )
        )
    return records, manifest.content_sha256, manifest.oracle_artifact.content_sha256


def _system_model_config(experiment_path: Path, system_id: Phase3BSystemId) -> ModelConfig:
    experiment = load_experiment_config(experiment_path)
    path = (
        experiment.source_model_config_path
        if system_id.startswith("source_")
        else experiment.target_model_config_path
    )
    return load_model_config(resolve(experiment_path, path))


def _historical_adapter(system_id: Phase3BSystemId) -> AdapterReference | None:
    directories = {
        "source_adapted_full": "source_adapted_full-8242bcea6f327545",
        "target_full_retrain": "target_full_retrain-fd1966615c845dab",
        "target_limited_retrain_10pct": "target_limited_retrain_10pct-c2e5ec18f58ba342",
    }
    name = directories.get(system_id)
    if name is None:
        return None
    root = Path.cwd() / "adapters/day2"
    reference = adapter_reference(root / name, root)
    verify_adapter(reference, Path.cwd())
    return reference.model_copy(update={"verified": True, "verified_at": datetime.now(UTC)})


def _load_with_adapter(
    config: ModelConfig,
    adapter: AdapterReference | None,
    device: Literal["auto", "mps", "cpu", "cuda"],
) -> LoadedModel:
    loaded = load_model(config, device_override=device)
    if adapter is not None:
        from peft import PeftModel

        path = verify_adapter(adapter, Path.cwd())
        peft_model: Any = PeftModel
        loaded.model = peft_model.from_pretrained(loaded.model, path, is_trainable=False)
    loaded.model.eval()
    return loaded


def _teacher_forced_loss(loaded: LoadedModel, records: list[_EvaluationRecord]) -> float:
    import torch

    total_loss = 0.0
    total_tokens = 0
    loaded.model.eval()
    for record in records:
        prompt = render_prompt(loaded.tokenizer, record, "0.1.0")
        messages = [
            *build_messages(record, "0.1.0"),
            {"role": "assistant", "content": canonical_json(record.expected)},
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


def _breakdown(key: str, predictions: list[Phase3BPredictionRecordV0_1]) -> EvaluationBreakdown:
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


def _parser_counts(predictions: list[Phase3BPredictionRecordV0_1]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        item.parser_result.classification for item in predictions if item.parser_result is not None
    )
    counts["FAILED"] = sum(item.status == "FAILED" for item in predictions)
    return dict(sorted(counts.items()))


def _reject_logical_rerun(root: Path, system_id: Phase3BSystemId, split: Phase3BSplit) -> None:
    for path in root.glob("*/manifest.json"):
        manifest = Phase3BEvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        if manifest.system_id == system_id and manifest.split == split:
            raise ValueError(f"Phase 3B {system_id} {split} may run exactly once")


def _require_hybrid_primary_replay(experiment_path: Path) -> None:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    hybrid = []
    for path in (root / "test").glob("*/manifest.json"):
        manifest = Phase3BEvaluationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        if manifest.system_id == "target_hybrid_anchored_distillation_10":
            hybrid.append(manifest)
    if len(hybrid) != 1 or hybrid[0].status != "COMPLETED":
        raise ValueError("hybrid confirmatory test must complete before later evaluations")
    replayed = []
    for path in (root / "replays").glob("*/verification.json"):
        replay = Phase3BReplayVerificationV0_1.model_validate_json(path.read_bytes(), strict=True)
        if replay.original_artifact_id == hybrid[0].run_id and replay.status == "PASSED":
            replayed.append(replay)
    if len(replayed) != 1:
        raise ValueError("hybrid confirmatory test requires an exact replay")


def _legacy_test_ids(experiment_path: Path) -> list[str]:
    experiment = load_experiment_config(experiment_path)
    path = resolve(experiment_path, experiment.dataset_directory) / "test.jsonl"
    examples = _read_jsonl(path, OpsRouteExample)
    return sorted(item.example_id for item in examples)


def _read_validation_loss(run_directory: Path) -> float:
    import json

    return float(
        json.loads((run_directory / "validation_loss.json").read_text(encoding="utf-8"))[
            "teacher_forced_loss"
        ]
    )


def _read_predictions(path: Path) -> list[Phase3BPredictionRecordV0_1]:
    return _read_jsonl(path, Phase3BPredictionRecordV0_1)


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        return [schema.model_validate_json(line, strict=True) for line in handle]


def _synchronize(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()
