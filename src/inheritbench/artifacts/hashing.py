"""Canonical serialization and SHA-256 helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [json_value(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_jsonl_bytes(records: Iterable[Any], *, id_key: str | None = None) -> bytes:
    values = [json_value(record) for record in records]
    if id_key is not None:
        values.sort(key=lambda item: str(item[id_key]))
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def strip_content_fields(value: Any, excluded_keys: set[str]) -> Any:
    normalized = json_value(value)
    if isinstance(normalized, dict):
        return {
            key: strip_content_fields(item, excluded_keys)
            for key, item in normalized.items()
            if key not in excluded_keys
        }
    if isinstance(normalized, list):
        return [strip_content_fields(item, excluded_keys) for item in normalized]
    return normalized


def content_sha256(value: Any, *, excluded_keys: set[str] | None = None) -> str:
    excluded = excluded_keys or set()
    return sha256_bytes(canonical_json_bytes(strip_content_fields(value, excluded)))


def input_ids_sha256(input_ids: Sequence[int]) -> str:
    payload = b"".join(
        int(token_id).to_bytes(8, byteorder="big", signed=True) for token_id in input_ids
    )
    return sha256_bytes(payload)
