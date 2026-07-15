"""Verified teacher reference and candidate-only matched inference."""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    input_ids_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.schemas import GenerationConfig
from inheritbench.artifacts.store import artifact_reference, write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.day3_matched.config import load_experiment_config, resolve
from inheritbench.day3_matched.distribution import (
    _local_snapshot,
    find_pool,
    load_candidates,
    load_pool_manifest,
)
from inheritbench.day3_matched.schemas import (
    DistributionMatchAuditV0_1,
    MatchedLeakageAuditV0_1,
    MatchedPoolManifestV0_1,
    MatchedTeacherPredictionV0_1,
    MatchedTeacherRunManifestV0_1,
    TeacherReferenceV0_1,
)
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import render_prompt

_ORIGINAL_VERIFICATION = Path(
    "artifacts/day3/teacher-verifications/"
    "day3-teacher-verification-51f66637be7badc8/verification.json"
)
_PREDICTION_EXCLUSIONS = {
    "prediction_id",
    "run_id",
    "started_at",
    "finished_at",
    "latency_ms",
    "content_sha256",
}
_RUN_EXCLUSIONS = {"run_id", "created_at", "finished_at", "content_sha256"}
_REFERENCE_EXCLUSIONS = {"reference_id", "verified_at", "content_sha256"}


