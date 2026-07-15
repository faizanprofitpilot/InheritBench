"""Verified Day 2 teacher loading and resumable Day 3 candidate inference."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import time
import urllib.request
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    input_ids_sha256,
    sha256_bytes,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.schemas import GenerationConfig
from inheritbench.artifacts.store import artifact_reference, write_atomic_bundle
from inheritbench.config import load_model_config
from inheritbench.day3.config import load_experiment_config, resolve
from inheritbench.day3.pool import find_pool, load_candidates
from inheritbench.day3.schemas import (
    SyntheticPoolManifestV0_1,
    TeacherAdapterVerificationV0_1,
    TeacherPredictionV0_1,
    TeacherRunManifestV0_1,
)
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.models.loader import LoadedModel, load_model, unload_model
from inheritbench.models.prompts import render_prompt

_ADAPTER_ID = "source_adapted_full-8242bcea6f327545"
_ARCHIVE_SHA256 = "8ee07058b71056bf7119582eb15f9fee4febf20b60f8942efa470be44b84a007"
_RELEASE_VERIFICATION = Path(
    "artifacts/day2/publications/day2-release-verification-5acbafb44fc44722/publication.json"
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


def verify_teacher(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    publication_path = Path.cwd() / _RELEASE_VERIFICATION
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    if publication.get("status") != "VERIFIED" or publication.get("tag") != "day2-v0.1.0":
        raise ValueError("the immutable Day 2 release verification is not valid")
    matching = [item for item in publication["assets"] if item["adapter_id"] == _ADAPTER_ID]
    if len(matching) != 1:
        raise ValueError("the Day 2 source adapter release asset is missing or ambiguous")
    asset = matching[0]
    if asset["archive_sha256"] != _ARCHIVE_SHA256 or not asset["verified"]:
        raise ValueError("the Day 2 source archive verification does not match the frozen hash")

    temporary = Path(tempfile.mkdtemp(prefix="inheritbench-day3-teacher-"))
    archive = temporary / asset["archive_name"]
    try:
        urllib.request.urlretrieve(asset["expected_url"], archive)
        if sha256_file(archive) != _ARCHIVE_SHA256:
            raise ValueError("downloaded teacher archive hash mismatch")
        files = _validated_archive_files(archive, asset["adapter_file_sha256s"])
        adapter_root = resolve(experiment_path, experiment.adapter_root) / "teacher"
        adapter_path = adapter_root / _ADAPTER_ID
        if adapter_path.exists():
            actual = {
                str(path.relative_to(adapter_path)): sha256_file(path)
                for path in sorted(adapter_path.rglob("*"))
                if path.is_file()
            }
            if actual != asset["adapter_file_sha256s"]:
                raise ValueError("existing extracted teacher adapter hash mismatch")
        else:
            write_atomic_bundle(adapter_root, _ADAPTER_ID, files)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    verified_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "adapter_id": _ADAPTER_ID,
            "archive_sha256": _ARCHIVE_SHA256,
            "release_verification": publication["content_sha256"],
        }
    )
    verification_id = f"day3-teacher-verification-{identity[:16]}"
    payload = {
        "schema_version": "teacher-adapter-verification-v0.1",
        "verification_id": verification_id,
        "status": "VERIFIED",
        "adapter_id": _ADAPTER_ID,
        "release_tag": "day2-v0.1.0",
        "release_verification_sha256": publication["content_sha256"],
        "archive_url": asset["expected_url"],
        "archive_sha256": _ARCHIVE_SHA256,
        "adapter_file_sha256s": asset["adapter_file_sha256s"],
        "adapter_relative_path": str(adapter_path.relative_to(Path.cwd())),
        "verified_at": verified_at,
    }
    verification = TeacherAdapterVerificationV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload,
                excluded_keys={"verification_id", "verified_at", "content_sha256"},
            ),
        },
        strict=True,
    )
    output_root = resolve(experiment_path, experiment.artifact_root) / "teacher-verifications"
    destination = output_root / verification_id
    if destination.exists():
        stored = TeacherAdapterVerificationV0_1.model_validate_json(
            (destination / "verification.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != verification.content_sha256:
            raise ValueError("existing teacher verification differs")
        return destination
    return write_atomic_bundle(
        output_root,
        verification_id,
        {"verification.json": canonical_json_bytes(verification) + b"\n"},
    )


def find_teacher_verification(experiment_path: Path) -> tuple[Path, TeacherAdapterVerificationV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "teacher-verifications"
    matches = sorted(root.glob("day3-teacher-verification-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one verified teacher artifact, found {len(matches)}")
    value = TeacherAdapterVerificationV0_1.model_validate_json(
        (matches[0] / "verification.json").read_bytes(), strict=True
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
    pool = SyntheticPoolManifestV0_1.model_validate_json(
        (pool_path / "manifest.json").read_bytes(), strict=True
    )
    candidates = load_candidates(pool_path)
    _, verification = find_teacher_verification(experiment_path)
    previous: list[TeacherPredictionV0_1] = []
    resumed_from_run_id: str | None = None
    if resume_run is not None:
        previous_manifest = TeacherRunManifestV0_1.model_validate_json(
            (resume_run / "manifest.json").read_bytes(), strict=True
        )
        if previous_manifest.status != "FAILED" or previous_manifest.phase != phase:
            raise ValueError("teacher resume requires a failed run for the same phase")
        if previous_manifest.pool_content_sha256 != pool.content_sha256:
            raise ValueError("teacher resume pool hash mismatch")
        if previous_manifest.teacher_verification_sha256 != verification.content_sha256:
            raise ValueError("teacher resume adapter verification mismatch")
        previous = _read_predictions(resume_run / "predictions.jsonl")
        resumed_from_run_id = previous_manifest.run_id
    successful = {item.candidate_id for item in previous if item.status == "COMPLETED"}
    pending = [item for item in candidates if item.candidate_id not in successful]

    created_at = datetime.now(UTC)
    run_id = f"day3-teacher-{phase}-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    artifact_root = resolve(experiment_path, experiment.artifact_root)
    active = artifact_root / "active" / run_id
    active.mkdir(parents=True, exist_ok=False)
    progress_path = active / "predictions.jsonl"
    source_config = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    inference_config = source_config.model_copy(update={"requested_dtype": "float16"})
    generation = GenerationConfig(do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714)
    predictions = list(previous)
    started = time.perf_counter()
    loaded: LoadedModel | None = None
    try:
        loaded = load_model(inference_config, device_override=device)
        from peft import PeftModel

        adapter_path = Path.cwd() / verification.adapter_relative_path
        loaded.model = PeftModel.from_pretrained(loaded.model, adapter_path, is_trainable=False)
        loaded.model.eval()
        for candidate in pending:
            prediction = _infer_candidate(
                loaded=loaded,
                candidate=candidate,
                pool=pool,
                verification=verification,
                source_model_id=source_config.model_id,
                source_revision=source_config.revision,
                generation=generation,
                run_id=run_id,
            )
            predictions.append(prediction)
            _append_progress(progress_path, prediction)
        manifest = _teacher_manifest(
            run_id=run_id,
            phase=phase,
            status="COMPLETED",
            pool=pool,
            verification=verification,
            predictions=predictions,
            resumed_from_run_id=resumed_from_run_id,
            created_at=created_at,
            duration=time.perf_counter() - started,
        )
        destination = _finalize_teacher_run(artifact_root / "teacher-runs", manifest, predictions)
    except BaseException:
        manifest = _teacher_manifest(
            run_id=run_id,
            phase=phase,
            status="FAILED",
            pool=pool,
            verification=verification,
            predictions=predictions,
            resumed_from_run_id=resumed_from_run_id,
            created_at=created_at,
            duration=time.perf_counter() - started,
        )
        _finalize_teacher_run(artifact_root / "failed", manifest, predictions)
        raise
    finally:
        if loaded is not None:
            unload_model(loaded)
        shutil.rmtree(active, ignore_errors=True)
    return destination


def recover_active(active_run: Path, output_root: Path) -> Path:
    if not active_run.is_dir() or active_run.parent.name != "active":
        raise ValueError("recover requires an active Day 3 run directory")
    run_id = active_run.name
    destination = output_root / run_id
    if destination.exists():
        raise FileExistsError(f"failed recovery already exists: {destination}")
    predictions = (
        _read_predictions(active_run / "predictions.jsonl")
        if (active_run / "predictions.jsonl").is_file()
        else []
    )
    payload = canonical_jsonl_bytes(predictions)
    result = write_atomic_bundle(
        output_root,
        run_id,
        {
            "predictions.jsonl": payload,
            "recovery.json": canonical_json_bytes(
                {"run_id": run_id, "status": "FAILED", "reason": "HARD_KILL_RECOVERY"}
            )
            + b"\n",
        },
    )
    shutil.rmtree(active_run)
    return result


def _validated_archive_files(archive: Path, expected: dict[str, str]) -> dict[str, bytes]:
    with zipfile.ZipFile(archive) as handle:
        infos = handle.infolist()
        names = [item.filename for item in infos if not item.is_dir()]
        if set(names) != set(expected) or len(names) != len(expected):
            raise ValueError("teacher archive contains unexpected files")
        files: dict[str, bytes] = {}
        for info in infos:
            if info.is_dir():
                continue
            path = Path(info.filename)
            mode = info.external_attr >> 16
            if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode):
                raise ValueError(f"unsafe teacher archive member: {info.filename}")
            payload = handle.read(info)
            if sha256_bytes(payload) != expected[info.filename]:
                raise ValueError(f"teacher archive member hash mismatch: {info.filename}")
            files[info.filename] = payload
    return files


def _infer_candidate(
    *,
    loaded: LoadedModel,
    candidate: Any,
    pool: SyntheticPoolManifestV0_1,
    verification: TeacherAdapterVerificationV0_1,
    source_model_id: str,
    source_revision: str,
    generation: GenerationConfig,
    run_id: str,
) -> TeacherPredictionV0_1:
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
        eos_ids = loaded.tokenizer.eos_token_id
        finish = (
            "MAX_NEW_TOKENS"
            if generated_tokens == generation.max_new_tokens
            else "EOS"
            if generated_tokens and eos_ids is not None and int(completion[-1]) == int(eos_ids)
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
        "schema_version": "teacher-prediction-v0.1",
        "prediction_id": f"teacher-prediction-{uuid.uuid4().hex[:16]}",
        "run_id": run_id,
        "status": status,
        "error_type": error_type,
        "candidate_id": candidate.candidate_id,
        "candidate_record_sha256": candidate.record_sha256,
        "pool_content_sha256": pool.content_sha256,
        "teacher_verification_sha256": verification.content_sha256,
        "model_id": source_model_id,
        "model_revision": source_revision,
        "adapter_id": verification.adapter_id,
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
    return TeacherPredictionV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PREDICTION_EXCLUSIONS),
        },
        strict=True,
    )


def _teacher_manifest(
    *,
    run_id: str,
    phase: Literal["initial", "expansion"],
    status: Literal["COMPLETED", "FAILED"],
    pool: SyntheticPoolManifestV0_1,
    verification: TeacherAdapterVerificationV0_1,
    predictions: list[TeacherPredictionV0_1],
    resumed_from_run_id: str | None,
    created_at: datetime,
    duration: float,
) -> TeacherRunManifestV0_1:
    prediction_bytes = canonical_jsonl_bytes(predictions)
    reference = artifact_reference(
        "predictions.jsonl",
        prediction_bytes,
        content_sha256=content_sha256([item.content_sha256 for item in predictions]),
    )
    completed = [item for item in predictions if item.status == "COMPLETED"]
    prompt_tokens = sum(item.prompt_token_count or 0 for item in completed)
    completion_tokens = sum(item.generated_token_count or 0 for item in completed)
    finished_at = datetime.now(UTC)
    payload = {
        "schema_version": "teacher-run-v0.1",
        "run_id": run_id,
        "phase": phase,
        "status": status,
        "pool_id": pool.pool_id,
        "pool_content_sha256": pool.content_sha256,
        "teacher_verification_sha256": verification.content_sha256,
        "candidate_count": pool.candidate_count,
        "attempts": len(predictions),
        "completed_outputs": len(completed),
        "failed_outputs": len(predictions) - len(completed),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "teacher_generation_processed_tokens": prompt_tokens + completion_tokens,
        "duration_seconds": duration,
        "prediction_artifact": reference.model_dump(mode="json"),
        "resumed_from_run_id": resumed_from_run_id,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    return TeacherRunManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_RUN_EXCLUSIONS)},
        strict=True,
    )


def _finalize_teacher_run(
    root: Path, manifest: TeacherRunManifestV0_1, predictions: list[TeacherPredictionV0_1]
) -> Path:
    return write_atomic_bundle(
        root,
        manifest.run_id,
        {
            "predictions.jsonl": canonical_jsonl_bytes(predictions),
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def _append_progress(path: Path, prediction: TeacherPredictionV0_1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(prediction) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_predictions(path: Path) -> list[TeacherPredictionV0_1]:
    with path.open(encoding="utf-8") as handle:
        return [TeacherPredictionV0_1.model_validate_json(line, strict=True) for line in handle]
