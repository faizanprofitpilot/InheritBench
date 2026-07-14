"""Strict parser with one whole-output Markdown-fence normalization."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from inheritbench.evaluation.contracts import ActionContract

_WHOLE_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(?P<body>.*)\r?\n```\Z", re.DOTALL)

ParserErrorCode = Literal[
    "INVALID_JSON",
    "ROOT_NOT_OBJECT",
    "MISSING_REQUIRED_KEY",
    "EXTRA_FIELD",
    "UNSUPPORTED_DECISION",
    "UNSUPPORTED_TOOL",
    "INVALID_ARGUMENT_SHAPE",
    "INVALID_FIELD_TYPE",
    "CROSS_FIELD_VIOLATION",
    "PROSE_OR_MULTIPLE_OBJECTS",
]


class ParserError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    code: ParserErrorCode
    path: list[str | int]
    message: str


class ParserResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    parser_version: Literal["0.1.0"]
    raw_output: str
    strict_candidate: str
    normalized_candidate: str | None
    classification: Literal["STRICT_VALID", "NORMALIZED_VALID", "UNPARSEABLE"]
    status: Literal[
        "valid",
        "recoverable_formatting_wrapper",
        "invalid_json",
        "schema_invalid",
    ]
    parsed_object: dict[str, Any] | None
    validated_contract: ActionContract | None
    errors: list[ParserError]


def parse_action_contract(raw_output: str) -> ParserResult:
    strict_candidate = raw_output.strip()
    strict_object, strict_contract, strict_errors, strict_status = _parse_candidate(
        strict_candidate
    )
    if strict_contract is not None:
        return ParserResult(
            parser_version="0.1.0",
            raw_output=raw_output,
            strict_candidate=strict_candidate,
            normalized_candidate=None,
            classification="STRICT_VALID",
            status="valid",
            parsed_object=strict_object,
            validated_contract=strict_contract,
            errors=[],
        )

    fence = _WHOLE_FENCE.fullmatch(strict_candidate)
    if fence is not None:
        normalized_candidate = fence.group("body").strip()
        normalized_object, normalized_contract, normalized_errors, normalized_status = (
            _parse_candidate(normalized_candidate)
        )
        if normalized_contract is not None:
            return ParserResult(
                parser_version="0.1.0",
                raw_output=raw_output,
                strict_candidate=strict_candidate,
                normalized_candidate=normalized_candidate,
                classification="NORMALIZED_VALID",
                status="recoverable_formatting_wrapper",
                parsed_object=normalized_object,
                validated_contract=normalized_contract,
                errors=[],
            )
        return ParserResult(
            parser_version="0.1.0",
            raw_output=raw_output,
            strict_candidate=strict_candidate,
            normalized_candidate=normalized_candidate,
            classification="UNPARSEABLE",
            status=normalized_status,
            parsed_object=normalized_object,
            validated_contract=None,
            errors=normalized_errors,
        )

    return ParserResult(
        parser_version="0.1.0",
        raw_output=raw_output,
        strict_candidate=strict_candidate,
        normalized_candidate=None,
        classification="UNPARSEABLE",
        status=strict_status,
        parsed_object=strict_object,
        validated_contract=None,
        errors=strict_errors,
    )


def _parse_candidate(
    candidate: str,
) -> tuple[
    dict[str, Any] | None,
    ActionContract | None,
    list[ParserError],
    Literal["invalid_json", "schema_invalid"],
]:
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        code: ParserErrorCode = (
            "PROSE_OR_MULTIPLE_OBJECTS"
            if _looks_like_embedded_or_multiple_json(candidate, exc)
            else "INVALID_JSON"
        )
        return (
            None,
            None,
            [ParserError(code=code, path=[], message=str(exc))],
            "invalid_json",
        )
    if not isinstance(value, dict):
        return (
            None,
            None,
            [
                ParserError(
                    code="ROOT_NOT_OBJECT",
                    path=[],
                    message="JSON root must be an object",
                )
            ],
            "schema_invalid",
        )
    try:
        contract = ActionContract.model_validate(value, strict=True)
    except ValidationError as exc:
        return value, None, _validation_errors(exc), "schema_invalid"
    return value, contract, [], "schema_invalid"


def _looks_like_embedded_or_multiple_json(candidate: str, error: json.JSONDecodeError) -> bool:
    stripped = candidate.strip()
    if error.msg == "Extra data":
        return True
    return ("{" in stripped and not stripped.startswith("{")) or (
        "}" in stripped and not stripped.endswith("}")
    )


def _validation_errors(error: ValidationError) -> list[ParserError]:
    mapped: list[ParserError] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        path = [part for part in item["loc"] if isinstance(part, str | int)]
        error_type = str(item["type"])
        code: ParserErrorCode
        if error_type == "missing":
            code = "MISSING_REQUIRED_KEY"
        elif error_type == "extra_forbidden":
            code = "EXTRA_FIELD"
        elif path and path[0] == "decision" and error_type == "literal_error":
            code = "UNSUPPORTED_DECISION"
        elif path and path[0] == "tool" and error_type == "literal_error":
            code = "UNSUPPORTED_TOOL"
        elif path and path[0] == "arguments":
            code = "INVALID_ARGUMENT_SHAPE"
        elif error_type.startswith(("string_", "int_", "bool_", "float_", "dict_")):
            code = "INVALID_FIELD_TYPE"
        else:
            code = "CROSS_FIELD_VIOLATION"
        mapped.append(ParserError(code=code, path=path, message=str(item["msg"])))
    return mapped
