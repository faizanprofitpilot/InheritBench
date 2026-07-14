"""Atomic no-overwrite artifact storage and verification."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from inheritbench.artifacts.hashing import sha256_bytes, sha256_file
from inheritbench.artifacts.schemas import ArtifactReference


def artifact_reference(
    relative_path: str, payload: bytes, *, content_sha256: str
) -> ArtifactReference:
    return ArtifactReference(
        relative_path=relative_path,
        byte_sha256=sha256_bytes(payload),
        content_sha256=content_sha256,
        bytes=len(payload),
    )


def write_atomic_bundle(output_root: Path, bundle_id: str, files: dict[str, bytes]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / bundle_id
    if destination.exists():
        raise FileExistsError(f"artifact bundle already exists: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=f".tmp-{bundle_id}-", dir=output_root))
    try:
        for relative_name, payload in files.items():
            path = staging / relative_name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        _fsync_tree(staging)
        os.replace(staging, destination)
        _fsync_directory(output_root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_atomic_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"artifact already exists: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".tmp-{path.name}-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def verify_reference(bundle: Path, reference: ArtifactReference) -> None:
    path = bundle / reference.relative_path
    if not path.is_file():
        raise FileNotFoundError(f"referenced artifact is missing: {path}")
    if path.stat().st_size != reference.bytes:
        raise ValueError(f"artifact byte count mismatch: {path}")
    actual = sha256_file(path)
    if actual != reference.byte_sha256:
        raise ValueError(
            f"artifact hash mismatch for {path}: expected {reference.byte_sha256}, got {actual}"
        )


def _fsync_tree(root: Path) -> None:
    directories = sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True)
    for directory in directories:
        _fsync_directory(directory)
    _fsync_directory(root)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
