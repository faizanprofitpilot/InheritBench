"""Safe capability-pack loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from inheritbench.artifacts.hashing import content_sha256, sha256_bytes, sha256_text
from inheritbench.capability.evaluator import load_vocabularies, validate_safety_ast
from inheritbench.capability.json_pointer import resolve_pointer
from inheritbench.capability.leakage import duplicate_ids
from inheritbench.capability.plugins import TrustedEvaluatorPlugin, load_trusted_plugin
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    CapabilityOracleRecord,
    CapabilityPackConfig,
    CapabilityValidationReport,
    EvaluatorConfig,
    ValidationFinding,
)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LoadedCapabilityPack:
    root: Path
    config: CapabilityPackConfig
    evaluator: EvaluatorConfig
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    cross_field_schema: dict[str, Any]
    safety_rules: list[dict[str, Any]]
    readiness_rules: dict[str, Any]
    vocabularies: dict[str, set[Any]]
    inputs: dict[str, list[CapabilityInputRecord]]
    oracles: dict[str, list[CapabilityOracleRecord]]
    direct_train: list[CapabilityLabeledRecord]
    anchors: list[CapabilityLabeledRecord]
    file_sha256s: dict[str, str]
    validation: CapabilityValidationReport
    trusted_plugin: TrustedEvaluatorPlugin | None

    def oracle_map(self, surface: str) -> dict[str, CapabilityOracleRecord]:
        return {record.record_id: record for record in self.oracles[surface]}


def load_capability_pack(
    root: Path,
    *,
    allow_fixture: bool = False,
    require_executable: bool = False,
) -> LoadedCapabilityPack:
    root = root.resolve()
    config_path = root / "capability.yaml"
    config = CapabilityPackConfig.model_validate(_yaml(config_path), strict=True)
    if (
        require_executable
        and config.capability.status not in {"READY", "REFERENCE"}
        and not (allow_fixture and config.capability.status == "FIXTURE_ONLY")
    ):
        raise ValueError(f"capability status {config.capability.status} is not executable")
    resolved = {
        name: _resolve(root, relative)
        for name, relative in config.paths.model_dump(mode="json").items()
    }
    input_schema = _json(resolved["input_schema"])
    output_schema = _json(resolved["output_schema"])
    cross_field_schema = _json(resolved["cross_field_schema"])
    Draft202012Validator.check_schema(input_schema)
    Draft202012Validator.check_schema(output_schema)
    Draft202012Validator.check_schema(cross_field_schema)
    evaluator = EvaluatorConfig.model_validate(_yaml(resolved["evaluator"]), strict=True)
    plugin_binding = (
        load_trusted_plugin(evaluator.trusted_plugin)
        if evaluator.trusted_plugin is not None
        else None
    )
    safety_document = _yaml(resolved["safety_rules"])
    if not isinstance(safety_document, dict) or not isinstance(safety_document.get("rules"), list):
        raise ValueError("safety rules file must contain a rules list")
    safety_rules = safety_document["rules"]
    for rule in safety_rules:
        if not isinstance(rule, dict) or set(rule) != {"code", "severity", "message", "when"}:
            raise ValueError("each safety rule must contain code, severity, message and when")
        if rule["severity"] not in {"info", "warning", "blocker"}:
            raise ValueError("invalid safety severity")
        validate_safety_ast(rule["when"])
    readiness_rules = _yaml(resolved["readiness_rules"])
    if not isinstance(readiness_rules, dict):
        raise ValueError("readiness rules must be a mapping")
    _validate_readiness_rules(readiness_rules)
    vocabularies = load_vocabularies(root, evaluator)
    input_names = {
        "source_gate": "source_gate_inputs",
        "transfer_pool": "transfer_pool_inputs",
        "validation": "validation_inputs",
        "confirmatory": "confirmatory_inputs",
        "adversarial": "adversarial_inputs",
    }
    oracle_names = {
        "source_gate": "source_gate_oracle",
        "transfer_pool": "transfer_pool_oracle",
        "validation": "validation_oracle",
        "confirmatory": "confirmatory_oracle",
        "adversarial": "adversarial_oracle",
    }
    inputs = {
        surface: _jsonl(resolved[path_name], CapabilityInputRecord)
        for surface, path_name in input_names.items()
    }
    oracles = {
        surface: _jsonl(resolved[path_name], CapabilityOracleRecord)
        for surface, path_name in oracle_names.items()
    }
    direct_train = _jsonl(resolved["direct_train"], CapabilityLabeledRecord)
    anchors = _jsonl(resolved["anchors"], CapabilityLabeledRecord)
    findings = _validate_records(
        root=root,
        input_schema=input_schema,
        output_schema=output_schema,
        inputs=inputs,
        oracles=oracles,
        direct_train=direct_train,
        anchors=anchors,
        coverage_group_key=config.coverage_group_key,
        vocabularies=vocabularies,
        evaluator=evaluator,
    )
    strategy_ids = [item.strategy_id for item in config.strategies]
    if len(strategy_ids) != len(set(strategy_ids)):
        findings.append(
            _finding(
                "DUPLICATE_STRATEGY_ID",
                "capability.yaml",
                None,
                "strategy IDs must be unique",
                "remove the duplicate strategy",
                "/strategies",
            )
        )
    for profile in config.strategies:
        if profile.teacher_outputs_artifact is not None:
            _resolve(root, profile.teacher_outputs_artifact)
            if profile.teacher_outputs_sha256 is None:
                findings.append(
                    _finding(
                        "TEACHER_OUTPUT_HASH_MISSING",
                        "capability.yaml",
                        None,
                        "frozen teacher outputs require an expected SHA-256",
                        "add teacher_outputs_sha256",
                    )
                )
        if profile.schedule_policy.type == "frozen-record-order-v0.1":
            schedule_path = _resolve(root, profile.schedule_policy.artifact)
            if sha256_bytes(schedule_path.read_bytes()) != profile.schedule_policy.sha256:
                findings.append(
                    _finding(
                        "FROZEN_SCHEDULE_HASH_MISMATCH",
                        profile.schedule_policy.artifact,
                        None,
                        "frozen schedule bytes do not match the declared SHA-256",
                        "restore the declared schedule or update the reference projection",
                    )
                )
    referenced_paths = {
        "capability.yaml": config_path,
        **{config.paths.model_dump(mode="json")[name]: path for name, path in resolved.items()},
    }
    for profile in config.strategies:
        if profile.teacher_outputs_artifact is not None:
            referenced_paths[profile.teacher_outputs_artifact] = _resolve(
                root, profile.teacher_outputs_artifact
            )
        if profile.schedule_policy.type == "frozen-record-order-v0.1":
            referenced_paths[profile.schedule_policy.artifact] = _resolve(
                root, profile.schedule_policy.artifact
            )
    file_sha256s = {
        relative: sha256_bytes(path.read_bytes())
        for relative, path in sorted(referenced_paths.items())
    }
    counts = {
        **{f"{surface}_inputs": len(records) for surface, records in inputs.items()},
        **{f"{surface}_oracles": len(records) for surface, records in oracles.items()},
        "direct_train": len(direct_train),
        "anchors": len(anchors),
    }
    report_payload = {
        "schema_version": "inheritbench.capability-validation.v0.1",
        "capability_id": config.capability.id,
        "capability_version": config.capability.version,
        "status": "FAIL" if any(item.severity == "ERROR" for item in findings) else "PASS",
        "findings": findings,
        "file_sha256s": file_sha256s,
        "record_counts": counts,
    }
    report_payload["content_sha256"] = content_sha256(report_payload)
    report = CapabilityValidationReport.model_validate(report_payload, strict=True)
    if report.status == "FAIL":
        codes = ", ".join(item.code for item in report.findings if item.severity == "ERROR")
        raise ValueError(f"capability-pack validation failed: {codes}")
    return LoadedCapabilityPack(
        root=root,
        config=config,
        evaluator=evaluator,
        input_schema=input_schema,
        output_schema=output_schema,
        cross_field_schema=cross_field_schema,
        safety_rules=safety_rules,
        readiness_rules=readiness_rules,
        vocabularies=vocabularies,
        inputs=inputs,
        oracles=oracles,
        direct_train=direct_train,
        anchors=anchors,
        file_sha256s=file_sha256s,
        validation=report,
        trusted_plugin=None if plugin_binding is None else plugin_binding.plugin,
    )


def _validate_records(
    *,
    root: Path,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    inputs: dict[str, list[CapabilityInputRecord]],
    oracles: dict[str, list[CapabilityOracleRecord]],
    direct_train: list[CapabilityLabeledRecord],
    anchors: list[CapabilityLabeledRecord],
    coverage_group_key: str,
    vocabularies: dict[str, set[Any]],
    evaluator: EvaluatorConfig,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    input_validator = Draft202012Validator(input_schema)
    output_validator = Draft202012Validator(output_schema)
    for surface, records in inputs.items():
        for duplicate in duplicate_ids(records):
            findings.append(
                _finding(
                    "DUPLICATE_RECORD_ID",
                    f"data/{surface}.inputs.jsonl",
                    duplicate,
                    "record ID occurs more than once",
                    "make record IDs unique",
                )
            )
        oracle_map = {item.record_id: item for item in oracles[surface]}
        if len(oracle_map) != len(oracles[surface]):
            findings.append(
                _finding(
                    "DUPLICATE_ORACLE_ID",
                    f"oracles/{surface}.jsonl",
                    None,
                    "oracle record IDs must be unique",
                    "provide exactly one oracle for every input",
                )
            )
        if set(oracle_map) != {item.record_id for item in records}:
            findings.append(
                _finding(
                    "ORACLE_JOIN_MISMATCH",
                    f"oracles/{surface}.jsonl",
                    None,
                    "input and oracle IDs do not match exactly",
                    "provide exactly one oracle for every input",
                )
            )
        for record in records:
            _validate_input_integrity(record, f"data/{surface}.inputs.jsonl", findings)
            if record.coverage.get(coverage_group_key) != record.group:
                findings.append(
                    _finding(
                        "COVERAGE_GROUP_MISMATCH",
                        f"data/{surface}.inputs.jsonl",
                        record.record_id,
                        "coverage group does not match the record group",
                        f"set coverage.{coverage_group_key} to {record.group}",
                        f"/coverage/{coverage_group_key}",
                    )
                )
            for error in input_validator.iter_errors(record.payload):
                findings.append(
                    _finding(
                        "INPUT_SCHEMA_INVALID",
                        f"data/{surface}.inputs.jsonl",
                        record.record_id,
                        error.message,
                        "update the input or schema",
                        "/" + "/".join(str(part) for part in error.path),
                    )
                )
            oracle = oracle_map.get(record.record_id)
            if oracle is None:
                continue
            _validate_oracle_integrity(
                oracle,
                f"oracles/{surface}.jsonl",
                findings,
            )
            if oracle.input_content_sha256 != record.content_sha256:
                findings.append(
                    _finding(
                        "ORACLE_INPUT_HASH_MISMATCH",
                        f"oracles/{surface}.jsonl",
                        record.record_id,
                        "oracle does not reference the exact input bytes",
                        "regenerate the oracle reference",
                    )
                )
            for error in output_validator.iter_errors(oracle.expected):
                findings.append(
                    _finding(
                        "ORACLE_SCHEMA_INVALID",
                        f"oracles/{surface}.jsonl",
                        record.record_id,
                        error.message,
                        "update the expected object or output schema",
                    )
                )
            _validate_controlled_values(
                oracle.expected,
                vocabularies,
                f"oracles/{surface}.jsonl",
                oracle.record_id,
                findings,
            )
    labeled_sets: list[tuple[str, list[CapabilityLabeledRecord]]] = [
        ("direct_train", direct_train),
        ("anchors", anchors),
    ]
    for name, labeled_records in labeled_sets:
        record_ids = [record.record_id for record in labeled_records]
        if len(record_ids) != len(set(record_ids)):
            findings.append(
                _finding(
                    "DUPLICATE_LABELED_RECORD_ID",
                    name,
                    None,
                    "labeled record IDs must be unique",
                    "make labeled record IDs unique",
                )
            )
        for labeled_record_item in labeled_records:
            _validate_labeled_integrity(labeled_record_item, name, findings)
            _validate_input_integrity(labeled_record_item.input_record, name, findings)
            if labeled_record_item.input_record.coverage.get(coverage_group_key) != (
                labeled_record_item.input_record.group
            ):
                findings.append(
                    _finding(
                        "COVERAGE_GROUP_MISMATCH",
                        name,
                        labeled_record_item.record_id,
                        "coverage group does not match the labeled record group",
                        "make the coverage and record groups identical",
                    )
                )
            for error in input_validator.iter_errors(labeled_record_item.input_record.payload):
                findings.append(
                    _finding(
                        "TRAINING_INPUT_SCHEMA_INVALID",
                        name,
                        labeled_record_item.record_id,
                        error.message,
                        "make the training input conform to input.schema.json",
                    )
                )
            try:
                label = json.loads(labeled_record_item.assistant_label)
            except json.JSONDecodeError as exc:
                findings.append(
                    _finding(
                        "TRAINING_LABEL_INVALID_JSON",
                        str(root / name),
                        labeled_record_item.record_id,
                        str(exc),
                        "use a strict JSON assistant label",
                    )
                )
                continue
            for error in output_validator.iter_errors(label):
                findings.append(
                    _finding(
                        "TRAINING_LABEL_SCHEMA_INVALID",
                        str(root / name),
                        labeled_record_item.record_id,
                        error.message,
                        "make the assistant label conform to output.schema.json",
                    )
                )
            _validate_controlled_values(
                label,
                vocabularies,
                name,
                labeled_record_item.record_id,
                findings,
            )
    comparison_names = [item.name for item in evaluator.comparisons]
    if len(comparison_names) != len(set(comparison_names)):
        findings.append(
            _finding(
                "DUPLICATE_COMPARISON_NAME",
                "evaluator.yaml",
                None,
                "comparison names must be unique",
                "rename or remove duplicate comparisons",
                "/comparisons",
            )
        )
    return findings


def validate_added_anchors(
    pack: LoadedCapabilityPack,
    records: list[CapabilityLabeledRecord],
) -> None:
    findings: list[ValidationFinding] = []
    _validate_records(
        root=pack.root,
        input_schema=pack.input_schema,
        output_schema=pack.output_schema,
        inputs={},
        oracles={},
        direct_train=[],
        anchors=records,
        coverage_group_key=pack.config.coverage_group_key,
        vocabularies=pack.vocabularies,
        evaluator=pack.evaluator,
    )
    evaluation_ids = {record.record_id for surface in pack.inputs.values() for record in surface}
    evaluation_hashes = {
        record.content_sha256 for surface in pack.inputs.values() for record in surface
    }
    evaluation_semantic = {
        record.semantic_signature for surface in pack.inputs.values() for record in surface
    }
    for record in records:
        if record.label_origin != "anchor":
            findings.append(
                _finding(
                    "ANCHOR_ORIGIN_INVALID",
                    "anchor intervention",
                    record.record_id,
                    "added records must declare label_origin=anchor",
                    "set label_origin to anchor",
                )
            )
        if record.input_record.surface != "anchor":
            findings.append(
                _finding(
                    "ANCHOR_SURFACE_INVALID",
                    "anchor intervention",
                    record.record_id,
                    "anchor inputs must use the dedicated anchor surface",
                    "set input_record.surface to anchor",
                )
            )
        if (
            record.record_id in evaluation_ids
            or record.input_record.content_sha256 in evaluation_hashes
            or record.input_record.semantic_signature in evaluation_semantic
        ):
            findings.append(
                _finding(
                    "ANCHOR_EVALUATION_LEAKAGE",
                    "anchor intervention",
                    record.record_id,
                    "anchor collides with an evaluation input",
                    "provide a distinct authorized training record",
                )
            )
    errors = [item.code for item in findings if item.severity == "ERROR"]
    if errors:
        raise ValueError(f"anchor validation failed: {', '.join(errors)}")


def _validate_input_integrity(
    record: CapabilityInputRecord,
    file: str,
    findings: list[ValidationFinding],
) -> None:
    body = record.model_dump(mode="json")
    stored = body.pop("content_sha256")
    if content_sha256(body) != stored:
        findings.append(
            _finding(
                "INPUT_CONTENT_HASH_MISMATCH",
                file,
                record.record_id,
                "input content hash does not match the record",
                "regenerate the input record",
            )
        )


def _validate_oracle_integrity(
    record: CapabilityOracleRecord,
    file: str,
    findings: list[ValidationFinding],
) -> None:
    body = record.model_dump(mode="json")
    stored = body.pop("content_sha256")
    if content_sha256(body) != stored:
        findings.append(
            _finding(
                "ORACLE_CONTENT_HASH_MISMATCH",
                file,
                record.record_id,
                "oracle content hash does not match the record",
                "regenerate the oracle record",
            )
        )


def _validate_labeled_integrity(
    record: CapabilityLabeledRecord,
    file: str,
    findings: list[ValidationFinding],
) -> None:
    if sha256_text(record.assistant_label) != record.assistant_label_sha256:
        findings.append(
            _finding(
                "ASSISTANT_LABEL_HASH_MISMATCH",
                file,
                record.record_id,
                "assistant label hash does not match the exact label bytes",
                "regenerate the labeled record",
            )
        )
    body = record.model_dump(mode="json")
    stored = body.pop("content_sha256")
    if content_sha256(body) != stored:
        findings.append(
            _finding(
                "LABELED_CONTENT_HASH_MISMATCH",
                file,
                record.record_id,
                "labeled record content hash does not match the record",
                "regenerate the labeled record",
            )
        )


def _validate_controlled_values(
    value: dict[str, Any],
    vocabularies: dict[str, set[Any]],
    file: str,
    record_id: str,
    findings: list[ValidationFinding],
) -> None:
    missing = object()
    for pointer, allowed in vocabularies.items():
        actual = resolve_pointer(value, pointer, missing)
        if actual is missing or actual not in allowed:
            findings.append(
                _finding(
                    "CONTROLLED_VOCABULARY_INVALID",
                    file,
                    record_id,
                    f"value at {pointer} is outside the controlled vocabulary",
                    "use a declared vocabulary value",
                    pointer,
                )
            )


def _validate_readiness_rules(document: dict[str, Any]) -> None:
    if not isinstance(document.get("version"), str) or not document["version"]:
        raise ValueError("readiness rules require a version")
    required = {
        "minimum_semantic_rate",
        "minimum_strict_rate",
        "minimum_group_semantic_rate",
        "maximum_blocker_safety_findings",
    }
    for surface in ("source_gate", "clean", "adversarial"):
        rules = document.get(surface)
        if not isinstance(rules, dict) or set(rules) != required:
            raise ValueError(f"readiness {surface} rules must contain {sorted(required)}")
        for name in required - {"maximum_blocker_safety_findings"}:
            value = rules[name]
            if (
                not isinstance(value, int | float)
                or isinstance(value, bool)
                or not 0 <= float(value) <= 1
            ):
                raise ValueError(f"readiness {surface}.{name} must be between zero and one")
        maximum = rules["maximum_blocker_safety_findings"]
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
            raise ValueError(
                f"readiness {surface}.maximum_blocker_safety_findings must be nonnegative"
            )


def _finding(
    code: str,
    file: str,
    record_id: str | None,
    message: str,
    remediation: str,
    pointer: str = "",
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity="ERROR",
        file=file,
        pointer=pointer,
        record_id=record_id,
        message=message,
        remediation=remediation,
    )


def _resolve(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes capability root: {relative}")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"unable to load YAML {path}: {exc}") from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _jsonl(path: Path, schema: type[T]) -> list[T]:
    records: list[T] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(schema.model_validate_json(line, strict=True))
        except ValidationError as exc:
            raise ValueError(f"invalid {schema.__name__} at {path}:{line_number}: {exc}") from exc
    return records
