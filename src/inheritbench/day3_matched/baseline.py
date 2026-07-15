"""Immutable historical anchors for the final Day 3 recovery."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_file,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.day3_matched.config import load_experiment_config, resolve
from inheritbench.day3_matched.schemas import (
    HistoricalArtifactExpectation,
    HistoricalBaselineV0_1,
)

_CONTENT_EXCLUSIONS = {"baseline_id", "created_at", "content_sha256"}


def build_baseline(experiment_path: Path) -> HistoricalBaselineV0_1:
    experiment = load_experiment_config(experiment_path)
    original_root = resolve(experiment_path, experiment.original_day3_artifact_root)
    verified: list[HistoricalArtifactExpectation] = []
    for expected in experiment.historical_artifacts:
        path = original_root / expected.relative_path
        if not path.is_file():
            raise FileNotFoundError(f"historical artifact is missing: {path}")
        actual_byte = sha256_file(path)
        if actual_byte != expected.byte_sha256:
            raise ValueError(f"historical artifact byte hash mismatch: {path}")
        if expected.content_sha256 is not None:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("content_sha256") != expected.content_sha256:
                raise ValueError(f"historical artifact content hash mismatch: {path}")
        verified.append(expected)
    tree_sha256 = historical_tree_sha256(original_root)
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "reference_commit": experiment.historical_reference_commit,
            "tree_sha256": tree_sha256,
            "files": verified,
        }
    )
    payload = {
        "schema_version": "day3-matched-historical-baseline-v0.1",
        "baseline_id": f"day3-matched-baseline-{identity[:16]}",
        "attempt_id": "independent_pool_attempt",
        "reference_commit": experiment.historical_reference_commit,
        "files": [item.model_dump(mode="json") for item in verified],
        "original_day3_tree_sha256": tree_sha256,
        "original_candidate_count": 768,
        "original_accepted_count": 59,
        "original_selected_count": 0,
        "original_scientific_status": "SCIENTIFICALLY_FAILED",
        "original_day4_gate": "DAY4_BLOCKED",
        "created_at": created_at,
    }
    return HistoricalBaselineV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_CONTENT_EXCLUSIONS),
        },
        strict=True,
    )


def freeze_baseline(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    baseline = build_baseline(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "historical-baselines"
    destination = root / baseline.baseline_id
    if destination.exists():
        stored = HistoricalBaselineV0_1.model_validate_json(
            (destination / "baseline.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != baseline.content_sha256:
            raise ValueError("existing historical baseline differs")
        return destination
    return write_atomic_bundle(
        root,
        baseline.baseline_id,
        {"baseline.json": canonical_json_bytes(baseline) + b"\n"},
    )


def find_baseline(experiment_path: Path) -> tuple[Path, HistoricalBaselineV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "historical-baselines"
    matches = sorted(root.glob("day3-matched-baseline-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one matched historical baseline, found {len(matches)}")
    baseline = HistoricalBaselineV0_1.model_validate_json(
        (matches[0] / "baseline.json").read_bytes(), strict=True
    )
    rebuilt = build_baseline(experiment_path)
    if rebuilt.content_sha256 != baseline.content_sha256:
        raise ValueError("historical baseline no longer matches immutable evidence")
    return matches[0], baseline


def historical_tree_sha256(root: Path) -> str:
    files = [
        {"relative_path": str(path.relative_to(root)), "byte_sha256": sha256_file(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return content_sha256(files)


def current_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
