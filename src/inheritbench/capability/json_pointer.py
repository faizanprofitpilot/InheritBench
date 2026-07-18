"""Minimal RFC 6901 JSON Pointer support."""

from __future__ import annotations

from typing import Any

_MISSING = object()


def resolve_pointer(document: Any, pointer: str, default: Any = _MISSING) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON Pointer: {pointer!r}")
    current = document
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                raise KeyError(part)
        except (KeyError, IndexError, ValueError):
            if default is not _MISSING:
                return default
            raise KeyError(pointer) from None
    return current


def pointer_exists(document: Any, pointer: str) -> bool:
    return resolve_pointer(document, pointer, _MISSING) is not _MISSING
