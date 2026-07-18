"""Declarative structured-output evaluator and safety-rule interpreter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from inheritbench.artifacts.hashing import canonical_json, content_sha256
from inheritbench.capability.json_pointer import pointer_exists, resolve_pointer
from inheritbench.capability.plugins import TrustedEvaluatorPlugin
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityOracleRecord,
    EvaluatorConfig,
    GenericEvaluationResult,
    ParserFinding,
    SafetyFinding,
)

_FENCE = re.compile(r"\A\s*```(?:json)?\s*\n(?P<body>.*)\n```\s*\Z", re.DOTALL | re.IGNORECASE)
_MISSING = object()


def evaluate_output(
    *,
    record: CapabilityInputRecord,
    oracle: CapabilityOracleRecord,
    raw_output: str,
    config: EvaluatorConfig,
    output_schema: dict[str, Any],
    cross_field_schema: dict[str, Any],
    vocabularies: dict[str, set[Any]],
    safety_rules: list[dict[str, Any]],
    trusted_plugin: TrustedEvaluatorPlugin | None = None,
) -> GenericEvaluationResult:
    if trusted_plugin is not None:
        result = trusted_plugin.evaluate(
            record_id=record.record_id,
            raw_output=raw_output,
            model_input=record.payload,
            oracle=oracle.model_dump(mode="json"),
        )
        if result.record_id != record.record_id:
            raise ValueError("trusted evaluator returned the wrong record ID")
        return GenericEvaluationResult.model_validate(result, strict=True)
    strict_candidate = raw_output.strip()
    parsed, strict_findings = _parse_candidate(strict_candidate)
    normalized_candidate: str | None = None
    classification = "UNPARSEABLE"
    findings = strict_findings
    if parsed is not None:
        classification = "STRICT_VALID"
    elif config.whole_output_json_fence:
        match = _FENCE.fullmatch(raw_output)
        if match is not None:
            normalized_candidate = match.group("body").strip()
            parsed, findings = _parse_candidate(normalized_candidate)
            if parsed is not None:
                classification = "NORMALIZED_VALID"

    schema_valid = False
    vocabulary_conformant = False
    cross_field_conformant = False
    if parsed is not None:
        errors = sorted(Draft202012Validator(output_schema).iter_errors(parsed), key=str)
        if errors:
            findings = [
                ParserFinding(code="SCHEMA_INVALID", message=error.message) for error in errors
            ]
        else:
            schema_valid = True
            vocabulary_conformant = not _vocabulary_errors(parsed, config, vocabularies)
            cross_field_conformant = not list(
                Draft202012Validator(cross_field_schema).iter_errors(parsed)
            )

    field_correctness: dict[str, bool] = {}
    evaluation_eligible = (
        schema_valid
        and parsed is not None
        and (cross_field_conformant or not config.strict_requires_cross_field)
    )
    if evaluation_eligible and parsed is not None:
        for rule in config.comparisons:
            predicted = resolve_pointer(parsed, rule.pointer, _MISSING)
            expected = resolve_pointer(oracle.expected, rule.pointer, _MISSING)
            field_correctness[rule.name] = _compare(predicted, expected, rule.mode, rule.tolerance)
    else:
        field_correctness = {rule.name: False for rule in config.comparisons}

    semantic_names = {rule.name for rule in config.comparisons if rule.semantic}
    semantic_match = (
        evaluation_eligible
        and bool(semantic_names)
        and all(field_correctness.get(name, False) for name in semantic_names)
    )
    structural_exact = evaluation_eligible and parsed == oracle.expected
    historical_strict_valid = (
        classification == "STRICT_VALID"
        and schema_valid
        and (cross_field_conformant or not config.strict_requires_cross_field)
    )
    safety_document = {
        "prediction": parsed,
        "expected": oracle.expected,
        "input": record.payload,
        "oracle": oracle.safety_context,
        "metrics": {
            "semantic_match": semantic_match,
            "structural_exact": structural_exact,
            "schema_valid": schema_valid,
        },
    }
    safety_findings = (
        _evaluate_safety_rules(safety_document, safety_rules) if parsed is not None else []
    )
    mean = sum(field_correctness.values()) / len(field_correctness) if field_correctness else 0.0
    payload = {
        "schema_version": "inheritbench.generic-evaluation.v0.2",
        "record_id": record.record_id,
        "raw_output": raw_output,
        "strict_candidate": strict_candidate,
        "normalized_candidate": normalized_candidate,
        "parser_classification": classification,
        "parse_valid": parsed is not None,
        "valid_json": parsed is not None,
        "schema_valid": schema_valid,
        "vocabulary_conformant": vocabulary_conformant,
        "cross_field_conformant": cross_field_conformant,
        "historical_strict_valid": historical_strict_valid,
        "strict_valid": historical_strict_valid,
        "structural_exact": structural_exact,
        "semantic_match": semantic_match,
        "field_correctness": field_correctness,
        "mean_field_correctness": mean,
        "parsed_output": parsed,
        "expected": oracle.expected,
        "parser_findings": findings,
        "safety_findings": safety_findings,
        "coverage": oracle.coverage,
    }
    payload["content_sha256"] = content_sha256(payload)
    return GenericEvaluationResult.model_validate(payload, strict=True)


def load_vocabularies(root: Path, config: EvaluatorConfig) -> dict[str, set[Any]]:
    values: dict[str, set[Any]] = {}
    for pointer, relative in config.controlled_vocabularies.items():
        raw = json.loads((root / relative).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"vocabulary {relative} must contain a JSON list")
        values[pointer] = {_hashable(item) for item in raw}
    return values


def _parse_candidate(candidate: str) -> tuple[dict[str, Any] | None, list[ParserFinding]]:
    if not candidate:
        return None, [ParserFinding(code="INVALID_JSON", message="output is empty")]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, [ParserFinding(code="INVALID_JSON", message=str(exc))]
    if not isinstance(value, dict):
        return None, [ParserFinding(code="ROOT_NOT_OBJECT", message="JSON root must be an object")]
    return value, []


def _vocabulary_errors(
    parsed: dict[str, Any],
    config: EvaluatorConfig,
    vocabularies: dict[str, set[Any]],
) -> list[ParserFinding]:
    findings: list[ParserFinding] = []
    for pointer in config.required_pointers:
        if not pointer_exists(parsed, pointer):
            findings.append(
                ParserFinding(code="SCHEMA_INVALID", message=f"missing required pointer {pointer}")
            )
    for pointer, allowed in vocabularies.items():
        value = resolve_pointer(parsed, pointer, _MISSING)
        if value is _MISSING or _hashable(value) not in allowed:
            findings.append(
                ParserFinding(
                    code="SCHEMA_INVALID",
                    message=f"value at {pointer} is not in the controlled vocabulary",
                )
            )
    return findings


def _compare(predicted: Any, expected: Any, mode: str, tolerance: float | None) -> bool:
    if predicted is _MISSING or expected is _MISSING:
        return False
    if mode in {"exact", "list"}:
        return bool(predicted == expected)
    if mode == "set":
        if not isinstance(predicted, list) or not isinstance(expected, list):
            return False
        return {_hashable(value) for value in predicted} == {_hashable(value) for value in expected}
    if mode == "numeric":
        if isinstance(predicted, bool) or isinstance(expected, bool):
            return False
        if not isinstance(predicted, int | float) or not isinstance(expected, int | float):
            return False
        return abs(float(predicted) - float(expected)) <= (tolerance or 0.0)
    raise ValueError(f"unsupported comparison mode {mode}")


def _hashable(value: Any) -> Any:
    if isinstance(value, dict | list):
        return canonical_json(value)
    return value


def _evaluate_safety_rules(
    document: dict[str, Any], rules: list[dict[str, Any]]
) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    for rule in rules:
        if _eval_ast(rule["when"], document):
            findings.append(
                SafetyFinding(
                    code=str(rule["code"]),
                    severity=cast(
                        Literal["info", "warning", "blocker"],
                        str(rule["severity"]),
                    ),
                    message=str(rule["message"]),
                )
            )
    return findings


def validate_safety_ast(node: Any) -> None:
    if not isinstance(node, dict) or len(node) != 1:
        raise ValueError("safety expression must be a one-key object")
    operator, value = next(iter(node.items()))
    if operator in {"and", "or"}:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{operator} requires a non-empty list")
        for child in value:
            validate_safety_ast(child)
        return
    if operator == "not":
        validate_safety_ast(value)
        return
    if operator in {"exists", "missing"}:
        if not isinstance(value, str) or not value.startswith("/"):
            raise ValueError(f"{operator} requires a JSON Pointer")
        return
    if operator in {"eq", "ne", "in", "not_in", "contains"}:
        if not isinstance(value, dict) or set(value) != {"pointer", "value"}:
            raise ValueError(f"{operator} requires pointer and value")
        if not isinstance(value["pointer"], str) or not value["pointer"].startswith("/"):
            raise ValueError(f"{operator} pointer is invalid")
        expected = value["value"]
        if isinstance(expected, dict):
            if set(expected) != {"pointer"}:
                raise ValueError(f"{operator} value reference must contain only pointer")
            if not isinstance(expected["pointer"], str) or not expected["pointer"].startswith("/"):
                raise ValueError(f"{operator} value reference pointer is invalid")
        return
    raise ValueError(f"unsupported safety operator {operator}")


def _eval_ast(node: dict[str, Any], document: dict[str, Any]) -> bool:
    operator, value = next(iter(node.items()))
    if operator == "and":
        return all(_eval_ast(child, document) for child in value)
    if operator == "or":
        return any(_eval_ast(child, document) for child in value)
    if operator == "not":
        return not _eval_ast(value, document)
    if operator == "exists":
        return pointer_exists(document, value)
    if operator == "missing":
        return not pointer_exists(document, value)
    actual = resolve_pointer(document, value["pointer"], _MISSING)
    expected_spec = value["value"]
    expected = (
        resolve_pointer(document, expected_spec["pointer"], _MISSING)
        if isinstance(expected_spec, dict) and set(expected_spec) == {"pointer"}
        else expected_spec
    )
    if operator == "eq":
        return bool(actual == expected)
    if operator == "ne":
        return bool(actual != expected)
    if operator == "in":
        return actual in expected if isinstance(expected, list) else False
    if operator == "not_in":
        return actual not in expected if isinstance(expected, list) else False
    if operator == "contains":
        return expected in actual if isinstance(actual, list | str | dict) else False
    raise ValueError(operator)
