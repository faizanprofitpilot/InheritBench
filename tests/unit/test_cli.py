from typer.testing import CliRunner

from inheritbench.cli import app


def test_cli_version_and_help() -> None:
    runner = CliRunner()
    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert version.stdout.strip() == "0.1.0"
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "model-succession" in help_result.stdout
