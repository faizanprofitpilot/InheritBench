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
day2_app = typer.Typer(no_args_is_help=True, help="Day 2 learned-capability workflow.")
day3_app = typer.Typer(no_args_is_help=True, help="Day 3 synthetic-distillation workflow.")
app.add_typer(data_app, name="data")
app.add_typer(compute_app, name="compute")
app.add_typer(day2_app, name="day2")
app.add_typer(day3_app, name="day3")
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


@day2_app.command("freeze-data")
def day2_freeze_data_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
) -> None:
    from inheritbench.day2.data import freeze_data

    path = freeze_data(experiment)
    console.print(f"[green]frozen[/green] {path}")


@day2_app.command("validate-configs")
def day2_validate_configs_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
) -> None:
    from inheritbench.day2.config import load_experiment_config, load_method_config

    config = load_experiment_config(experiment)
    for path in config.method_config_paths:
        load_method_config(Path(path))
    console.print("[green]validated[/green] five Day 2 method configs")


@day2_app.command("train")
def day2_train_command(
    method: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
    resume: Annotated[
        Path | None,
        typer.Option(exists=True, file_okay=False, help="Resume from an immutable checkpoint."),
    ] = None,
) -> None:
    from inheritbench.day2.training import train_method

    training, decision = train_method(
        experiment_path=experiment,
        method_path=method,
        device=device,
        resume_checkpoint=resume,
    )
    console.print(f"[green]trained[/green] {training}")
    console.print(f"[green]selected[/green] {decision}")


@day2_app.command("recover")
def day2_recover_command(
    active_run: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    mark_failed: Annotated[bool, typer.Option(help="Finalize the active run as failed.")] = False,
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/day2/failed"),
) -> None:
    from inheritbench.day2.training import recover_active

    if not mark_failed:
        raise typer.BadParameter("--mark-failed is required; active runs are never reused")
    path = recover_active(active_run, output_root)
    console.print(f"[yellow]recovered as failed[/yellow] {path}")


@day2_app.command("evaluate")
def day2_evaluate_command(
    method: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    split: Annotated[Literal["validation", "test"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.day2.evaluation import evaluate_method

    path = evaluate_method(
        experiment_path=experiment,
        method_path=method,
        split=split,
        device=device,
        command=sys.argv,
    )
    console.print(f"[green]evaluated[/green] {path}")


@day2_app.command("source-gate")
def day2_source_gate_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.day2.gates import run_source_gate

    path = run_source_gate(experiment, device=device)
    console.print(f"[green]source gate finalized[/green] {path}")


@day2_app.command("compare")
def day2_compare_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
) -> None:
    from inheritbench.day2.comparison import build_comparison

    path = build_comparison(experiment)
    console.print(f"[green]comparison finalized[/green] {path}")


@day2_app.command("replay")
def day2_replay_command(
    run: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/day2/replays"),
) -> None:
    from inheritbench.day2.evaluation import replay_evaluation

    path = replay_evaluation(run, output_root)
    console.print(f"[green]replay passed[/green] {path}")


@day2_app.command("package-adapters")
def day2_package_adapters_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day2.yaml"
    ),
) -> None:
    from inheritbench.day2.publication import package_adapters

    path = package_adapters(experiment)
    console.print(f"[green]packaged[/green] {path}")


@day2_app.command("verify-release")
def day2_verify_release_command(
    publication: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/day2/publications"),
) -> None:
    from inheritbench.day2.publication import verify_release

    path = verify_release(publication, output_root)
    console.print(f"[green]release verified[/green] {path}")


@day3_app.command("validate-configs")
def day3_validate_configs_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.config import load_experiment_config

    load_experiment_config(experiment)
    console.print("[green]validated[/green] Day 3 experiment, pool, method, and model configs")


@day3_app.command("freeze-pool")
def day3_freeze_pool_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.pool import freeze_pool

    path = freeze_pool(experiment, "initial")
    console.print(f"[green]initial pool frozen[/green] {path}")


@day3_app.command("verify-teacher")
def day3_verify_teacher_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.teacher import verify_teacher

    path = verify_teacher(experiment)
    console.print(f"[green]teacher verified[/green] {path}")


