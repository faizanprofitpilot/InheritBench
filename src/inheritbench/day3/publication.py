"""Deterministic Day 3 adapter packaging and bounded release verification."""

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
from inheritbench.day2.evaluation import verify_adapter
from inheritbench.day3.config import load_experiment_config, resolve
from inheritbench.day3.evaluation import find_checkpoint_decision
from inheritbench.day3.schemas import (
    Day3PublicationManifestV0_1,
    Day3PublishedAsset,
    Day3ScientificDecisionV0_1,
)

_TAG = "day3-v0.1.0"
_REPOSITORY = "faizanprofitpilot/InheritBench"


def package_adapter(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    scientific = _scientific_decision(root)
    if scientific.scientific_status != "SCIENTIFICALLY_COMPLETED":
        raise ValueError("adapter packaging requires scientific completion")
    _, checkpoint = find_checkpoint_decision(experiment_path)
    if checkpoint.status != "SELECTED" or checkpoint.selected_adapter is None:
        raise ValueError("adapter packaging requires a verified selected checkpoint")
    adapter_path = verify_adapter(checkpoint.selected_adapter, Path.cwd())
    archive_name = f"{checkpoint.selected_adapter.adapter_id}.zip"
    archive = _deterministic_zip(adapter_path)
    archive_sha256 = sha256_bytes(archive)
    checksum = f"{archive_sha256}  {archive_name}\n".encode()
    asset = Day3PublishedAsset(
        adapter_id=checkpoint.selected_adapter.adapter_id,
        archive_name=archive_name,
        expected_url=(f"https://github.com/{_REPOSITORY}/releases/download/{_TAG}/{archive_name}"),
        archive_sha256=archive_sha256,
        archive_bytes=len(archive),
        adapter_file_sha256s=checkpoint.selected_adapter.file_sha256s,
        downloaded_sha256=None,
        verified=False,
    )
    created_at = datetime.now(UTC)
    publication_id = f"day3-publication-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "day3-publication-v0.1",
        "publication_id": publication_id,
        "status": "PACKAGED",
        "repository": _REPOSITORY,
        "tag": _TAG,
        "commit": _git_commit(),
        "scientific_decision_sha256": scientific.content_sha256,
        "asset": asset.model_dump(mode="json"),
        "sha256sums_sha256": sha256_bytes(checksum),
        "attempt": 1,
        "error": None,
        "verified_at": None,
        "created_at": created_at,
    }
    publication = Day3PublicationManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload,
                excluded_keys={"publication_id", "created_at", "content_sha256"},
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        root / "publications",
        publication_id,
        {
            archive_name: archive,
            "SHA256SUMS": checksum,
            "publication.json": canonical_json_bytes(publication) + b"\n",
        },
    )


def verify_release(publication_directory: Path, output_root: Path) -> Path:
    source = Day3PublicationManifestV0_1.model_validate_json(
        (publication_directory / "publication.json").read_bytes(), strict=True
    )
    if source.status != "PACKAGED":
        raise ValueError("release verification requires the immutable packaged artifact")
    prior_failures = _prior_failures(output_root, source.asset.archive_sha256)
    attempt = len(prior_failures) + 1
    if attempt > 2:
        raise ValueError("Day 3 publication permits only one attempt and one identical-byte retry")
    downloaded_sha256 = None
    verified = False
    error = None
    try:
        with urllib.request.urlopen(source.asset.expected_url, timeout=120) as response:
            payload = response.read()
        downloaded_sha256 = sha256_bytes(payload)
        if downloaded_sha256 != source.asset.archive_sha256:
            raise ValueError("release asset hash mismatch")
        verified = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    verified_at = datetime.now(UTC) if verified else None
    asset = source.asset.model_copy(
        update={"downloaded_sha256": downloaded_sha256, "verified": verified}
    )
    publication_id = (
        f"day3-release-verification-{uuid.uuid4().hex[:16]}"
        if verified
        else f"day3-publication-attempt-{attempt}-blocked-{uuid.uuid4().hex[:12]}"
    )
    payload = {
        **source.model_dump(mode="python"),
        "publication_id": publication_id,
        "status": "VERIFIED" if verified else "PUBLICATION_BLOCKED",
        "asset": asset.model_dump(mode="json"),
        "attempt": attempt,
        "error": error,
        "verified_at": verified_at,
        "created_at": datetime.now(UTC),
    }
    payload.pop("content_sha256", None)
    result = Day3PublicationManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(
                payload,
                excluded_keys={
                    "publication_id",
                    "created_at",
                    "verified_at",
                    "content_sha256",
                },
            ),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        publication_id,
        {"publication.json": canonical_json_bytes(result) + b"\n"},
    )


def _scientific_decision(root: Path) -> Day3ScientificDecisionV0_1:
    paths = sorted((root / "scientific-decisions").glob("*/decision.json"))
    if len(paths) != 1:
        raise ValueError("packaging requires exactly one scientific decision")
    return Day3ScientificDecisionV0_1.model_validate_json(paths[0].read_bytes(), strict=True)


def _prior_failures(root: Path, archive_sha256: str) -> list[Day3PublicationManifestV0_1]:
    values = [
        Day3PublicationManifestV0_1.model_validate_json(path.read_bytes(), strict=True)
        for path in sorted(root.glob("*/publication.json"))
    ]
    return [
        item
        for item in values
        if item.status == "PUBLICATION_BLOCKED" and item.asset.archive_sha256 == archive_sha256
    ]


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


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
