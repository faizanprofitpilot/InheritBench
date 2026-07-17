"""Honest prerequisite checks for the existing phased training workflow."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from typing import Any

import psutil

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import load_model_config
from inheritbench.succession.replay import CAPABILITY_PATH, REPO_ROOT, load_capability_pack
from inheritbench.succession.schemas import (
    SuccessionPreflightCheckV0_1,
    SuccessionPreflightReportV0_1,
)

SOURCE_CONFIG = REPO_ROOT / "configs/models/source.yaml"
TARGET_CONFIG = REPO_ROOT / "configs/models/target.yaml"
PREREGISTRATION = REPO_ROOT / (
    "artifacts/phase3b/preregistrations/phase3b-preregistration-2b54c44c199115a2/attestation.json"
)

PHASED_COMMANDS = [
    "inheritbench phase3b freeze-baseline",
    "inheritbench phase3b freeze-hybrid-selection",
    "inheritbench phase3b freeze-confirmatory-data",
    "inheritbench phase3b audit-confirmatory-leakage",
    "inheritbench phase3b freeze-schedule",
    "inheritbench phase3b attest-preregistration",
    "inheritbench phase3b train --device mps",
    "inheritbench phase3b evaluate --split confirmatory-validation",
    "inheritbench phase3b select-checkpoint",
    "inheritbench phase3b evaluate --split confirmatory-test",
    "inheritbench phase3b evaluate-confirmatory-matrix",
    "inheritbench phase3b replay --kind evaluation --artifact PATH",
    "inheritbench phase3b analyze-failures",
    "inheritbench phase3b compare",
    "inheritbench phase3b finalize-science",
    "inheritbench phase3b package-adapter",
    "inheritbench phase3b verify-release --publication PATH",
]


def _check(
    check_id: str,
    status: str,
    blocking: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> SuccessionPreflightCheckV0_1:
    return SuccessionPreflightCheckV0_1.model_validate(
        {
            "check_id": check_id,
            "status": status,
            "blocking": blocking,
            "message": message,
            "details": details or {},
        },
        strict=True,
    )


def run_full_preflight() -> SuccessionPreflightReportV0_1:
    checks: list[SuccessionPreflightCheckV0_1] = []
    python_ok = sys.version_info[:2] == (3, 11)
    checks.append(
        _check(
            "python",
            "PASS" if python_ok else "FAIL",
            not python_ok,
            f"Python {sys.version.split()[0]} detected; the scientific workflow requires 3.11.x.",
            {"executable": sys.executable},
        )
    )

    required_modules = ["torch", "transformers", "peft", "accelerate", "safetensors"]
    missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
    checks.append(
        _check(
            "model_dependencies",
            "PASS" if not missing else "FAIL",
            bool(missing),
            "Required local training dependencies are available."
            if not missing
            else f"Missing model dependencies: {', '.join(missing)}.",
            {"required": required_modules, "missing": missing},
        )
    )

    source = load_model_config(SOURCE_CONFIG)
    target = load_model_config(TARGET_CONFIG)
    pack = load_capability_pack()
    models_ok = (
        source.revision == pack.source_model.revision
        and target.revision == pack.target_model.revision
        and not source.trust_remote_code
        and not target.trust_remote_code
    )
    checks.append(
        _check(
            "pinned_models",
            "PASS" if models_ok else "FAIL",
            not models_ok,
            "Pinned source and target revisions match the capability pack."
            if models_ok
            else "Pinned model identity differs from the supported capability pack.",
            {"source_revision": source.revision, "target_revision": target.revision},
        )
    )

    accelerator = "not_imported"
    if not missing and importlib.util.find_spec("torch") is not None:
        import torch

        if torch.backends.mps.is_available():
            accelerator = "mps"
        elif torch.cuda.is_available():
            accelerator = "cuda"
        else:
            accelerator = "cpu_only"
    checks.append(
        _check(
            "accelerator",
            "PASS" if accelerator in {"mps", "cuda"} else "WARN",
            False,
            f"Resolved training accelerator: {accelerator}.",
            {"resolved": accelerator},
        )
    )

    free_bytes = shutil.disk_usage(REPO_ROOT).free
    disk_ok = free_bytes >= 20 * 1024**3
    checks.append(
        _check(
            "disk",
            "PASS" if disk_ok else "FAIL",
            not disk_ok,
            f"Free repository-volume storage: {free_bytes / 1024**3:.1f} GiB.",
            {"free_bytes": free_bytes, "required_bytes": 20 * 1024**3},
        )
    )

    data_paths = [
        REPO_ROOT / "data/opsroute/v0.1.0/train.jsonl",
        REPO_ROOT / "configs/tasks/opsroute.yaml",
        CAPABILITY_PATH,
    ]
    missing_data = [str(path.relative_to(REPO_ROOT)) for path in data_paths if not path.is_file()]
    checks.append(
        _check(
            "capability_data",
            "PASS" if not missing_data else "FAIL",
            bool(missing_data),
            "Frozen OpsRoute capability inputs are present."
            if not missing_data
            else "Required capability inputs are missing.",
            {"missing": missing_data},
        )
    )

    preregistered = PREREGISTRATION.is_file()
    checks.append(
        _check(
            "preregistration",
            "PASS" if preregistered else "FAIL",
            not preregistered,
            "The published Phase 3B workflow has an immutable preregistration attestation."
            if preregistered
            else "The required Phase 3B preregistration attestation is missing.",
            {"path": str(PREREGISTRATION.relative_to(REPO_ROOT))},
        )
    )

    memory = psutil.virtual_memory().total
    checks.append(
        _check(
            "memory",
            "PASS" if memory >= 16 * 1024**3 else "WARN",
            False,
            f"System memory: {memory / 1024**3:.1f} GiB.",
            {"total_bytes": memory},
        )
    )

    blocking_failure = any(item.blocking and item.status == "FAIL" for item in checks)
    payload = {
        "schema_version": "succession-preflight-v0.1",
        "case_id": "opsroute-qwen-olmo",
        "mode": "full",
        "status": "FAILED" if blocking_failure else "FULL_WORKFLOW_PREFLIGHT_READY",
        "checks": [item.model_dump(mode="json") for item in checks],
        "phased_commands": PHASED_COMMANDS,
    }
    return SuccessionPreflightReportV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )
