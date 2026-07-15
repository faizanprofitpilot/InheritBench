from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from inheritbench.phase3b import baseline
from inheritbench.phase3b.schemas import Phase3BPreregistrationAttestationV0_1

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
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b""),
    )
    with pytest.raises(ValueError, match="not committed"):
        baseline.attest_preregistration(EXPERIMENT)
