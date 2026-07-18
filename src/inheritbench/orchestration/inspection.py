"""Human and JSON inspection of generic succession runs."""

from __future__ import annotations

import json
from pathlib import Path

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.orchestration.schemas import (
    InterventionWebBundle,
    RunInspection,
    StageManifest,
)
from inheritbench.orchestration.storage import load_plan


def inspect_run(run_directory: Path) -> RunInspection:
    run_directory = run_directory.resolve()
    plan = load_plan(run_directory)
    stages = [
        StageManifest.model_validate_json(path.read_text(encoding="utf-8"), strict=True)
        for path in sorted((run_directory / "stages").glob("*/stage.json"))
    ]
    current = "CREATED" if not stages else stages[-1].stage
    intervention = None
    if current == "ANCHORS_REQUIRED":
        intervention = stages[-1].payload["supervision"]
    readiness = None
    path = run_directory / "readiness_report.json"
    if path.is_file():
        readiness = json.loads(path.read_text(encoding="utf-8"))
        if current == "COMPLETED" and readiness.get("status") == "MIGRATION_BLOCKED":
            current = "MIGRATION_BLOCKED"
    return RunInspection(
        run_id=plan.run_id,
        current_state=current,
        capability=f"{plan.capability_id}@{plan.capability_version}",
        strategy=plan.strategy_id,
        stages=[stage.stage for stage in stages],
        intervention=intervention,
        readiness=readiness,
        replay_command=f"inheritbench succession replay --run {run_directory}",
    )


def build_intervention_web_bundle(run_directory: Path) -> InterventionWebBundle:
    inspection = inspect_run(run_directory)
    if inspection.current_state != "ANCHORS_REQUIRED" or inspection.intervention is None:
        raise ValueError("run is not waiting for anchor intervention")
    payload = {
        "schema_version": "inheritbench.intervention-web-bundle.v0.2",
        "run_id": inspection.run_id,
        "capability": {
            "id": inspection.capability.split("@", 1)[0],
            "version": inspection.capability.split("@", 1)[1],
        },
        "strategy": inspection.strategy,
        "state": "ANCHORS_REQUIRED",
        "intervention": inspection.intervention,
        "stages": inspection.stages,
    }
    payload["content_sha256"] = content_sha256(payload)
    return InterventionWebBundle.model_validate(payload, strict=True)
