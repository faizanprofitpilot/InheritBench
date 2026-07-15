"""Deterministic adapter packaging and release verification."""

from __future__ import annotations

import io
import subprocess
import urllib.request
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, sha256_bytes
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.day2.config import load_experiment_config
from inheritbench.day2.schemas import (
    AdapterPublicationManifestV0_1,
    CheckpointDecisionV0_1,
    PublishedAsset,
)

_TAG = "day2-v0.1.0"
_REPOSITORY = "faizanprofitpilot/InheritBench"
_METHODS = (
    "source_adapted_full",
    "target_full_retrain",
    "target_limited_retrain_10pct",
)


def package_adapters(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = _resolve(experiment_path, experiment.artifact_root)
    commit = _git_commit()
    files: dict[str, bytes] = {}
    assets: list[PublishedAsset] = []
    checksum_lines: list[str] = []
    for method_id in _METHODS:
        decision = _single_decision(root, method_id)
        if decision.selected_adapter is None or not decision.selected_adapter.verified:
            raise ValueError(f"{method_id} has no verified selected adapter")
        adapter = Path.cwd() / decision.selected_adapter.relative_path
        archive_name = f"{decision.selected_adapter.adapter_id}.zip"
        archive = _deterministic_zip(adapter)
        digest = sha256_bytes(archive)
        files[archive_name] = archive
        checksum_lines.append(f"{digest}  {archive_name}\n")
        assets.append(
            PublishedAsset(
                adapter_id=decision.selected_adapter.adapter_id,
                method_id=method_id,  # type: ignore[arg-type]
                archive_name=archive_name,
                expected_url=(
                    f"https://github.com/{_REPOSITORY}/releases/download/{_TAG}/{archive_name}"
                ),
                archive_sha256=digest,
                archive_bytes=len(archive),
                adapter_file_sha256s=decision.selected_adapter.file_sha256s,
                downloaded_sha256=None,
                verified=False,
            )
        )
    checksums = "".join(sorted(checksum_lines)).encode()
    files["SHA256SUMS"] = checksums
    created_at = datetime.now(UTC)
    publication_id = f"day2-publication-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "adapter-publication-v0.1",
        "publication_id": publication_id,
        "status": "PACKAGED",
        "repository": _REPOSITORY,
        "tag": _TAG,
        "commit": commit,
        "assets": [item.model_dump(mode="json") for item in assets],
        "sha256sums_sha256": sha256_bytes(checksums),
        "verified_at": None,
        "created_at": created_at,
    }
    manifest = AdapterPublicationManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload, excluded_keys={"publication_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    files["publication.json"] = canonical_json_bytes(manifest) + b"\n"
    return write_atomic_bundle(root / "publications", publication_id, files)


def verify_release(publication_directory: Path, output_root: Path) -> Path:
    source = AdapterPublicationManifestV0_1.model_validate_json(
        (publication_directory / "publication.json").read_bytes(), strict=True
    )
    assets: list[PublishedAsset] = []
    for asset in source.assets:
        with urllib.request.urlopen(asset.expected_url, timeout=120) as response:
            payload = response.read()
        actual = sha256_bytes(payload)
        if actual != asset.archive_sha256:
            raise ValueError(f"release asset hash mismatch: {asset.archive_name}")
        assets.append(asset.model_copy(update={"downloaded_sha256": actual, "verified": True}))
    verified_at = datetime.now(UTC)
    publication_id = f"day2-release-verification-{uuid.uuid4().hex[:16]}"
    payload = {
        **source.model_dump(mode="python"),
        "publication_id": publication_id,
        "status": "VERIFIED",
        "assets": [item.model_dump(mode="json") for item in assets],
        "verified_at": verified_at,
        "created_at": verified_at,
    }
    payload.pop("content_sha256", None)
    verified = AdapterPublicationManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload,
                excluded_keys={"publication_id", "created_at", "verified_at", "content_sha256"},
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        publication_id,
        {"publication.json": canonical_json_bytes(verified) + b"\n"},
    )


def _deterministic_zip(directory: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative = str(path.relative_to(directory))
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return buffer.getvalue()


def _single_decision(root: Path, method_id: str) -> CheckpointDecisionV0_1:
    values = [
        CheckpointDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted((root / "checkpoint-decisions").glob("*/decision.json"))
    ]
    matches = [item for item in values if item.method_id == method_id and item.status == "SELECTED"]
    if len(matches) != 1:
        raise ValueError(f"publication requires one selected adapter for {method_id}")
    return matches[0]


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _resolve(parent_file: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    return direct if direct.exists() or path.parts[0] == "artifacts" else parent_file.parent / path
