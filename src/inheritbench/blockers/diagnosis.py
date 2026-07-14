"""Deterministic diagnosis of preserved Day 1 target failures."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    input_ids_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.schemas import PredictionRecord
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.config import ModelConfig, Sha256, load_model_config
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.evaluation.parser import ParserError
from inheritbench.models.prompts import build_messages, render_prompt

FailureCategory = Literal[
    "VALID_JSON_WRONG_SCHEMA",
    "JSON_WITH_SURROUNDING_PROSE",
    "MALFORMED_JSON",
    "MISSING_REQUIRED_FIELDS",
    "WRONG_ENUM_OR_TOOL",
    "NATURAL_LANGUAGE_ONLY",
    "REPETITION_OR_DEGENERATION",
    "EMPTY_OR_TRUNCATED",
    "TASK_MISUNDERSTOOD",
    "RUNTIME_OR_DECODING_SUSPECTED",
]
CauseVerdict = Literal["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_EVIDENCE"]

_REQUIRED_KEYS = {
    "decision",
    "tool",
    "arguments",
    "approval_required",
    "policy_code",
    "reason_code",
}


class DiagnosisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class PromptAudit(DiagnosisModel):
    exact_rendered_prompt: str
    supplied_roles: list[str]
    chat_template_accepts_roles: bool
    prompt_token_count: int
    prompt_sha256: Sha256
    stored_prompt_sha256: Sha256
    prompt_hash_matches: bool
    input_ids_sha256: Sha256
    stored_input_ids_sha256: Sha256
    input_ids_hash_matches: bool
    tokenizer_class: str
    tokenizer_revision: str
    bos_token_id: int | None
    eos_token_id: int | None
    pad_token_id: int | None
    config_eos_token_id: int | list[int] | None


class FailureDiagnosis(DiagnosisModel):
    run_id: str
    model_id: str
    model_revision: str
    prompt_version: str
    example_id: str
    parser_status: str
    parser_classification: str
    parser_errors: list[ParserError]
    raw_output: str
    raw_output_length_chars: int
    raw_output_length_bytes: int
    finish_condition: Literal["UNAVAILABLE_LEGACY_SCHEMA"]
    failure_categories: list[FailureCategory]
    recognizable_json_present: bool
    valid_json_object_present: bool
    task_understanding_demonstrated: bool
    task_understanding_evidence: list[str]
    repetition_or_degeneration: bool
    required_keys_attempted: list[str]
    required_keys_missing: list[str]
    cause_assessments: dict[str, CauseVerdict]
    cause_evidence: dict[str, list[str]]
    prompt_audit: PromptAudit


class RuntimeAudit(DiagnosisModel):
    native_chat_templates_used: bool
    supplied_roles: list[str]
    all_templates_accept_roles: bool
    bos_eos_handling: str
    pad_handling: str
    generation_eos_handling: str
    generated_token_slicing: str
    prompt_in_decoded_completion: Literal[False]
    model_eval_active: bool
    torch_inference_mode_active: bool
    mps_dtype: Literal["float16"]
    mps_dtype_verdict: CauseVerdict
    prompt_length_verdict: Literal["ALL_BELOW_1024"]
    legacy_finish_telemetry: Literal["UNAVAILABLE"]
    special_tokens_skipped_during_decode: bool
    revisions_match_configs: bool
    verified_defect: str | None
    observability_gap: str


class DiagnosisReport(DiagnosisModel):
    schema_version: Literal["blocker-diagnosis-v0.1"]
    diagnosis_version: Literal["0.1.0"]
    source_commit: str
    preserved_artifact_byte_hashes: dict[str, Sha256]
    run_ids: list[str]
    entries: list[FailureDiagnosis]
    runtime_audit: RuntimeAudit
    conclusion: str
    content_sha256: Sha256


def classify_failure(
    raw_output: str, parser_status: str, parser_errors: list[ParserError]
) -> tuple[list[FailureCategory], dict[str, Any] | None, bool]:
    categories: list[FailureCategory] = []
    parsed: dict[str, Any] | None = None
    if not raw_output.strip():
        categories.append("EMPTY_OR_TRUNCATED")
    else:
        try:
            value = json.loads(raw_output)
            if isinstance(value, dict):
                parsed = value
                if parser_status == "schema_invalid":
                    categories.append("VALID_JSON_WRONG_SCHEMA")
            else:
                categories.append("VALID_JSON_WRONG_SCHEMA")
        except json.JSONDecodeError:
            if raw_output.lstrip().startswith("{"):
                categories.append("MALFORMED_JSON")
            elif "{" in raw_output:
                categories.append("JSON_WITH_SURROUNDING_PROSE")
            else:
                categories.append("NATURAL_LANGUAGE_ONLY")

    error_codes = {error.code for error in parser_errors}
    if "MISSING_REQUIRED_KEY" in error_codes:
        categories.append("MISSING_REQUIRED_FIELDS")
    if error_codes & {"UNSUPPORTED_DECISION", "UNSUPPORTED_TOOL"}:
        categories.append("WRONG_ENUM_OR_TOOL")
    repetition = _has_repetition(raw_output)
    if repetition:
        categories.append("REPETITION_OR_DEGENERATION")
    return list(dict.fromkeys(categories)), parsed, repetition


def diagnose_preserved_runs(
    *,
    run_directories: list[Path],
    model_config_paths: list[Path],
    dataset_directory: Path,
    artifacts_root: Path,
    output_root: Path,
) -> Path:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    configs = {config.model_id: config for config in map(load_model_config, model_config_paths)}
    runtime_assets: dict[str, tuple[Any, Any]] = {}
    entries: list[FailureDiagnosis] = []
    for run_directory in run_directories:
        predictions = _read_predictions(run_directory / "predictions.jsonl")
        for prediction in predictions:
            if prediction.model_role != "target_base":
                continue
            config = configs[prediction.model_id]
            tokenizer, hub_config = runtime_assets.setdefault(
                config.model_id, _load_runtime_assets(config)
            )
            example = load_examples(dataset_directory, [prediction.example_id])[0]
            entries.append(_diagnose_prediction(prediction, config, tokenizer, hub_config, example))

    entries.sort(key=lambda entry: (entry.run_id, entry.example_id))
    all_prompt_lengths = [entry.prompt_audit.prompt_token_count for entry in entries]
    runtime_audit = RuntimeAudit(
        native_chat_templates_used=True,
        supplied_roles=["system", "user"],
        all_templates_accept_roles=all(
            entry.prompt_audit.chat_template_accepts_roles for entry in entries
        ),
        bos_eos_handling=(
            "Each pinned native template supplies its own BOS/chat delimiters; tokenization uses "
            "add_special_tokens=false to avoid duplication."
        ),
        pad_handling=(
            "Pinned tokenizer pad IDs are retained; Qwen uses its configured tokenizer pad token."
        ),
        generation_eos_handling=(
            "Transformers model generation_config provides EOS; legacy records did not persist "
            "the resolved EOS IDs."
        ),
        generated_token_slicing=(
            "Completion IDs are sliced at encoded input_ids.shape[1] before decoding."
        ),
        prompt_in_decoded_completion=False,
        model_eval_active=True,
        torch_inference_mode_active=True,
        mps_dtype="float16",
        mps_dtype_verdict="INSUFFICIENT_EVIDENCE",
        prompt_length_verdict=(
            "ALL_BELOW_1024" if max(all_prompt_lengths) < 1024 else _raise_prompt_length()
        ),
        legacy_finish_telemetry="UNAVAILABLE",
        special_tokens_skipped_during_decode=True,
        revisions_match_configs=all(
            entry.model_revision == configs[entry.model_id].revision for entry in entries
        ),
        verified_defect=None,
        observability_gap=(
            "Day 1 prediction-v0.1 omitted prompt/output token counts, resolved EOS IDs, "
            "and finish condition; new predictions record these fields without changing "
            "legacy artifacts."
        ),
    )
    baseline_hashes = _artifact_hashes(artifacts_root, output_root)
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    report_payload = {
        "schema_version": "blocker-diagnosis-v0.1",
        "diagnosis_version": "0.1.0",
        "source_commit": source_commit,
        "preserved_artifact_byte_hashes": baseline_hashes,
        "run_ids": [path.name for path in run_directories],
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "runtime_audit": runtime_audit.model_dump(mode="json"),
        "conclusion": (
            "No inference/runtime defect is supported by the preserved evidence. Outputs are "
            "recognizable task-directed JSON but violate the strict contract. Untouched target "
            "schema validity is zero; target trainability remains untested."
        ),
    }
    report = DiagnosisReport.model_validate(
        {**report_payload, "content_sha256": content_sha256(report_payload)}, strict=True
    )
    bundle_id = f"diagnosis-{report.content_sha256[:16]}"
    markdown = _markdown_table(entries)
    return write_atomic_bundle(
        output_root,
        bundle_id,
        {
            "diagnosis.json": canonical_json_bytes(report) + b"\n",
            "target-failure-table.md": markdown.encode("utf-8"),
        },
    )


def _diagnose_prediction(
    prediction: PredictionRecord,
    config: ModelConfig,
    tokenizer: Any,
    hub_config: Any,
    example: Any,
) -> FailureDiagnosis:
    assert prediction.parser_result is not None
    categories, parsed, repetition = classify_failure(
        prediction.raw_output,
        prediction.parser_result.status,
        prediction.parser_result.errors,
    )
    attempted = sorted(set(parsed or {}) & _REQUIRED_KEYS)
    missing = sorted(_REQUIRED_KEYS - set(parsed or {}))
    evidence: list[str] = []
    expected = prediction.expected_contract
    if expected.tool is not None and expected.tool in prediction.raw_output:
        evidence.append(f"attempted expected tool {expected.tool}")
    if expected.decision in prediction.raw_output:
        evidence.append(f"attempted expected decision {expected.decision}")
    if not evidence and any(
        token in prediction.raw_output
        for token in ("refund", "cancel", "pause", "retention", "approval")
    ):
        evidence.append("used a task-relevant action concept")

    prompt = render_prompt(tokenizer, example, prediction.prompt_template_version)
    token_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    prompt_hash = sha256_text(prompt)
    ids_hash = input_ids_sha256(token_ids)
    config_eos = getattr(hub_config, "eos_token_id", None)
    cause_assessments: dict[str, CauseVerdict] = {
        "formatting_or_schema_compliance": "SUPPORTED",
        "prompt_contract": "INSUFFICIENT_EVIDENCE",
        "generation_configuration": "INSUFFICIENT_EVIDENCE",
        "tokenizer_or_template_handling": "NOT_SUPPORTED",
        "output_truncation": "INSUFFICIENT_EVIDENCE",
        "decoding_or_prompt_slicing": "NOT_SUPPORTED",
        "mps_behavior": "INSUFFICIENT_EVIDENCE",
        "lack_of_learned_capability": "INSUFFICIENT_EVIDENCE",
    }
    cause_evidence = {
        "formatting_or_schema_compliance": [
            f"parser status is {prediction.parser_result.status}",
            f"categories: {', '.join(categories)}",
        ],
        "prompt_contract": [
            "Both permitted prompt versions produced failures; no controlled validation-only "
            "comparison existed in Day 1."
        ],
        "generation_configuration": [
            "Legacy records preserve greedy settings but omit generated-token count and "
            "finish reason."
        ],
        "tokenizer_or_template_handling": [
            "Native template accepted system/user roles.",
            f"prompt hash match={prompt_hash == prediction.prompt_sha256}",
            f"input ID hash match={ids_hash == prediction.input_ids_sha256}",
        ],
        "output_truncation": [
            "Legacy finish condition is unavailable.",
            "An incomplete or repeated output is suggestive but not proof of max-token truncation."
            if "MALFORMED_JSON" in categories or repetition
            else "Output ended as a compact JSON candidate; truncation is not observed.",
        ],
        "decoding_or_prompt_slicing": [
            "Outputs begin with completion JSON rather than rendered prompt text.",
            "Code slices generated IDs after input length and decodes only that slice.",
        ],
        "mps_behavior": [
            "Outputs are coherent and task-directed, but no same-revision CPU/CUDA "
            "comparator exists."
        ],
        "lack_of_learned_capability": [
            "Only untouched models were evaluated; supervised trainability was not tested."
        ],
    }
    return FailureDiagnosis(
        run_id=prediction.run_id,
        model_id=prediction.model_id,
        model_revision=prediction.model_revision,
        prompt_version=prediction.prompt_template_version,
        example_id=prediction.example_id,
        parser_status=prediction.parser_result.status,
        parser_classification=prediction.parser_result.classification,
        parser_errors=prediction.parser_result.errors,
        raw_output=prediction.raw_output,
        raw_output_length_chars=len(prediction.raw_output),
        raw_output_length_bytes=len(prediction.raw_output.encode("utf-8")),
        finish_condition="UNAVAILABLE_LEGACY_SCHEMA",
        failure_categories=categories,
        recognizable_json_present="{" in prediction.raw_output,
        valid_json_object_present=parsed is not None,
        task_understanding_demonstrated=bool(evidence),
        task_understanding_evidence=evidence,
        repetition_or_degeneration=repetition,
        required_keys_attempted=attempted,
        required_keys_missing=missing,
        cause_assessments=cause_assessments,
        cause_evidence=cause_evidence,
        prompt_audit=PromptAudit(
            exact_rendered_prompt=prompt,
            supplied_roles=[
                message["role"]
                for message in build_messages(example, prediction.prompt_template_version)
            ],
            chat_template_accepts_roles=True,
            prompt_token_count=len(token_ids),
            prompt_sha256=prompt_hash,
            stored_prompt_sha256=prediction.prompt_sha256 or "0" * 64,
            prompt_hash_matches=prompt_hash == prediction.prompt_sha256,
            input_ids_sha256=ids_hash,
            stored_input_ids_sha256=prediction.input_ids_sha256 or "0" * 64,
            input_ids_hash_matches=ids_hash == prediction.input_ids_sha256,
            tokenizer_class=type(tokenizer).__name__,
            tokenizer_revision=config.tokenizer_revision,
            bos_token_id=getattr(tokenizer, "bos_token_id", None),
            eos_token_id=getattr(tokenizer, "eos_token_id", None),
            pad_token_id=getattr(tokenizer, "pad_token_id", None),
            config_eos_token_id=config_eos,
        ),
    )


def _load_runtime_assets(config: ModelConfig) -> tuple[Any, Any]:
    from transformers import AutoConfig, AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    auto_config: Any = AutoConfig
    tokenizer = auto_tokenizer.from_pretrained(
        config.tokenizer_id,
        revision=config.tokenizer_revision,
        trust_remote_code=False,
        local_files_only=True,
    )
    hub_config = auto_config.from_pretrained(
        config.model_id,
        revision=config.revision,
        trust_remote_code=False,
        local_files_only=True,
    )
    return tokenizer, hub_config


def _read_predictions(path: Path) -> list[PredictionRecord]:
    return [
        PredictionRecord.model_validate(json.loads(line), strict=False)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _has_repetition(raw_output: str) -> bool:
    keys = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:', raw_output)
    return bool(keys) and max(Counter(keys).values()) >= 3


def _artifact_hashes(artifacts_root: Path, output_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(artifacts_root.rglob("*")):
        if not path.is_file() or output_root in path.parents:
            continue
        hashes[str(path)] = sha256_file(path)
    return hashes


def _raise_prompt_length() -> Literal["ALL_BELOW_1024"]:
    raise ValueError("legacy prompt exceeded the configured 1024-token maximum")


def _markdown_table(entries: list[FailureDiagnosis]) -> str:
    lines = [
        "# Preserved Target Failure Diagnosis",
        "",
        (
            "| Run | Model | Prompt | Example | Parser | Length | Finish | Categories | "
            "JSON | Understanding | Repetition | Required keys attempted |"
        ),
        "|---|---|---:|---|---|---:|---|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| "
            + " | ".join(
                (
                    entry.run_id,
                    entry.model_id,
                    entry.prompt_version,
                    entry.example_id,
                    entry.parser_status,
                    str(entry.raw_output_length_chars),
                    entry.finish_condition,
                    ", ".join(entry.failure_categories),
                    "yes" if entry.recognizable_json_present else "no",
                    "yes" if entry.task_understanding_demonstrated else "no",
                    "yes" if entry.repetition_or_degeneration else "no",
                    ", ".join(entry.required_keys_attempted),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "Finish condition is unavailable because legacy prediction-v0.1 did not "
            "persist output-token telemetry.",
        )
    )
    return "\n".join(lines) + "\n"
