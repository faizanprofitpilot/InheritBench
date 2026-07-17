import json
from pathlib import Path

from typer.testing import CliRunner

from inheritbench.cli import app


def test_succession_replay_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    command = [
        "succession",
        "replay",
        "--case",
        "opsroute-qwen-olmo",
        "--profile",
        "maximum-confirmed-capability",
        "--output",
        str(tmp_path),
    ]
    first = runner.invoke(app, command)
    second = runner.invoke(app, command)
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    bundles = list(tmp_path.iterdir())
    assert len(bundles) == 1
    report = json.loads((bundles[0] / "readiness_report.json").read_text())
    receipt = json.loads((bundles[0] / "replay_receipt.json").read_text())
    assert report["decision"] == "CONDITIONAL_PASS"
    assert receipt["status"] == "VERIFIED_REPLAY_COMPLETED"


def test_succession_replay_rejects_unsupported_case(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["succession", "replay", "--case", "unsupported", "--output", str(tmp_path)],
    )
    assert result.exit_code == 2


def test_full_preflight_outputs_machine_readable_contract() -> None:
    result = CliRunner().invoke(
        app,
        [
            "succession",
            "preflight",
            "--case",
            "opsroute-qwen-olmo",
            "--mode",
            "full",
            "--json",
            "-",
        ],
    )
    assert result.exit_code in {0, 1}, result.output
    report = json.loads(result.output)
    expected_exit_code = 0 if report["status"] == "FULL_WORKFLOW_PREFLIGHT_READY" else 1
    assert result.exit_code == expected_exit_code
    if report["status"] == "FAILED":
        assert any(check["blocking"] and check["status"] == "FAIL" for check in report["checks"])
    assert len(report["phased_commands"]) >= 10
    assert not any("one-click" in command.lower() for command in report["phased_commands"])
