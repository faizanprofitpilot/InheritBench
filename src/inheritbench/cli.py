"""InheritBench command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from inheritbench import __version__
from inheritbench.artifacts.hashing import canonical_json, canonical_json_bytes
from inheritbench.artifacts.store import write_atomic_file
from inheritbench.config import load_model_config, load_task_config
from inheritbench.logging import configure_logging

app = typer.Typer(no_args_is_help=True, help="Reproducible model-succession benchmark core.")
data_app = typer.Typer(no_args_is_help=True, help="Deterministic dataset commands.")
compute_app = typer.Typer(no_args_is_help=True, help="Bounded compute checks.")
app.add_typer(data_app, name="data")
app.add_typer(compute_app, name="compute")
console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
    json_logs: Annotated[
        bool,
        typer.Option(help="Render structured logs as JSON on stderr."),
    ] = False,
) -> None:
    del version
    configure_logging(json_logs=json_logs)


@app.command("doctor")
def doctor_command(
    source: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    target: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    task: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    check_hub: Annotated[
        bool,
        typer.Option(help="Check pinned Hub metadata without weights."),
    ] = False,
    profile: Annotated[Literal["local", "modal"], typer.Option()] = "local",
    json_output: Annotated[
        Path | None,
        typer.Option("--json", help="Write JSON to PATH, or use '-' for stdout."),
    ] = None,
) -> None:
    from inheritbench.doctor import run_doctor

    try:
        result = run_doctor(
            source_path=source,
            target_path=target,
            task_path=task,
            check_hub=check_hub,
            profile=profile,
        )
        if json_output is not None:
            if str(json_output) == "-":
                typer.echo(canonical_json(result))
            else:
                write_atomic_file(json_output, canonical_json_bytes(result) + b"\n")
        else:
            _doctor_table(result)
        if result.overall == "FAIL":
            raise typer.Exit(code=1)
    except (ValidationError, ValueError) as exc:
        console.print(f"[red]Invalid configuration:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command("inspect-pair")
def inspect_pair_command(
    source: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    target: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    mode: Annotated[Literal["metadata", "loaded"], typer.Option()],
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/inspections"),
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "auto",
) -> None:
    from inheritbench.models.inspection import inspect_pair, write_inspection

    try:
        result = inspect_pair(
            load_model_config(source),
            load_model_config(target),
            mode=mode,
            device_override=device,
        )
        path = write_inspection(result, output_root)
        console.print(
            f"[bold]{result.heterogeneity_verdict}[/bold] · adapter reuse "
            f"{result.direct_adapter_reuse} · {path}"
        )
    except (ValidationError, ValueError) as exc:
        console.print(f"[red]Invalid configuration:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@data_app.command("generate")
def data_generate_command(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option()],
    check: Annotated[
        bool,
        typer.Option(help="Regenerate in memory and compare exact bytes."),
    ] = False,
) -> None:
    from inheritbench.data.opsroute.generate import check_dataset, write_dataset

    try:
        task_config = load_task_config(config)
        manifest = (
            check_dataset(task_config, output) if check else write_dataset(task_config, output)
        )
        console.print(
            f"[green]{'verified' if check else 'generated'}[/green] "
            f"{manifest.total_records} records · {manifest.dataset_sha256}"
        )
    except (ValidationError, ValueError, FileExistsError, FileNotFoundError) as exc:
        console.print(f"[red]Dataset command failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command("infer")
def infer_command(
    source: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    target: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    task: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    examples: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "auto",
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/runs"),
) -> None:
    from inheritbench.inference.runner import run_pair_inference

    path = run_pair_inference(
        source_path=source,
        target_path=target,
        task_path=task,
        examples_path=examples,
        device=device,
        output_root=output_root,
        command=sys.argv,
    )
    console.print(f"[green]finalized[/green] {path}")


@app.command("evaluate")
def evaluate_command(
    run: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    verify_stored: Annotated[
        bool,
        typer.Option(help="Verify original artifact byte hashes."),
    ] = True,
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/replays"),
) -> None:
    from inheritbench.inference.runner import replay_run

    path = replay_run(run_directory=run, output_root=output_root, verify_stored=verify_stored)
    console.print(f"[green]replay passed[/green] {path}")


@compute_app.command("modal-smoke")
def modal_smoke_command(
    gpu: Annotated[Literal["L4"], typer.Option()] = "L4",
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/modal"),
) -> None:
    from inheritbench.compute.modal_smoke import ModalSmokeResult, run_modal_smoke

    path = run_modal_smoke(gpu=gpu, output_root=output_root)
    result = ModalSmokeResult.model_validate_json(path.read_bytes(), strict=True)
    style = "green" if result.status == "COMPLETED" else "yellow"
    console.print(f"[{style}]{result.status}[/{style}] {path}")


def _doctor_table(result: object) -> None:
    from inheritbench.doctor import DoctorResult

    doctor = DoctorResult.model_validate(result)
    table = Table(title=f"InheritBench doctor: {doctor.overall}")
    table.add_column("Status")
    table.add_column("Check")
    table.add_column("Message")
    for check in doctor.checks:
        table.add_row(check.status, check.id, check.message)
    console.print(table)


def entrypoint() -> None:
    try:
        app()
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Internal failure:[/red] {type(exc).__name__}: {exc}")
        raise typer.Exit(code=3) from exc


if __name__ == "__main__":
    entrypoint()
