"""Shared deterministic pack-writing helpers outside the generic engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from inheritbench.artifacts.hashing import (
    canonical_json,
    canonical_jsonl_bytes,
    content_sha256,
    sha256_bytes,
    sha256_text,
)
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    CapabilityOracleRecord,
)


def input_record(
    *,
    record_id: str,
    surface: str,
    group: str,
    payload: dict[str, Any],
    messages: list[dict[str, str]],
    coverage: dict[str, str | int | bool],
    semantic_signature: str,
    source_record_sha256: str,
) -> CapabilityInputRecord:
    body = {
        "schema_version": "inheritbench.capability-input.v0.2",
        "record_id": record_id,
        "surface": surface,
        "group": group,
        "payload": payload,
        "messages": messages,
        "coverage": coverage,
        "semantic_signature": semantic_signature,
        "source_record_sha256": source_record_sha256,
    }
    body["content_sha256"] = content_sha256(body)
    return CapabilityInputRecord.model_validate(body, strict=True)


def oracle_record(
    record: CapabilityInputRecord,
    expected: dict[str, Any],
    *,
    safety_context: dict[str, Any],
) -> CapabilityOracleRecord:
    body = {
        "schema_version": "inheritbench.capability-oracle.v0.2",
        "record_id": record.record_id,
        "input_content_sha256": record.content_sha256,
        "expected": expected,
        "safety_context": safety_context,
        "coverage": record.coverage,
    }
    body["content_sha256"] = content_sha256(body)
    return CapabilityOracleRecord.model_validate(body, strict=True)


def labeled_record(
    record: CapabilityInputRecord,
    expected: dict[str, Any],
    origin: str,
) -> CapabilityLabeledRecord:
    label = canonical_json(expected)
    body = {
        "schema_version": "inheritbench.capability-labeled-record.v0.2",
        "record_id": record.record_id,
        "input_record": record,
        "assistant_label": label,
        "label_origin": origin,
        "assistant_label_sha256": sha256_text(label),
    }
    body["content_sha256"] = content_sha256(body)
    return CapabilityLabeledRecord.model_validate(body, strict=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def write_jsonl(path: Path, records: list[Any], *, id_key: str = "record_id") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_jsonl_bytes(records, id_key=id_key))


def semantic_hash(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode())
