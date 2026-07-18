"""Immutable stage storage with one mutable active-state pointer."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_bundle, write_atomic_file
from inheritbench.orchestration.schemas import StageManifest, SuccessionPlan


def write_stage(
    run_directory: Path,
    *,
    stage: str,
    sequence: int,
    parent_stage_sha256: str | None,
    status: str,
    payload: dict[str, Any],
    errors: list[str] | None = None,
) -> tuple[Path, StageManifest]:
    body = {
        "schema_version": "inheritbench.succession-stage.v0.2",
        "run_id": run_directory.name,
        "stage": stage,
        "sequence": sequence,
        "parent_stage_sha256": parent_stage_sha256,
        "status": status,
        "payload": payload,
        "errors": errors or [],
    }
    body["content_sha256"] = content_sha256(body)
    manifest = StageManifest.model_validate(body, strict=True)
    directory = write_atomic_bundle(
        run_directory / "stages",
        f"{sequence:02d}-{stage.lower()}",
        {"stage.json": canonical_json_bytes(manifest) + b"\n"},
    )
    write_active_state(run_directory, manifest)
    return directory, manifest


def write_active_state(run_directory: Path, manifest: StageManifest) -> None:
    active_root = run_directory.parent / ".active" / run_directory.name
    active_root.mkdir(parents=True, exist_ok=True)
    path = active_root / "state.json"
    temporary = active_root / ".state.json.tmp"
    temporary.write_bytes(canonical_json_bytes(manifest) + b"\n")
    temporary.replace(path)


def finalize_active(run_directory: Path) -> None:
    shutil.rmtree(run_directory.parent / ".active" / run_directory.name, ignore_errors=True)


def load_plan(run_directory: Path) -> SuccessionPlan:
    return SuccessionPlan.model_validate_json(
        (run_directory / "plan.json").read_text(encoding="utf-8"),
        strict=True,
    )


def latest_stage(run_directory: Path) -> StageManifest | None:
    paths = sorted((run_directory / "stages").glob("*/stage.json"))
    if not paths:
        return None
    return StageManifest.model_validate_json(paths[-1].read_text(encoding="utf-8"), strict=True)


def write_final_file(run_directory: Path, name: str, value: Any) -> Path:
    path = run_directory / name
    write_atomic_file(path, canonical_json_bytes(value) + b"\n")
    return path
