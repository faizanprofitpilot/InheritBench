"""Deterministic Phase 3B adapter packaging and public verification."""

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
from inheritbench.phase3b.config import load_experiment_config, resolve
from inheritbench.phase3b.schemas import (
    Phase3BPublicationManifestV0_1,
    Phase3BScientificDecisionV0_1,
)
from inheritbench.phase3b.training import find_checkpoint_decision

_PUBLICATION_EXCLUSIONS = {
    "publication_id",
    "verification_timestamp",
    "content_sha256",
}


def package_adapter(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    science = _science(experiment_path)
    if science.scientific_status != "PHASE3B_SCIENTIFICALLY_COMPLETED":
        raise ValueError("only scientifically completed Phase 3B adapters may be packaged")
    _, checkpoint = find_checkpoint_decision(experiment_path)
    if checkpoint.status != "SELECTED" or checkpoint.selected_adapter is None:
        raise ValueError("Phase 3B packaging requires the selected verified adapter")
    adapter_path = verify_adapter(checkpoint.selected_adapter, Path.cwd())
    required = ["README.md", "adapter_config.json", "adapter_model.safetensors", "lineage.json"]
    if sorted(path.name for path in adapter_path.iterdir() if path.is_file()) != sorted(required):
        raise ValueError("selected adapter contains unexpected or missing package files")
    archive_name = f"{checkpoint.selected_adapter.adapter_id}.zip"
    archive_bytes = deterministic_zip(adapter_path, required)
    archive_sha = sha256_bytes(archive_bytes)
    sums = f"{archive_sha}  {archive_name}\n".encode()
    publication_id = f"phase3b-publication-package-{archive_sha[:16]}"
    expected_url = (
        "https://github.com/faizanprofitpilot/InheritBench/releases/download/"
        f"{experiment.release_tag}/{archive_name}"
    )
    payload = {
        "schema_version": "phase3b-publication-v0.1",
        "publication_id": publication_id,
        "publication_status": "NOT_ATTEMPTED",
        "scientific_decision_sha256": science.content_sha256,
        "lineage": science.lineage,
        "release_tag": experiment.release_tag,
        "release_commit": None,
        "archive_name": archive_name,
        "archive_sha256": archive_sha,
        "adapter_file_sha256s": checkpoint.selected_adapter.file_sha256s,
        "urls": [expected_url],
        "attempts": 0,
        "anonymous_download_verified": False,
        "verification_timestamp": None,
    }
    publication = Phase3BPublicationManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PUBLICATION_EXCLUSIONS),
        },
        strict=True,
    )
    return write_atomic_bundle(
        resolve(experiment_path, experiment.artifact_root) / "publications",
        publication_id,
        {
            archive_name: archive_bytes,
            "SHA256SUMS": sums,
            "publication.json": canonical_json_bytes(publication) + b"\n",
        },
    )


def verify_release(publication_path: Path, output_root: Path) -> Path:
    publication = Phase3BPublicationManifestV0_1.model_validate_json(
        (publication_path / "publication.json").read_bytes(), strict=True
    )
    if publication.publication_status != "NOT_ATTEMPTED":
        raise ValueError("release verification requires the deterministic package manifest")
    if publication.archive_name is None or publication.archive_sha256 is None:
        raise ValueError("package manifest lacks archive identity")
    with urllib.request.urlopen(publication.urls[0], timeout=120) as response:
        downloaded = response.read()
    if sha256_bytes(downloaded) != publication.archive_sha256:
        raise ValueError("public Phase 3B archive hash mismatch")
    internal = _zip_hashes(downloaded)
    if internal != publication.adapter_file_sha256s:
        raise ValueError("public Phase 3B archive internal file hashes mismatch")
    commit = subprocess.run(
        ["git", "rev-list", "-n", "1", publication.release_tag],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    verified_at = datetime.now(UTC)
    publication_id = f"phase3b-publication-verified-{uuid.uuid4().hex[:16]}"
    payload = {
        **publication.model_dump(mode="python"),
        "publication_id": publication_id,
        "publication_status": "PUBLISHED_VERIFIED",
        "release_commit": commit,
        "attempts": 1,
        "anonymous_download_verified": True,
        "verification_timestamp": verified_at,
    }
    payload.pop("content_sha256")
    verified = Phase3BPublicationManifestV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_PUBLICATION_EXCLUSIONS),
        },
        strict=True,
    )
    return write_atomic_bundle(
        output_root,
        publication_id,
        {"publication.json": canonical_json_bytes(verified) + b"\n"},
    )


def finalize_distribution(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    science = _science(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    verified = sorted((root / "publication-verifications").glob("*/publication.json"))
    if verified:
        publication = Phase3BPublicationManifestV0_1.model_validate_json(
            verified[-1].read_bytes(), strict=True
        )
    else:
        package_path = _single(root / "publications", "publication.json")
        package = Phase3BPublicationManifestV0_1.model_validate_json(
            package_path.read_bytes(), strict=True
        )
        payload = {
            **package.model_dump(mode="python"),
            "publication_id": f"phase3b-publication-blocked-{uuid.uuid4().hex[:16]}",
            "publication_status": "PUBLICATION_BLOCKED",
            "attempts": 2,
        }
        payload.pop("content_sha256")
        publication = Phase3BPublicationManifestV0_1.model_validate(
            {
                **payload,
                "content_sha256": content_sha256(payload, excluded_keys=_PUBLICATION_EXCLUSIONS),
            },
            strict=True,
        )
    if publication.scientific_decision_sha256 != science.content_sha256:
        raise ValueError("publication cannot change the Phase 3B scientific decision")
    return write_atomic_bundle(
        root / "distribution-decisions",
        publication.publication_id,
        {"publication.json": canonical_json_bytes(publication) + b"\n"},
    )


def deterministic_zip(adapter_path: Path, names: list[str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(names):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (adapter_path / name).read_bytes())
    return output.getvalue()


def _zip_hashes(value: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(value)) as archive:
        names = sorted(archive.namelist())
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            raise ValueError("unsafe Phase 3B release archive path")
        return {name: sha256_bytes(archive.read(name)) for name in names}


def _science(experiment_path: Path) -> Phase3BScientificDecisionV0_1:
    experiment = load_experiment_config(experiment_path)
    path = _single(
        resolve(experiment_path, experiment.artifact_root) / "scientific-decisions",
        "decision.json",
    )
    return Phase3BScientificDecisionV0_1.model_validate_json(path.read_bytes(), strict=True)


def _single(root: Path, filename: str) -> Path:
    values = sorted(root.glob(f"*/{filename}"))
    if len(values) != 1:
        raise ValueError(f"expected one {root}/*/{filename}")
    return values[0]
