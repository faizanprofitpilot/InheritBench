from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from inheritbench.phase3b import baseline
from inheritbench.phase3b.publication import _zip_hashes, deterministic_zip
from inheritbench.phase3b.schemas import (
    Phase3BPreregistrationAttestationV0_1,
    Phase3BPublicationManifestV0_1,
    Phase3BScientificDecisionV0_1,
)

EXPERIMENT = Path("configs/experiments/phase3b.yaml")
COMMIT = "1" * 40


def test_preregistration_rejects_dirty_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(baseline, "_git", lambda arguments: " M configs/a.yaml")
    with pytest.raises(ValueError, match="clean worktree"):
        baseline.attest_preregistration(EXPERIMENT)


def test_preregistration_reads_required_bytes_from_git_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_git(arguments: list[str]) -> str:
        return "" if arguments[0] == "status" else COMMIT

    def fake_run(arguments: list[str], **_: object) -> SimpleNamespace:
        calls.append(arguments)
        object_spec = arguments[-1]
        if arguments[1] == "cat-file":
            return SimpleNamespace(returncode=0, stdout=b"")
        relative = object_spec.split(":", 1)[1]
        return SimpleNamespace(returncode=0, stdout=Path(relative).read_bytes())

    def fake_write(_root: Path, _bundle_id: str, files: dict[str, bytes]) -> Path:
        output = tmp_path / "attestation.json"
        output.write_bytes(files["attestation.json"])
        return output

    monkeypatch.setattr(baseline, "_git", fake_git)
    monkeypatch.setattr(baseline, "_real_training_exists", lambda root: False)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(baseline, "write_atomic_bundle", fake_write)

    output = baseline.attest_preregistration(EXPERIMENT)
    attestation = Phase3BPreregistrationAttestationV0_1.model_validate_json(
        output.read_bytes(), strict=True
    )
    assert attestation.preregistration_commit == COMMIT
    assert attestation.git_object_verification_passed is True
    assert len([call for call in calls if call[1] == "cat-file"]) == len(
        attestation.required_paths_in_commit
    )
    assert len([call for call in calls if call[1] == "show"]) == len(
        attestation.required_paths_in_commit
    )


def test_preregistration_rejects_missing_git_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        baseline,
        "_git",
        lambda arguments: "" if arguments[0] == "status" else COMMIT,
    )
    monkeypatch.setattr(baseline, "_real_training_exists", lambda root: False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b""),
    )
    with pytest.raises(ValueError, match="not committed"):
        baseline.attest_preregistration(EXPERIMENT)


def test_publication_status_cannot_change_scientific_gate() -> None:
    decision_path = next(Path("artifacts/phase3b/scientific-decisions").glob("*/decision.json"))
    decision = Phase3BScientificDecisionV0_1.model_validate_json(
        decision_path.read_bytes(), strict=True
    )
    payload = {
        "schema_version": "phase3b-publication-v0.1",
        "publication_id": "fixture-publication",
        "publication_status": "PUBLICATION_BLOCKED",
        "scientific_decision_sha256": decision.content_sha256,
        "lineage": decision.lineage,
        "release_tag": "phase3b-anchored-v0.1.0",
        "release_commit": None,
        "archive_name": None,
        "archive_sha256": None,
        "adapter_file_sha256s": {},
        "urls": [],
        "attempts": 2,
        "anonymous_download_verified": False,
        "verification_timestamp": None,
        "content_sha256": "0" * 64,
    }
    publication = Phase3BPublicationManifestV0_1.model_validate(payload, strict=True)
    assert publication.publication_status == "PUBLICATION_BLOCKED"
    assert decision.scientific_status == "PHASE3B_SCIENTIFICALLY_COMPLETED"
    assert decision.day4_gate == "DAY4_UNBLOCKED"


def test_phase3b_adapter_archive_is_deterministic() -> None:
    adapter = Path("adapters/phase3b/target_hybrid_anchored_distillation_10-7461072c83b4dcde")
    names = ["README.md", "adapter_config.json", "adapter_model.safetensors", "lineage.json"]
    first = deterministic_zip(adapter, names)
    second = deterministic_zip(adapter, list(reversed(names)))
    assert first == second
    assert _zip_hashes(first) == {
        name: hashlib.sha256((adapter / name).read_bytes()).hexdigest() for name in names
    }
