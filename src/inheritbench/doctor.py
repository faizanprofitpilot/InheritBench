"""Actionable environment and pinned-config diagnostics."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

import psutil
from pydantic import BaseModel, ConfigDict

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.config import ModelConfig, load_model_config, load_task_config


class DoctorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DoctorCheck(DoctorModel):
    id: str
    status: Literal["PASS", "WARN", "FAIL"]
    blocking: bool
    message: str
    details: dict[str, Any]
    remediation: str | None


class DoctorEnvironment(DoctorModel):
    python: dict[str, str]
    packages: dict[str, str]
    os: dict[str, str]
    cpu: dict[str, Any]
    ram: dict[str, Any]
    accelerators: dict[str, Any]
    disk: dict[str, Any]
    git: dict[str, Any]
    fingerprint_sha256: str


class DoctorResult(DoctorModel):
    schema_version: Literal["doctor-v0.1"]
    overall: Literal["PASS", "WARN", "FAIL"]
    checks: list[DoctorCheck]
    environment: DoctorEnvironment


def run_doctor(
    *,
    source_path: Path,
    target_path: Path,
    task_path: Path,
    check_hub: bool,
    profile: Literal["local", "modal"],
    artifact_root: Path = Path("artifacts"),
) -> DoctorResult:
    source = load_model_config(source_path)
    target = load_model_config(target_path)
    task = load_task_config(task_path)
    checks: list[DoctorCheck] = []

    python_ok = sys.version_info[:2] == (3, 11)
    checks.append(
        _check(
            "python.version",
            python_ok,
            blocking=True,
            message=f"running CPython {platform.python_version()}",
            remediation="Run commands through uv with Python 3.11.15.",
        )
    )
    in_environment = sys.prefix != sys.base_prefix
    checks.append(
        _check(
            "python.project_environment",
            in_environment,
            blocking=True,
            message=f"project environment prefix is {sys.prefix}",
            remediation="Run uv sync, then use uv run inheritbench.",
        )
    )

    required_packages = {
        "pydantic": "pydantic",
        "pydantic-settings": "pydantic_settings",
        "PyYAML": "yaml",
        "typer": "typer",
        "rich": "rich",
        "structlog": "structlog",
        "psutil": "psutil",
        "torch": "torch",
        "transformers": "transformers",
        "accelerate": "accelerate",
        "huggingface-hub": "huggingface_hub",
        "safetensors": "safetensors",
    }
    package_versions: dict[str, str] = {}
    for distribution, module in required_packages.items():
        available = importlib.util.find_spec(module) is not None
        version = _distribution_version(distribution)
        if available:
            package_versions[distribution] = version
        checks.append(
            _check(
                f"package.{distribution}",
                available,
                blocking=True,
                message=f"{distribution} {version if available else 'is unavailable'}",
                remediation="Run uv sync --extra model --extra modal --group dev.",
            )
        )

    accelerator_details: dict[str, Any] = {"mps_available": False, "cuda_available": False}
    if importlib.util.find_spec("torch") is not None:
        import torch

        accelerator_details = {
            "torch_version": torch.__version__,
            "mps_built": torch.backends.mps.is_built(),
            "mps_available": torch.backends.mps.is_available(),
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "cuda_device_count": torch.cuda.device_count(),
        }
        accelerator_available = bool(
            accelerator_details["mps_available"] or accelerator_details["cuda_available"]
        )
        checks.append(
            DoctorCheck(
                id="accelerator.local",
                status="PASS" if accelerator_available else "WARN",
                blocking=False,
                message=(
                    "local accelerator is available"
                    if accelerator_available
                    else "no local MPS/CUDA accelerator is available"
                ),
                details=accelerator_details,
                remediation=(
                    None
                    if accelerator_available
                    else "Use CPU only for tests and the bounded Modal path for model smoke runs."
                ),
            )
        )

    disk_usage = shutil.disk_usage(Path.cwd())
    free_gib = disk_usage.free / 1024**3
    checks.append(
        _check(
            "disk.free",
            free_gib >= 20,
            blocking=True,
            message=f"{free_gib:.1f} GiB free",
            remediation="Free at least 20 GiB before downloading model weights.",
            details={"free_gib": free_gib},
        )
    )
    artifact_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=artifact_root, prefix=".doctor-", delete=True):
            writable = True
    except OSError:
        writable = False
    checks.append(
        _check(
            "artifacts.writable",
            writable,
            blocking=True,
            message=(
                f"artifact root {artifact_root} is writable"
                if writable
                else "artifact root is not writable"
            ),
            remediation="Grant write access to the project artifact directory.",
        )
    )

    checks.extend(_model_config_checks(source, "source"))
    checks.extend(_model_config_checks(target, "target"))
    checks.append(
        DoctorCheck(
            id="config.task",
            status="PASS",
            blocking=True,
            message=f"validated {task.task_id} {task.task_version}",
            details={"seed": task.seed, "families": task.families},
            remediation=None,
        )
    )

    if check_hub:
        checks.extend(_hub_checks(source, "source"))
        checks.extend(_hub_checks(target, "target"))

    modal_installed = importlib.util.find_spec("modal") is not None
    modal_configured = Path.home().joinpath(".modal.toml").exists() or bool(
        os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET")
    )
    modal_ok = modal_installed and modal_configured
    modal_blocking = profile == "modal"
    checks.append(
        DoctorCheck(
            id="modal.profile",
            status="PASS" if modal_ok else "FAIL" if modal_blocking else "WARN",
            blocking=modal_blocking,
            message=(
                "Modal package and credential profile are available"
                if modal_ok
                else "Modal package or credential profile is unavailable"
            ),
            details={"package_available": modal_installed, "profile_configured": modal_configured},
            remediation=(
                None if modal_ok else "Install the modal extra and configure a Modal profile."
            ),
        )
    )

    environment_payload = {
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "packages": package_versions,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "cpu": {"logical": psutil.cpu_count(), "physical": psutil.cpu_count(logical=False)},
        "ram": {"total_bytes": psutil.virtual_memory().total},
        "accelerators": accelerator_details,
        "disk": {"total_bytes": disk_usage.total, "free_bytes": disk_usage.free},
        "git": _git_state(),
    }
    environment = DoctorEnvironment.model_validate(
        {**environment_payload, "fingerprint_sha256": content_sha256(environment_payload)},
        strict=True,
    )
    overall = aggregate_status(checks)
    return DoctorResult(
        schema_version="doctor-v0.1",
        overall=overall,
        checks=checks,
        environment=environment,
    )


def aggregate_status(checks: list[DoctorCheck]) -> Literal["PASS", "WARN", "FAIL"]:
    if any(check.status == "FAIL" and check.blocking for check in checks):
        return "FAIL"
    if any(check.status != "PASS" for check in checks):
        return "WARN"
    return "PASS"


def _check(
    identifier: str,
    passed: bool,
    *,
    blocking: bool,
    message: str,
    remediation: str,
    details: dict[str, Any] | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        id=identifier,
        status="PASS" if passed else "FAIL",
        blocking=blocking,
        message=message,
        details=details or {},
        remediation=None if passed else remediation,
    )


def _model_config_checks(config: ModelConfig, role: str) -> list[DoctorCheck]:
    checks = [
        DoctorCheck(
            id=f"config.{role}",
            status="PASS",
            blocking=True,
            message=f"validated {config.model_id}@{config.revision}",
            details={
                "trust_remote_code": config.trust_remote_code,
                "license": config.license.spdx,
                "access": config.license.access,
            },
            remediation=None,
        )
    ]
    license_ok = config.license.review_status == "reviewed"
    checks.append(
        _check(
            f"license.{role}",
            license_ok,
            blocking=True,
            message=f"license review status is {config.license.review_status}",
            remediation="Complete license review or reject the model.",
        )
    )
    if config.license.access != "public":
        token_available = bool(os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN"))
        checks.append(
            _check(
                f"hub_token.{role}",
                token_available,
                blocking=True,
                message=(
                    "Hugging Face token is available"
                    if token_available
                    else "Hugging Face token is missing"
                ),
                remediation="Set HF_TOKEN outside the repository for gated or private access.",
            )
        )
    return checks


def _hub_checks(config: ModelConfig, role: str) -> list[DoctorCheck]:
    from huggingface_hub import HfApi
    from transformers import AutoConfig, AutoTokenizer

    try:
        info = HfApi().model_info(config.model_id, revision=config.revision)
        model_config = AutoConfig.from_pretrained(
            config.model_id,
            revision=config.revision,
            trust_remote_code=False,
        )
        auto_tokenizer: Any = AutoTokenizer
        tokenizer = auto_tokenizer.from_pretrained(
            config.tokenizer_id,
            revision=config.tokenizer_revision,
            trust_remote_code=False,
        )
    except Exception as exc:
        return [
            DoctorCheck(
                id=f"hub.{role}",
                status="FAIL",
                blocking=True,
                message=f"pinned metadata access failed: {type(exc).__name__}: {exc}",
                details={},
                remediation=(
                    "Verify network access, repository availability, and the pinned revision."
                ),
            )
        ]
    architectures = getattr(model_config, "architectures", [])
    architecture = architectures[0] if architectures else None
    valid = architecture == config.expected_architecture_class and bool(tokenizer.chat_template)
    return [
        DoctorCheck(
            id=f"hub.{role}",
            status="PASS" if valid else "FAIL",
            blocking=True,
            message=f"resolved pinned commit {info.sha} with architecture {architecture}",
            details={
                "resolved_sha": info.sha,
                "architecture_class": architecture,
                "tokenizer_class": type(tokenizer).__name__,
                "chat_template_available": bool(tokenizer.chat_template),
            },
            remediation=(
                None
                if valid
                else "Reject the model if architecture or native chat-template validation fails."
            ),
        )
    ]


def _distribution_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unknown"


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {"commit": commit, "worktree_dirty": bool(status)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "worktree_dirty": None}
