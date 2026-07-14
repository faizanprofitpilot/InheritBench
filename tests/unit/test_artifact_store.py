from pathlib import Path

import pytest

from inheritbench.artifacts.store import write_atomic_bundle, write_atomic_file


def test_atomic_file_and_bundle_refuse_overwrite(tmp_path: Path) -> None:
    file_path = tmp_path / "artifact.json"
    write_atomic_file(file_path, b"{}\n")
    with pytest.raises(FileExistsError):
        write_atomic_file(file_path, b"{}\n")

    bundle = write_atomic_bundle(tmp_path, "run-1", {"data.json": b"{}\n"})
    assert bundle.joinpath("data.json").read_bytes() == b"{}\n"
    with pytest.raises(FileExistsError):
        write_atomic_bundle(tmp_path, "run-1", {"data.json": b"changed"})