@day3_app.command("run-teacher")
def day3_run_teacher_command(
    pool: Annotated[Literal["initial", "expansion"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
    resume: Annotated[
        Path | None,
        typer.Option(exists=True, file_okay=False, help="Resume one failed teacher run."),
    ] = None,
) -> None:
    from inheritbench.day3.teacher import run_teacher

    path = run_teacher(experiment, pool, device=device, resume_run=resume)
    console.print(f"[green]teacher run finalized[/green] {path}")


@day3_app.command("filter")
def day3_filter_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.filtering import filter_teacher_outputs

    dataset, evidence = filter_teacher_outputs(experiment)
    console.print(f"[green]filter finalized[/green] {dataset} · {evidence}")


@day3_app.command("expand-pool")
def day3_expand_pool_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.filtering import find_synthetic_dataset
    from inheritbench.day3.pool import freeze_pool

    _, dataset = find_synthetic_dataset(experiment, require_completed=False)
    if dataset.status != "NEEDS_EXPANSION":
        raise typer.BadParameter("expansion is allowed only after an insufficient initial filter")
    path = freeze_pool(experiment, "expansion")
    console.print(f"[yellow]expansion pool frozen[/yellow] {path}")


@day3_app.command("freeze-schedule")
def day3_freeze_schedule_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.filtering import freeze_schedule

    path = freeze_schedule(experiment)
    console.print(f"[green]schedule frozen[/green] {path}")


@day3_app.command("train")
def day3_train_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
    resume: Annotated[
        Path | None,
        typer.Option(exists=True, file_okay=False, help="Resume from an immutable checkpoint."),
    ] = None,
) -> None:
    from inheritbench.day3.training import train_method

    training, decision = train_method(experiment, device=device, resume_checkpoint=resume)
    console.print(f"[green]trained[/green] {training}")
    console.print(f"[green]checkpoint decision[/green] {decision}")


@day3_app.command("recover")
def day3_recover_command(
    active_run: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    mark_failed: Annotated[bool, typer.Option(help="Finalize active evidence as failed.")] = False,
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.config import load_experiment_config, resolve

    if not mark_failed:
        raise typer.BadParameter("--mark-failed is required; active runs are never reused")
    config = load_experiment_config(experiment)
    failed_root = resolve(experiment, config.artifact_root) / "failed"
    if (active_run / "active.json").is_file():
        from inheritbench.day3.training import recover_active as recover_training

        path = recover_training(active_run, failed_root)
    else:
        from inheritbench.day3.teacher import recover_active as recover_teacher

        path = recover_teacher(active_run, failed_root)
    console.print(f"[yellow]recovered as failed[/yellow] {path}")


@day3_app.command("evaluate")
def day3_evaluate_command(
    split: Annotated[Literal["validation", "test"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.day3.evaluation import evaluate_method

    path = evaluate_method(experiment, split, device=device)
    console.print(f"[green]evaluated[/green] {path}")


@day3_app.command("replay")
def day3_replay_command(
    kind: Annotated[
        Literal["teacher", "filter", "schedule", "evaluation", "comparison"],
        typer.Option(),
    ],
    artifact: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.lifecycle import replay_artifact

    path = replay_artifact(experiment, kind, artifact)
    console.print(f"[green]replay passed[/green] {path}")


@day3_app.command("analyze-failures")
def day3_analyze_failures_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.lifecycle import analyze_failures

    path = analyze_failures(experiment)
    console.print(f"[green]failure analysis finalized[/green] {path}")


@day3_app.command("compare")
def day3_compare_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.lifecycle import build_comparison

    path = build_comparison(experiment)
    console.print(f"[green]comparison finalized[/green] {path}")


@day3_app.command("finalize-science")
def day3_finalize_science_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.lifecycle import finalize_science
    from inheritbench.day3.schemas import Day3ScientificDecisionV0_1

    path = finalize_science(experiment)
    decision = Day3ScientificDecisionV0_1.model_validate_json(
        (path / "decision.json").read_bytes(), strict=True
    )
    color = "green" if decision.scientific_status == "SCIENTIFICALLY_COMPLETED" else "yellow"
    console.print(f"[{color}]{decision.scientific_status} · {decision.day4_gate}[/{color}] {path}")


@day3_app.command("package-adapter")
def day3_package_adapter_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.publication import package_adapter

    path = package_adapter(experiment)
    console.print(f"[green]adapter packaged[/green] {path}")


@day3_app.command("verify-release")
def day3_verify_release_command(
    publication: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    output_root: Annotated[Path, typer.Option()] = Path("artifacts/day3/publications"),
) -> None:
    from inheritbench.day3.publication import verify_release

    path = verify_release(publication, output_root)
    console.print(f"[green]publication attempt finalized[/green] {path}")


@day3_app.command("finalize-distribution")
def day3_finalize_distribution_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3.yaml"
    ),
) -> None:
    from inheritbench.day3.lifecycle import finalize_distribution

    path = finalize_distribution(experiment)
    console.print(f"[green]distribution decision finalized[/green] {path}")


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
