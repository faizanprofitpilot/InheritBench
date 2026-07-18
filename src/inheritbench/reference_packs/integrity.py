"""Frozen-evidence root digests for product-regression protection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import canonical_json_bytes, sha256_bytes, sha256_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPOSITORY_ROOT / "configs/integrity/frozen_evidence_roots_v0.2.json"
FROZEN_ROOTS = (
    "data/opsroute/v0.1.0",
    "artifacts/day1",
    "artifacts/inspections",
    "artifacts/runs",
    "artifacts/replays",
    "artifacts/blocker-resolution",
    "artifacts/day2",
    "artifacts/day3",
    "artifacts/day3-matched",
    "artifacts/phase3b",
    "artifacts/phase4",
    "artifacts/phase5",
    "artifacts/showcase",
    "adapters/day2/source_adapted_full-8242bcea6f327545",
    "adapters/day2/target_full_retrain-fd1966615c845dab",
    "adapters/day2/target_limited_retrain_10pct-c2e5ec18f58ba342",
    "adapters/phase3b/target_hybrid_anchored_distillation_10-7461072c83b4dcde",
)


def build_frozen_root_manifest() -> dict[str, Any]:
    roots: dict[str, Any] = {}
    for relative in FROZEN_ROOTS:
        root = REPOSITORY_ROOT / relative
        files: list[dict[str, str | int]] = [
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != ".DS_Store"
        ]
        roots[relative] = {
            "file_count": len(files),
            "bytes": sum(item["bytes"] for item in files if isinstance(item["bytes"], int)),
            "root_sha256": sha256_bytes(canonical_json_bytes(files)),
        }
    payload = {
        "schema_version": "inheritbench.frozen-evidence-roots.v0.2",
        "roots": roots,
    }
    payload["content_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def verify_frozen_root_manifest(
    path: Path = BASELINE_PATH,
) -> dict[str, Any]:
    expected = json.loads(path.read_text(encoding="utf-8"))
    actual = build_frozen_root_manifest()
    if expected != actual:
        raise ValueError("frozen historical evidence root digest mismatch")
    return actual
