"""InheritBench command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal, cast

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
day3_matched_app = typer.Typer(
    no_args_is_help=True,
    help="Final distribution-matched Day 3 recovery workflow.",
)
phase3b_app = typer.Typer(
    no_args_is_help=True,
    help="Phase 3B anchored behavioral transfer workflow.",
)
phase4_app = typer.Typer(
    no_args_is_help=True,
    help="Phase 4 adversarial evidence and GPT-5.6 analysis workflow.",
)
app.add_typer(data_app, name="data")
app.add_typer(compute_app, name="compute")
app.add_typer(day2_app, name="day2")
app.add_typer(day3_app, name="day3")
app.add_typer(day3_matched_app, name="day3-matched")
app.add_typer(phase3b_app, name="phase3b")
app.add_typer(phase4_app, name="phase4")
console = Console(stderr=True)


@phase4_app.command("validate-configs")
def phase4_validate_configs_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.config import load_experiment_config

    load_experiment_config(experiment)
    console.print("[green]validated[/green] isolated Phase 4 configs")


@phase4_app.command("freeze-protocol")
def phase4_freeze_protocol_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.protocol import freeze_protocol

    path = freeze_protocol(experiment)
    console.print(f"[green]Phase 4 protocol frozen[/green] {path}")


@phase4_app.command("attest-protocol")
def phase4_attest_protocol_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.protocol import attest_protocol

    path = attest_protocol(experiment)
    console.print(f"[green]Phase 4 protocol attested[/green] {path}")


@phase4_app.command("evaluate-adversarial")
def phase4_evaluate_adversarial_command(
    system: Annotated[
        Literal[
            "source_base_supporting",
            "source_adapted_full",
            "target_untouched",
            "target_full_retrain",
            "target_limited_retrain_10pct",
            "target_hybrid_anchored_distillation_10",
        ],
        typer.Option(),
    ],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
    resume: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None,
) -> None:
    from inheritbench.phase4.evaluation import evaluate_adversarial

    path = evaluate_adversarial(experiment, system, resume=resume)
    console.print(f"[green]Phase 4 adversarial evaluation completed[/green] {path}")


@phase4_app.command("replay")
def phase4_replay_command(
    artifact: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    kind: Annotated[
        Literal["evaluation", "analysis", "profiles", "cases", "evidence"] | None,
        typer.Option(),
    ] = None,
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.analysis import replay_derived
    from inheritbench.phase4.config import load_experiment_config, resolve
    from inheritbench.phase4.evaluation import replay_evaluation

    config = load_experiment_config(experiment)
    output_root = resolve(experiment, config.artifact_root) / "replays"
    resolved_kind = kind or (
        "evaluation" if (artifact / "manifest.json").is_file() else _phase4_replay_kind(artifact)
    )
    path = (
        replay_evaluation(artifact, output_root)
        if resolved_kind == "evaluation"
        else replay_derived(experiment, resolved_kind, artifact)
    )
    console.print(f"[green]Phase 4 replay passed[/green] {path}")


@phase4_app.command("analyze")
def phase4_analyze_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.analysis import analyze

    path = analyze(experiment)
    console.print(f"[green]Phase 4 analyses frozen[/green] {path}")


@phase4_app.command("compute-profiles")
def phase4_compute_profiles_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.analysis import compute_profiles

    path = compute_profiles(experiment)
    console.print(f"[green]Phase 4 migration profiles frozen[/green] {path}")


@phase4_app.command("select-cases")
def phase4_select_cases_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.analysis import select_cases

    path = select_cases(experiment)
    console.print(f"[green]Phase 4 representative cases frozen[/green] {path}")


@phase4_app.command("build-evidence-pack")
def phase4_build_evidence_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.analysis import build_evidence_pack

    path = build_evidence_pack(experiment)
    console.print(f"[green]Phase 4 evidence pack validated[/green] {path}")


@phase4_app.command("build-fallback-memo")
def phase4_build_fallback_memo_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.memo import build_fallback_memo

    path = build_fallback_memo(experiment)
    console.print(f"[green]Phase 4 deterministic fallback validated[/green] {path}")


@phase4_app.command("generate-gpt-memo")
def phase4_generate_gpt_memo_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.memo import generate_gpt_memo

    path = generate_gpt_memo(experiment)
    console.print(f"[green]Phase 4 GPT memo attempt finalized[/green] {path}")


@phase4_app.command("validate-memo")
def phase4_validate_memo_command(
    memo: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.memo import validate_memo

    path = validate_memo(experiment, memo)
    console.print(f"[green]Phase 4 memo validation passed[/green] {path}")


@phase4_app.command("build-showcase")
def phase4_build_showcase_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.showcase import build_showcase

    path = build_showcase(experiment)
    console.print(f"[green]Phase 4 showcase built[/green] {path}")


@phase4_app.command("replay-showcase")
def phase4_replay_showcase_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.showcase import replay_showcase

    path = replay_showcase(experiment)
    console.print(f"[green]Phase 4 showcase replay passed[/green] {path}")


@phase4_app.command("finalize")
def phase4_finalize_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase4.yaml"
    ),
) -> None:
    from inheritbench.phase4.showcase import finalize

    path = finalize(experiment)
    console.print(f"[green]Phase 4 decision finalized[/green] {path}")


def _phase4_replay_kind(
    artifact: Path,
) -> Literal["analysis", "profiles", "cases", "evidence"]:
    candidates = {
        "analysis": "analysis.json",
        "profiles": "profiles.json",
        "cases": "cases.json",
        "evidence": "evidence.json",
    }
    matches = [name for name, filename in candidates.items() if (artifact / filename).is_file()]
    if len(matches) != 1:
        raise typer.BadParameter("unable to infer replay kind; pass --kind")
    return cast(Literal["analysis", "profiles", "cases", "evidence"], matches[0])


@phase3b_app.command("validate-configs")
def phase3b_validate_configs_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.config import load_experiment_config

    load_experiment_config(experiment)
    console.print("[green]validated[/green] isolated Phase 3B configs")


@phase3b_app.command("freeze-baseline")
def phase3b_freeze_baseline_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.baseline import freeze_baseline

    path = freeze_baseline(experiment)
    console.print(f"[green]Phase 3B historical baseline frozen[/green] {path}")


@phase3b_app.command("attest-preregistration")
def phase3b_attest_preregistration_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.baseline import attest_preregistration

    path = attest_preregistration(experiment)
    console.print(f"[green]Phase 3B preregistration attested[/green] {path}")


@phase3b_app.command("freeze-hybrid-selection")
def phase3b_freeze_hybrid_selection_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.selection import freeze_hybrid_selection

    synthetic, anchors, hybrid = freeze_hybrid_selection(experiment)
    console.print(
        f"[green]Phase 3B hybrid selection frozen[/green] {synthetic} · {anchors} · {hybrid}"
    )


@phase3b_app.command("freeze-confirmatory-data")
def phase3b_freeze_confirmatory_data_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.confirmatory import freeze_confirmatory_data

    path = freeze_confirmatory_data(experiment)
    console.print(f"[green]Phase 3B confirmatory data frozen[/green] {path}")


@phase3b_app.command("audit-confirmatory-leakage")
def phase3b_audit_confirmatory_leakage_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.confirmatory import audit_confirmatory_leakage

    path = audit_confirmatory_leakage(experiment)
    console.print(f"[green]Phase 3B confirmatory leakage audit passed[/green] {path}")


@phase3b_app.command("freeze-schedule")
def phase3b_freeze_schedule_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.training import freeze_schedule

    path = freeze_schedule(experiment)
    console.print(f"[green]Phase 3B training schedule frozen[/green] {path}")


@phase3b_app.command("train")
def phase3b_train_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
    resume: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None,
) -> None:
    from inheritbench.phase3b.training import train_method

    path = train_method(experiment, device=device, resume_checkpoint=resume)
    console.print(f"[green]Phase 3B training completed[/green] {path}")


@phase3b_app.command("recover")
def phase3b_recover_command(
    active_run: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    mark_failed: Annotated[bool, typer.Option("--mark-failed")] = False,
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.config import load_experiment_config, resolve
    from inheritbench.phase3b.training import recover_active

    if not mark_failed:
        raise typer.BadParameter("Phase 3B recovery requires --mark-failed")
    config = load_experiment_config(experiment)
    path = recover_active(active_run, resolve(experiment, config.artifact_root) / "failed")
    console.print(f"[yellow]Phase 3B active run finalized failed[/yellow] {path}")


@phase3b_app.command("evaluate")
def phase3b_evaluate_command(
    split: Annotated[
        Literal["confirmatory-validation", "confirmatory-test", "legacy-test"],
        typer.Option(),
    ],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.phase3b.evaluation import evaluate_checkpoints, evaluate_hybrid

    if split == "confirmatory-validation":
        paths = evaluate_checkpoints(experiment, device=device if device != "auto" else "mps")
    elif split == "confirmatory-test":
        paths = [evaluate_hybrid(experiment, "confirmatory_test", device=device)]
    else:
        paths = [evaluate_hybrid(experiment, "exploratory_legacy_test", device=device)]
    console.print(f"[green]Phase 3B evaluation completed[/green] {len(paths)} run(s)")


@phase3b_app.command("select-checkpoint")
def phase3b_select_checkpoint_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.evaluation import select_checkpoint

    path = select_checkpoint(experiment)
    console.print(f"[green]Phase 3B checkpoint decision frozen[/green] {path}")


@phase3b_app.command("evaluate-confirmatory-matrix")
def phase3b_evaluate_matrix_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.phase3b.evaluation import evaluate_confirmatory_matrix

    paths = evaluate_confirmatory_matrix(experiment, device=device)
    console.print(f"[green]Phase 3B matrix evaluation completed[/green] {len(paths)} run(s)")


@phase3b_app.command("replay")
def phase3b_replay_command(
    kind: Annotated[Literal["evaluation", "analysis", "comparison"], typer.Option()],
    artifact: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.config import load_experiment_config, resolve
    from inheritbench.phase3b.evaluation import replay_evaluation
    from inheritbench.phase3b.lifecycle import replay_derived

    config = load_experiment_config(experiment)
    output_root = resolve(experiment, config.artifact_root) / "replays"
    path = (
        replay_evaluation(artifact, output_root)
        if kind == "evaluation"
        else replay_derived(kind, artifact, output_root)
    )
    console.print(f"[green]Phase 3B replay passed[/green] {path}")


@phase3b_app.command("analyze-failures")
def phase3b_analyze_failures_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.lifecycle import analyze_failures

    path = analyze_failures(experiment)
    console.print(f"[green]Phase 3B failure analysis frozen[/green] {path}")


@phase3b_app.command("compare")
def phase3b_compare_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.lifecycle import build_comparisons

    paths = build_comparisons(experiment)
    console.print(f"[green]Phase 3B comparisons frozen[/green] {len(paths)} bundle(s)")


@phase3b_app.command("finalize-science")
def phase3b_finalize_science_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
    blocked_reason: Annotated[str | None, typer.Option()] = None,
) -> None:
    from inheritbench.phase3b.lifecycle import finalize_science

    path = finalize_science(experiment, blocked_reason)
    console.print(f"[green]Phase 3B scientific decision frozen[/green] {path}")


@phase3b_app.command("package-adapter")
def phase3b_package_adapter_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.publication import package_adapter

    path = package_adapter(experiment)
    console.print(f"[green]Phase 3B adapter packaged[/green] {path}")


@phase3b_app.command("verify-release")
def phase3b_verify_release_command(
    publication: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.config import load_experiment_config, resolve
    from inheritbench.phase3b.publication import verify_release

    config = load_experiment_config(experiment)
    path = verify_release(
        publication,
        resolve(experiment, config.artifact_root) / "publication-verifications",
    )
    console.print(f"[green]Phase 3B public release verified[/green] {path}")


@phase3b_app.command("finalize-distribution")
def phase3b_finalize_distribution_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/phase3b.yaml"
    ),
) -> None:
    from inheritbench.phase3b.publication import finalize_distribution

    path = finalize_distribution(experiment)
    console.print(f"[green]Phase 3B distribution decision frozen[/green] {path}")


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


@day3_matched_app.command("validate-configs")
def day3_matched_validate_configs_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.config import load_experiment_config

    load_experiment_config(experiment)
    console.print("[green]validated[/green] isolated Day 3 matched-recovery configs")


@day3_matched_app.command("freeze-baseline")
def day3_matched_freeze_baseline_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.baseline import freeze_baseline

    path = freeze_baseline(experiment)
    console.print(f"[green]historical baseline frozen[/green] {path}")


@day3_matched_app.command("freeze-fingerprint")
def day3_matched_freeze_fingerprint_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.distribution import freeze_fingerprint

    path = freeze_fingerprint(experiment)
    console.print(f"[green]train distribution frozen[/green] {path}")


@day3_matched_app.command("freeze-pool")
def day3_matched_freeze_pool_command(
    pool: Annotated[Literal["initial", "expansion"], typer.Option()] = "initial",
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.distribution import freeze_pool

    path = freeze_pool(experiment, pool)
    console.print(f"[green]{pool} matched pool frozen[/green] {path}")


@day3_matched_app.command("audit-distribution")
def day3_matched_audit_distribution_command(
    pool: Annotated[Literal["initial", "expansion"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.distribution import audit_distribution

    path = audit_distribution(experiment, pool)
    console.print(f"[green]distribution audit passed[/green] {path}")


@day3_matched_app.command("audit-leakage")
def day3_matched_audit_leakage_command(
    pool: Annotated[Literal["initial", "expansion"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.distribution import audit_leakage

    path = audit_leakage(experiment, pool)
    console.print(f"[green]leakage audit passed[/green] {path}")


@day3_matched_app.command("verify-teacher")
def day3_matched_verify_teacher_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.teacher import verify_teacher

    path = verify_teacher(experiment)
    console.print(f"[green]matched teacher reference verified[/green] {path}")


@day3_matched_app.command("run-teacher")
def day3_matched_run_teacher_command(
    pool: Annotated[Literal["initial", "expansion"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
    resume: Annotated[
        Path | None,
        typer.Option(exists=True, file_okay=False, help="Resume one failed matched run."),
    ] = None,
) -> None:
    from inheritbench.day3_matched.teacher import run_teacher

    path = run_teacher(experiment, pool, device=device, resume_run=resume)
    console.print(f"[green]matched teacher run finalized[/green] {path}")


@day3_matched_app.command("filter")
def day3_matched_filter_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.filtering import filter_teacher_outputs

    dataset, evidence = filter_teacher_outputs(experiment)
    console.print(f"[green]matched filter finalized[/green] {dataset} · {evidence}")


@day3_matched_app.command("expand-pool")
def day3_matched_expand_pool_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.distribution import freeze_pool
    from inheritbench.day3_matched.filtering import find_synthetic_dataset

    _, dataset = find_synthetic_dataset(experiment, require_completed=False)
    if dataset.status != "NEEDS_EXPANSION":
        raise typer.BadParameter("expansion requires an insufficient initial matched filter")
    path = freeze_pool(experiment, "expansion")
    console.print(f"[yellow]matched expansion pool frozen[/yellow] {path}")


@day3_matched_app.command("freeze-schedule")
def day3_matched_freeze_schedule_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.filtering import freeze_schedule

    path = freeze_schedule(experiment)
    console.print(f"[green]matched schedule frozen[/green] {path}")


@day3_matched_app.command("train")
def day3_matched_train_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
    resume: Annotated[
        Path | None,
        typer.Option(exists=True, file_okay=False, help="Resume from a matched checkpoint."),
    ] = None,
) -> None:
    from inheritbench.day3_matched.training import train_method

    training, decision = train_method(experiment, device=device, resume_checkpoint=resume)
    console.print(f"[green]matched training finalized[/green] {training} · {decision}")


@day3_matched_app.command("recover")
def day3_matched_recover_command(
    active_run: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    mark_failed: Annotated[bool, typer.Option("--mark-failed")] = False,
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    if not mark_failed:
        raise typer.BadParameter("matched recovery requires --mark-failed")
    from inheritbench.day3_matched.config import load_experiment_config, resolve

    config = load_experiment_config(experiment)
    failed_root = resolve(experiment, config.artifact_root) / "failed"
    if (active_run / "active.json").is_file():
        from inheritbench.day3_matched.training import recover_active as recover_training

        path = recover_training(active_run, failed_root)
    else:
        from inheritbench.day3_matched.teacher import recover_active as recover_teacher

        path = recover_teacher(active_run, failed_root)
    console.print(f"[yellow]matched run recovered as failed[/yellow] {path}")


@day3_matched_app.command("evaluate")
def day3_matched_evaluate_command(
    split: Annotated[Literal["validation", "test"], typer.Option()],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
    device: Annotated[Literal["auto", "mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.day3_matched.evaluation import evaluate_method

    path = evaluate_method(experiment, split, device=device)
    console.print(f"[green]matched {split} evaluation finalized[/green] {path}")


@day3_matched_app.command("select-checkpoint")
def day3_matched_select_checkpoint_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
    device: Annotated[Literal["mps", "cpu", "cuda"], typer.Option()] = "mps",
) -> None:
    from inheritbench.day3_matched.training import select_checkpoints

    path = select_checkpoints(experiment, device=device)
    console.print(f"[green]matched checkpoint decision frozen[/green] {path}")


@day3_matched_app.command("replay")
def day3_matched_replay_command(
    kind: Annotated[
        Literal[
            "fingerprint",
            "distribution",
            "leakage",
            "teacher",
            "filter",
            "schedule",
            "training",
            "evaluation",
            "failure_analysis",
            "attempt_comparison",
            "method_comparison",
            "recovery_decision",
        ],
        typer.Option(),
    ],
    artifact: Annotated[Path, typer.Option(exists=True)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.lifecycle import replay_artifact

    path = replay_artifact(experiment, kind, artifact)
    console.print(f"[green]matched {kind} replay passed[/green] {path}")


@day3_matched_app.command("analyze-failures")
def day3_matched_analyze_failures_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.lifecycle import analyze_failures

    path = analyze_failures(experiment)
    console.print(f"[green]matched failure analysis finalized[/green] {path}")


@day3_matched_app.command("compare-attempts")
def day3_matched_compare_attempts_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.lifecycle import build_attempt_comparison

    path = build_attempt_comparison(experiment)
    console.print(f"[green]synthetic attempts compared[/green] {path}")


@day3_matched_app.command("compare-methods")
def day3_matched_compare_methods_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.lifecycle import build_method_comparison

    path = build_method_comparison(experiment)
    console.print(f"[green]six method rows compared[/green] {path}")


@day3_matched_app.command("finalize-recovery")
def day3_matched_finalize_recovery_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
    blocked_reason: Annotated[str | None, typer.Option()] = None,
) -> None:
    from inheritbench.day3_matched.lifecycle import finalize_recovery

    path = finalize_recovery(experiment, blocked_reason=blocked_reason)
    console.print(f"[green]matched recovery decision finalized[/green] {path}")


@day3_matched_app.command("package-adapter")
def day3_matched_package_adapter_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.publication import package_adapter

    path = package_adapter(experiment)
    console.print(f"[green]matched adapter packaged[/green] {path}")


@day3_matched_app.command("verify-release")
def day3_matched_verify_release_command(
    publication: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.config import load_experiment_config, resolve
    from inheritbench.day3_matched.publication import verify_release

    config = load_experiment_config(experiment)
    path = verify_release(publication, resolve(experiment, config.artifact_root) / "publications")
    console.print(f"[green]matched release verification finalized[/green] {path}")


@day3_matched_app.command("finalize-distribution")
def day3_matched_finalize_distribution_command(
    experiment: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "configs/experiments/day3_matched.yaml"
    ),
) -> None:
    from inheritbench.day3_matched.lifecycle import finalize_distribution

    path = finalize_distribution(experiment)
    console.print(f"[green]matched distribution decision finalized[/green] {path}")


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
