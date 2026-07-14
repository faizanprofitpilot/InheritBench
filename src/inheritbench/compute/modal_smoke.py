"""One bounded Modal L4 CUDA/BF16 environment probe."""

from __future__ import annotations

import os
import platform
import tempfile
import uuid
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_file


class ModalSmokeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["modal-smoke-v0.1"]
    smoke_id: str
    status: Literal["COMPLETED", "BLOCKED"]
    gpu_requested: Literal["L4"]
    attempts: int
    remote_environment: dict[str, Any] | None
    errors: list[str]
    created_at: datetime
    finished_at: datetime
    content_sha256: str


def _remote_probe() -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Modal function did not receive a CUDA device")
    properties = torch.cuda.get_device_properties(0)
    with tempfile.NamedTemporaryFile(prefix="inheritbench-modal-") as handle:
        handle.write(b"writable")
        handle.flush()
        writable = os.path.getsize(handle.name) == 8
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": properties.name,
        "gpu_memory_bytes": properties.total_memory,
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "bf16_supported": torch.cuda.is_bf16_supported(),
        "ephemeral_storage_writable": writable,
    }


def run_modal_smoke(*, gpu: Literal["L4"], output_root: Path) -> Path:
    created_at = datetime.now(UTC)
    smoke_id = f"modal-smoke-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    attempts = 1
    errors: list[str] = []
    remote_environment: dict[str, Any] | None = None
    try:
        import modal

        torch_version = metadata.version("torch").split("+")[0]
        image = modal.Image.debian_slim(python_version="3.11").pip_install(
            f"torch=={torch_version}"
        )
        app = modal.App("inheritbench-day1-modal-smoke")
        remote_function = app.function(image=image, gpu=gpu, timeout=600)(_remote_probe)
        with app.run():
            remote_environment = remote_function.remote()
        status: Literal["COMPLETED", "BLOCKED"] = "COMPLETED"
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        status = "BLOCKED"
    finished_at = datetime.now(UTC)
    payload = {
        "schema_version": "modal-smoke-v0.1",
        "smoke_id": smoke_id,
        "status": status,
        "gpu_requested": gpu,
        "attempts": attempts,
        "remote_environment": remote_environment,
        "errors": errors,
        "created_at": created_at,
        "finished_at": finished_at,
    }
    result = ModalSmokeResult.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload,
                excluded_keys={"smoke_id", "created_at", "finished_at", "content_sha256"},
            ),
        },
        strict=True,
    )
    path = output_root / f"{smoke_id}.json"
    write_atomic_file(path, canonical_json_bytes(result) + b"\n")
    return path


def record_blocked_modal_smoke(*, output_root: Path, reason: str) -> Path:
    """Record a pre-invocation policy or approval blocker without contacting Modal."""

    created_at = datetime.now(UTC)
    smoke_id = f"modal-smoke-{created_at:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    payload = {
        "schema_version": "modal-smoke-v0.1",
        "smoke_id": smoke_id,
        "status": "BLOCKED",
        "gpu_requested": "L4",
        "attempts": 0,
        "remote_environment": None,
        "errors": [reason],
        "created_at": created_at,
        "finished_at": datetime.now(UTC),
    }
    result = ModalSmokeResult.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload,
                excluded_keys={"smoke_id", "created_at", "finished_at", "content_sha256"},
            ),
        },
        strict=True,
    )
    path = output_root / f"{smoke_id}.json"
    write_atomic_file(path, canonical_json_bytes(result) + b"\n")
    return path