def verify_teacher(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    source_path = Path.cwd() / _ORIGINAL_VERIFICATION
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if raw.get("status") != "VERIFIED" or raw.get("content_sha256") != (
        "8ac32c0c6e4d811419faa3896a9955a9ad9582ef3f293f5129595ca3bdef4d56"
    ):
        raise ValueError("the immutable original Day 3 teacher verification is invalid")
    adapter_path = Path.cwd() / raw["adapter_relative_path"]
    actual = {
        str(path.relative_to(adapter_path)): sha256_file(path)
        for path in sorted(adapter_path.rglob("*"))
        if path.is_file()
    }
    if actual != raw["adapter_file_sha256s"]:
        raise ValueError("local teacher adapter bytes do not match verified Day 2 release bytes")
    source = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    verified_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "source_verification": raw["content_sha256"],
            "adapter_files": actual,
            "model_revision": source.revision,
        }
    )
    payload = {
        "schema_version": "day3-matched-teacher-reference-v0.1",
        "reference_id": f"day3-matched-teacher-reference-{identity[:16]}",
        "status": "VERIFIED",
        "source_verification_path": str(_ORIGINAL_VERIFICATION),
        "source_verification_sha256": raw["content_sha256"],
        "adapter_id": raw["adapter_id"],
        "release_tag": raw["release_tag"],
        "archive_sha256": raw["archive_sha256"],
        "adapter_file_sha256s": actual,
        "adapter_relative_path": raw["adapter_relative_path"],
        "model_id": source.model_id,
        "model_revision": source.revision,
        "tokenizer_id": source.tokenizer_id,
        "tokenizer_revision": source.tokenizer_revision,
        "verified_at": verified_at,
    }
    reference = TeacherReferenceV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_REFERENCE_EXCLUSIONS),
        },
        strict=True,
    )
    root = resolve(experiment_path, experiment.artifact_root) / "teacher-references"
    destination = root / reference.reference_id
    if destination.exists():
        stored = TeacherReferenceV0_1.model_validate_json(
            (destination / "reference.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != reference.content_sha256:
            raise ValueError("existing matched teacher reference differs")
        return destination
    return write_atomic_bundle(
        root,
        reference.reference_id,
        {"reference.json": canonical_json_bytes(reference) + b"\n"},
    )


def find_teacher_reference(experiment_path: Path) -> tuple[Path, TeacherReferenceV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "teacher-references"
    matches = sorted(root.glob("day3-matched-teacher-reference-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one matched teacher reference, found {len(matches)}")
    value = TeacherReferenceV0_1.model_validate_json(
        (matches[0] / "reference.json").read_bytes(), strict=True
    )
    return matches[0], value


def run_teacher(
    experiment_path: Path,
    phase: Literal["initial", "expansion"],
    *,
    device: Literal["mps", "cpu", "cuda"] = "mps",
    resume_run: Path | None = None,
) -> Path:
    experiment = load_experiment_config(experiment_path)
    pool_path = find_pool(experiment_path, phase)
    pool = load_pool_manifest(pool_path)
    candidates = load_candidates(pool_path)
    distribution = DistributionMatchAuditV0_1.model_validate_json(
        (pool_path / "distribution_audit.json").read_bytes(), strict=True
    )
    leakage = MatchedLeakageAuditV0_1.model_validate_json(
        (pool_path / "leakage_audit.json").read_bytes(), strict=True
    )
    if (
        distribution.status != "PASS"
        or leakage.status != "PASS"
        or distribution.content_sha256 != pool.distribution_audit_sha256
        or leakage.content_sha256 != pool.leakage_audit_sha256
    ):
        raise ValueError("teacher generation requires passing frozen matched audits")
    _, reference = find_teacher_reference(experiment_path)
    previous: list[MatchedTeacherPredictionV0_1] = []
    resumed_from_run_id: str | None = None
    if resume_run is not None:
        previous_manifest = MatchedTeacherRunManifestV0_1.model_validate_json(
            (resume_run / "manifest.json").read_bytes(), strict=True
        )
        if previous_manifest.status != "FAILED" or previous_manifest.phase != phase:
            raise ValueError("teacher resume requires a failed run for the same phase")
        if previous_manifest.pool_content_sha256 != pool.content_sha256:
            raise ValueError("teacher resume pool hash mismatch")
        if previous_manifest.teacher_reference_sha256 != reference.content_sha256:
            raise ValueError("teacher resume reference hash mismatch")
        previous = _read_predictions(resume_run / "predictions.jsonl")
        resumed_from_run_id = previous_manifest.run_id
    successful = {item.candidate_id for item in previous if item.status == "COMPLETED"}
    pending = [item for item in candidates if item.candidate_id not in successful]
    created_at = datetime.now(UTC)
    run_id = f"day3-matched-teacher-{phase}-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    active = artifact_root / "active" / run_id
    active.mkdir(parents=True, exist_ok=False)
    progress_path = active / "predictions.jsonl"
    source_config = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    local_snapshot = _local_snapshot(source_config.model_id, source_config.revision)
    inference_config = source_config.model_copy(
        update={
            "model_id": local_snapshot,
            "tokenizer_id": local_snapshot,
            "requested_dtype": "float16",
        }
    )
    generation = GenerationConfig(do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714)
    predictions = list(previous)
    started = time.perf_counter()
    loaded: LoadedModel | None = None
    try:
        loaded = load_model(inference_config, device_override=device)
        from peft import PeftModel

        peft_model: Any = PeftModel
        adapter_path = Path.cwd() / reference.adapter_relative_path
        loaded.model = peft_model.from_pretrained(loaded.model, adapter_path, is_trainable=False)
        loaded.model.eval()
        for candidate in pending:
            prediction = _infer_candidate(
                loaded,
                candidate,
                pool,
                distribution,
                leakage,
                reference,
                source_config.model_id,
                source_config.revision,
                generation,
                run_id,
            )
            predictions.append(prediction)
            _append_progress(progress_path, prediction)
        manifest = _teacher_manifest(
            run_id,
            phase,
            "COMPLETED",
            pool,
            distribution,
            leakage,
            reference,
            predictions,
            resumed_from_run_id,
            created_at,
            time.perf_counter() - started,
        )
        destination = _finalize(artifact_root / "teacher-runs", manifest, predictions)
    except BaseException:
        manifest = _teacher_manifest(
            run_id,
            phase,
            "FAILED",
            pool,
            distribution,
            leakage,
            reference,
            predictions,
            resumed_from_run_id,
            created_at,
            time.perf_counter() - started,
        )
        _finalize(artifact_root / "failed", manifest, predictions)
        raise
    finally:
        if loaded is not None:
            unload_model(loaded)
        shutil.rmtree(active, ignore_errors=True)
    return destination


def recover_active(active_run: Path, output_root: Path) -> Path:
    if not active_run.is_dir() or active_run.parent.name != "active":
        raise ValueError("recover requires an active matched run directory")
    run_id = active_run.name
    predictions = (
        _read_predictions(active_run / "predictions.jsonl")
        if (active_run / "predictions.jsonl").is_file()
        else []
    )
    result = write_atomic_bundle(
        output_root,
        run_id,
        {
            "predictions.jsonl": canonical_jsonl_bytes(predictions),
            "recovery.json": canonical_json_bytes(
                {
                    "run_id": run_id,
                    "attempt_id": "distribution_matched_attempt",
                    "status": "FAILED",
                    "reason": "HARD_KILL_RECOVERY",
                }
            )
            + b"\n",
        },
    )
    shutil.rmtree(active_run)
    return result


def find_teacher_run(
    experiment_path: Path, phase: Literal["initial", "expansion"]
) -> tuple[Path, MatchedTeacherRunManifestV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "teacher-runs"
    values: list[tuple[Path, MatchedTeacherRunManifestV0_1]] = []
    for path in sorted(root.glob(f"day3-matched-teacher-{phase}-*")):
        manifest = MatchedTeacherRunManifestV0_1.model_validate_json(
            (path / "manifest.json").read_bytes(), strict=True
        )
        if manifest.status == "COMPLETED":
            values.append((path, manifest))
    if len(values) != 1:
        raise ValueError(f"expected one completed matched {phase} teacher run, found {len(values)}")
    return values[0]


def _infer_candidate(
    loaded: LoadedModel,
    candidate: Any,
    pool: MatchedPoolManifestV0_1,
    distribution: DistributionMatchAuditV0_1,
    leakage: MatchedLeakageAuditV0_1,
    reference: TeacherReferenceV0_1,
    source_model_id: str,
    source_revision: str,
    generation: GenerationConfig,
    run_id: str,
) -> MatchedTeacherPredictionV0_1:
    import torch

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    raw_output = ""
    prompt_hash: str | None = None
    ids_hash: str | None = None
    prompt_tokens: int | None = None
    generated_tokens: int | None = None
    finish: Literal["EOS", "MAX_NEW_TOKENS", "OTHER"] | None = None
    parser = None
    status: Literal["COMPLETED", "FAILED"] = "COMPLETED"
    error_type: Literal["MODEL_ERROR", "OOM", "TIMEOUT"] | None = None
    errors: list[str] = []
    try:
        prompt = render_prompt(loaded.tokenizer, candidate, "0.1.0")
        prompt_hash = sha256_text(prompt)
        encoded = loaded.tokenizer(prompt, add_special_tokens=False, return_tensors="pt")
        prompt_tokens = int(encoded["input_ids"].shape[-1])
        if prompt_tokens > 1024:
            raise ValueError(f"prompt exceeds 1024 tokens: {prompt_tokens}")
        input_values = [int(value) for value in encoded["input_ids"][0].tolist()]
        ids_hash = input_ids_sha256(input_values)
        encoded = {name: value.to(loaded.device) for name, value in encoded.items()}
        torch.manual_seed(generation.seed)
        with torch.inference_mode():
            output = loaded.model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=generation.max_new_tokens,
                pad_token_id=loaded.tokenizer.pad_token_id,
            )
        completion = output[0, prompt_tokens:]
        generated_tokens = int(completion.shape[-1])
        raw_output = loaded.tokenizer.decode(completion, skip_special_tokens=True)
        eos_id = loaded.tokenizer.eos_token_id
        finish = (
            "MAX_NEW_TOKENS"
            if generated_tokens == generation.max_new_tokens
            else "EOS"
            if generated_tokens and eos_id is not None and int(completion[-1]) == int(eos_id)
            else "OTHER"
        )
        parser = parse_action_contract(raw_output)
    except BaseException as exc:
        status = "FAILED"
        message = f"{type(exc).__name__}: {exc}"
        errors.append(message)
        error_type = "OOM" if "out of memory" in message.lower() else "MODEL_ERROR"
    finished_at = datetime.now(UTC)
    payload = {
        "schema_version": "day3-matched-teacher-prediction-v0.1",
        "prediction_id": f"matched-teacher-prediction-{uuid.uuid4().hex[:16]}",
        "run_id": run_id,
        "attempt_id": "distribution_matched_attempt",
        "status": status,
        "error_type": error_type,
        "candidate_id": candidate.candidate_id,
        "candidate_record_sha256": candidate.record_sha256,
        "pool_content_sha256": pool.content_sha256,
        "distribution_audit_sha256": distribution.content_sha256,
        "leakage_audit_sha256": leakage.content_sha256,
        "teacher_reference_sha256": reference.content_sha256,
        "model_id": source_model_id,
        "model_revision": source_revision,
        "adapter_id": reference.adapter_id,
        "resolved_device": loaded.device,
        "resolved_dtype": loaded.dtype,
        "prompt_sha256": prompt_hash,
        "input_ids_sha256": ids_hash,
        "generation": generation.model_dump(mode="json"),
        "prompt_token_count": prompt_tokens,
        "generated_token_count": generated_tokens,
        "finish_condition": finish,
        "raw_output": raw_output,
        "parser_result": parser.model_dump(mode="json") if parser else None,
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "errors": errors,
    }
    return MatchedTeacherPredictionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_EXCLUSIONS),
        },
        strict=True,
    )


def _teacher_manifest(
    run_id: str,
    phase: Literal["initial", "expansion"],
    status: Literal["COMPLETED", "FAILED"],
    pool: MatchedPoolManifestV0_1,
    distribution: DistributionMatchAuditV0_1,
    leakage: MatchedLeakageAuditV0_1,
    reference: TeacherReferenceV0_1,
    predictions: list[MatchedTeacherPredictionV0_1],
    resumed_from_run_id: str | None,
    created_at: datetime,
    duration: float,
) -> MatchedTeacherRunManifestV0_1:
    prediction_bytes = canonical_jsonl_bytes(predictions)
    completed = [item for item in predictions if item.status == "COMPLETED"]
    prompt_tokens = sum(item.prompt_token_count or 0 for item in completed)
    completion_tokens = sum(item.generated_token_count or 0 for item in completed)
    payload = {
        "schema_version": "day3-matched-teacher-run-v0.1",
        "run_id": run_id,
        "attempt_id": "distribution_matched_attempt",
        "phase": phase,
        "status": status,
        "pool_id": pool.pool_id,
        "pool_content_sha256": pool.content_sha256,
        "fingerprint_sha256": pool.fingerprint_sha256,
        "distribution_audit_sha256": distribution.content_sha256,
        "leakage_audit_sha256": leakage.content_sha256,
        "teacher_reference_sha256": reference.content_sha256,
        "candidate_count": pool.candidate_count,
        "attempts": len(predictions),
        "completed_outputs": len(completed),
        "failed_outputs": len(predictions) - len(completed),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "teacher_generation_processed_tokens": prompt_tokens + completion_tokens,
        "duration_seconds": max(0.0, duration),
        "prediction_artifact": artifact_reference(
            "predictions.jsonl",
            prediction_bytes,
            content_sha256=content_sha256([item.content_sha256 for item in predictions]),
        ).model_dump(mode="json"),
        "resumed_from_run_id": resumed_from_run_id,
        "created_at": created_at,
        "finished_at": datetime.now(UTC),
    }
    return MatchedTeacherRunManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )


def _finalize(
    root: Path,
    manifest: MatchedTeacherRunManifestV0_1,
    predictions: list[MatchedTeacherPredictionV0_1],
) -> Path:
    return write_atomic_bundle(
        root,
        manifest.run_id,
        {
            "predictions.jsonl": canonical_jsonl_bytes(predictions),
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def _append_progress(path: Path, prediction: MatchedTeacherPredictionV0_1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(prediction) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_predictions(path: Path) -> list[MatchedTeacherPredictionV0_1]:
    with path.open(encoding="utf-8") as handle:
        return [
            MatchedTeacherPredictionV0_1.model_validate_json(line, strict=True) for line in handle
        ]
