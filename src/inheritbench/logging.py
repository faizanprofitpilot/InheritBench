"""Structured stderr logging with conservative secret redaction."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

_SENSITIVE_FRAGMENTS = ("token", "secret", "password", "credential", "api_key")


def _redact_value(value: Any) -> Any:
    if isinstance(value, MutableMapping):
        return {
            key: (
                "[REDACTED]"
                if any(part in str(key).lower() for part in _SENSITIVE_FRAGMENTS)
                else _redact_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_secrets(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    return cast(MutableMapping[str, Any], _redact_value(event_dict))


def configure_logging(*, json_logs: bool = False, level: str | None = None) -> None:
    resolved_level = (level or os.getenv("INHERITBENCH_LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=resolved_level, force=True)
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer(sort_keys=True)
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, resolved_level, logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
