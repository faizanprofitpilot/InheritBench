import json
from pathlib import Path

from inheritbench.compute.modal_smoke import record_blocked_modal_smoke


def test_modal_blocker_is_recorded_without_remote_attempt(tmp_path: Path) -> None:
    path = record_blocked_modal_smoke(output_root=tmp_path, reason="approval denied")
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["status"] == "BLOCKED"
    assert result["attempts"] == 0
    assert result["remote_environment"] is None
