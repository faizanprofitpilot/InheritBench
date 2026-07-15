from pathlib import Path

from inheritbench.artifacts.hashing import sha256_bytes
from inheritbench.day2.publication import _deterministic_zip


def test_adapter_zip_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "adapter_config.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "adapter_model.safetensors").write_bytes(b"weights")
    first = _deterministic_zip(tmp_path)
    (tmp_path / "adapter_config.json").touch()
    second = _deterministic_zip(tmp_path)
    assert first == second
    assert sha256_bytes(first) == sha256_bytes(second)
