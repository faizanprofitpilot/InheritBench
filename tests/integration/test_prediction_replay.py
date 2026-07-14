from pathlib import Path

import pytest

from inheritbench.artifacts.schemas import ArtifactReference
from inheritbench.artifacts.store import verify_reference


def test_tampered_prediction_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "predictions.jsonl"
    path.write_bytes(b"tampered\n")
    reference = ArtifactReference(
        relative_path="predictions.jsonl",
        byte_sha256="0" * 64,
        content_sha256="1" * 64,
        bytes=len(b"tampered\n"),
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_reference(tmp_path, reference)
