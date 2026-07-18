"""Bounded four-seed anchored recovery execution and model-free replay."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_file,
)
from inheritbench.artifacts.store import write_atomic_directory, write_atomic_file
from inheritbench.capability.loader import LoadedCapabilityPack, load_capability_pack
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    CapabilityOracleRecord,
    StrategyProfile,
)
from inheritbench.config import ModelConfig, load_model_config
from inheritbench.model_adapters.registry import default_registry
from inheritbench.model_adapters.schemas import TrainingResult, TrainingSchedule
from inheritbench.orchestration.evaluation import (
    checkpoint_decision,
    evaluate_generations,
    summarize,
)
from inheritbench.orchestration.executor import (
    _write_or_verify_json,
    _write_or_verify_jsonl,
)
from inheritbench.orchestration.readiness import derive_readiness
from inheritbench.orchestration.schemas import EvaluationRecord, SurfaceSummary
from inheritbench.reference_packs.integrity import REPOSITORY_ROOT
from inheritbench.reference_packs.multistart_protocol import (
    CANDIDATE_RANKING,
    CROSSWALK_PATH,
    DEFAULT_AMENDMENT_PATH,
    DEFAULT_SEED_PATH,
    verify_bounded_multistart_amendment,
    verify_bounded_multistart_seeds,
)
from inheritbench.reference_packs.multistart_surfaces import (
    DEFAULT_OUTPUT as FINAL_SURFACE_ROOT,
)
from inheritbench.reference_packs.multistart_surfaces import verify_final_surfaces
from inheritbench.strategies.schemas import SupervisionAccounting

REFERENCE_ANCHORED_RUN = REPOSITORY_ROOT / (
    "runs/reference/succession-opsroute-anchored-behavioral-transfer-v0.1-00-ee7a07404b124c1b"
)
CORRECTED_DIRECT_RUN = REPOSITORY_ROOT / (
    "runs/reproducibility/succession-opsroute-direct-target-lora-v0.1-03-8795423ea3013599"
)
PACK_ROOT = REPOSITORY_ROOT / "capabilities/opsroute/v0.2.0"
SOURCE_CONFIG_PATH = REPOSITORY_ROOT / "configs/models/source.yaml"
TARGET_CONFIG_PATH = REPOSITORY_ROOT / "configs/models/target.yaml"
RUNS_ROOT = REPOSITORY_ROOT / "runs/reference"
OPERATIONAL_FIELDS = (
    "decision",
    "tool",
    "arguments",
    "approval_required",
    "reason_code",
)
EXPECTED_CANDIDATES = 4
GUARD_REPAIR_ID = "bounded-multistart-guard-repair-v0.1"
GUARD_REPAIR_PATH = (
    REPOSITORY_ROOT / "artifacts/protocol-amendments/bounded-multistart-guard-repair-v0.1.json"
)
READINESS_AUDIT_ROOT = REPOSITORY_ROOT / "runs/audits/readiness-and-instability"


def _candidate_root(run_directory: Path) -> Path:
    repaired = run_directory / "corrected-candidates"
    return repaired if repaired.exists() else run_directory / "candidates"


def _candidate_execution_id(run_directory: Path, plan: dict[str, Any], index: int) -> str:
    prefix = (
        run_directory.name
        if (run_directory / "guard_repair_lineage.json").is_file()
        else plan["canonical_multistart_plan_id"]
    )
    return f"{prefix}-candidate-{index}"


def freeze_multistart_plan(output_root: Path = RUNS_ROOT) -> Path:
    amendment = verify_bounded_multistart_amendment(DEFAULT_AMENDMENT_PATH)
    seeds = verify_bounded_multistart_seeds(DEFAULT_SEED_PATH)
    surfaces = verify_final_surfaces(FINAL_SURFACE_ROOT)
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    profile = _anchored_profile(pack)
    supervision = _supervision_records()
    schedule = _schedule()
    _validate_frozen_training_inputs(supervision, schedule, profile)
    canonical: dict[str, Any] = {
        "schema_version": "inheritbench.bounded-multistart-plan.v0.1",
        "amendment_id": amendment["amendment_id"],
        "amendment_sha256": amendment["content_sha256"],
        "seed_manifest_sha256": seeds["content_sha256"],
        "candidate_count": EXPECTED_CANDIDATES,
        "candidate_seeds": seeds["candidates"],
        "capability": {
            "id": pack.config.capability.id,
            "version": pack.config.capability.version,
            "pack_validation_sha256": pack.validation.content_sha256,
            "pack_root_sha256": amendment["capability_pack_root_sha256"],
        },
        "source": _model_binding(SOURCE_CONFIG_PATH, pack.config.models.source_registry_ids[0]),
        "target": _model_binding(TARGET_CONFIG_PATH, pack.config.models.target_registry_ids[0]),
        "strategy_id": profile.strategy_id,
        "supervision": {
            "records": len(supervision),
            "teacher_labels": sum(item.label_origin == "teacher" for item in supervision),
            "anchor_labels": sum(item.label_origin == "anchor" for item in supervision),
            "records_sha256": content_sha256([item.content_sha256 for item in supervision]),
            "ordered_record_ids_sha256": content_sha256([item.record_id for item in supervision]),
            "parent_stage_byte_sha256": sha256_file(
                REFERENCE_ANCHORED_RUN / "stages/09-supervision_frozen/stage.json"
            ),
        },
        "schedule": {
            "byte_sha256": sha256_file(REFERENCE_ANCHORED_RUN / "schedule_manifest.json"),
            "content_sha256": schedule.content_sha256,
            "order_sha256": schedule.order_sha256,
            "exposures": len(schedule.items),
            "processed_tokens": schedule.processed_tokens,
            "optimizer_steps": schedule.optimizer_steps,
            "checkpoint_steps": schedule.checkpoint_steps,
        },
        "training_profile": profile.training.model_dump(mode="json"),
        "recovery_validation": {
            "inputs_byte_sha256": sha256_file(PACK_ROOT / "data/validation.inputs.jsonl"),
            "oracles_byte_sha256": sha256_file(PACK_ROOT / "oracles/validation.jsonl"),
            "records": len(pack.inputs["validation"]),
            "checkpoint_policy": profile.checkpoint_policy.model_dump(mode="json"),
        },
        "candidate_ranking": CANDIDATE_RANKING,
        "candidate_ranking_operational_fields": list(OPERATIONAL_FIELDS),
        "final_surfaces": {
            "manifest_sha256": surfaces["content_sha256"],
            "confirmatory_inputs_root_sha256": surfaces["confirmatory"]["inputs_root_sha256"],
            "confirmatory_oracles_root_sha256": surfaces["confirmatory"]["oracles_root_sha256"],
            "adversarial_inputs_root_sha256": surfaces["adversarial"]["inputs_root_sha256"],
            "adversarial_oracles_root_sha256": surfaces["adversarial"]["oracles_root_sha256"],
            "candidate_access": "PROHIBITED_UNTIL_SELECTED_CANDIDATE_FROZEN",
        },
        "readiness_contract": {
            "byte_sha256": sha256_file(PACK_ROOT / "rules/readiness.yaml"),
            "rules": pack.readiness_rules,
        },
        "generation": {
            "device": "mps",
            "dtype": "float16",
            "batch_size": 1,
            "greedy": True,
            "maximum_new_tokens": pack.config.prompt.maximum_new_tokens,
            "seed": pack.config.seed,
        },
        "export_and_replay_required": True,
        "historical_artifacts_mutated": False,
    }
    canonical_sha256 = content_sha256(canonical)
    canonical_plan_id = f"anchored-multistart-{canonical_sha256[:16]}"
    plan = {
        **canonical,
        "canonical_multistart_plan_id": canonical_plan_id,
        "canonical_multistart_plan_sha256": canonical_sha256,
    }
    run_directory = output_root / canonical_plan_id
    if run_directory.exists():
        verify_multistart_plan(run_directory)
        return run_directory

    def build(staging: Path) -> None:
        _raw_json(staging / "canonical_plan.json", plan)
        (staging / "canonical_plan.sha256").write_text(canonical_sha256 + "\n", encoding="utf-8")
        _raw_json(
            staging / "protocol_amendment_reference.json",
            _reference(DEFAULT_AMENDMENT_PATH, amendment["content_sha256"]),
        )
        crosswalk = _json(CROSSWALK_PATH)
        _raw_json(
            staging / "metric_identity_crosswalk_reference.json",
            _reference(CROSSWALK_PATH, crosswalk["content_sha256"]),
        )
        _raw_json(staging / "seed_manifest.json", seeds)
        _raw_json(staging / "fresh_surface_manifest.json", surfaces)
        _raw_json(
            staging / "final_surface_sealing_receipt.json",
            {
                "schema_version": "inheritbench.final-surface-sealing.v0.1",
                "status": "FRESH_FINAL_SURFACES_FROZEN",
                "surface_manifest_sha256": surfaces["content_sha256"],
                "amendment_sha256": amendment["content_sha256"],
                "seed_manifest_sha256": seeds["content_sha256"],
                "candidate_training_artifacts_present_at_seal": False,
                "selected_candidate_present_at_seal": False,
                "candidate_training_access_to_final_inputs": False,
                "candidate_training_access_to_final_oracles": False,
                "candidate_ranking_access_to_final_inputs": False,
                "candidate_ranking_access_to_final_oracles": False,
            },
        )
        _raw_json(
            staging / "candidate_ranking_policy.json",
            {
                "schema_version": "inheritbench.multistart-ranking-policy.v0.1",
                "status": "PROSPECTIVE_CONTENT_FROZEN",
                "order": CANDIDATE_RANKING,
                "operational_fields": list(OPERATIONAL_FIELDS),
                "policy_code_excluded_from_operational_semantic": True,
                "final_surface_fields_permitted": False,
            },
        )
        (staging / "candidates").mkdir()

    write_atomic_directory(run_directory, build)
    verify_multistart_plan(run_directory)
    return run_directory


def freeze_repaired_multistart_plan(output_root: Path = RUNS_ROOT) -> Path:
    """Freeze execution-only repair lineage around the unchanged canonical plan."""

    original = freeze_multistart_plan(output_root)
    plan = verify_multistart_plan(original)
    amendment = verify_bounded_multistart_amendment(DEFAULT_AMENDMENT_PATH)
    audit_manifest = _json(READINESS_AUDIT_ROOT / "audit_manifest.json")
    source_path = REPOSITORY_ROOT / "src/inheritbench/model_adapters/huggingface.py"
    test_path = REPOSITORY_ROOT / "tests/unit/test_numerical_guard.py"
    repair = {
        "schema_version": "inheritbench.execution-engine-repair.v0.1",
        "repair_id": GUARD_REPAIR_ID,
        "parent_amendment_id": amendment["amendment_id"],
        "parent_amendment_hash": amendment["content_sha256"],
        "classification": "IMPLEMENTATION_DEFECT_REPAIR",
        "defect": "FINITE_PRECLIP_GRADIENT_NORM_MISCLASSIFIED_AS_NUMERICAL_INSTABILITY",
        "scientific_protocol_changed": False,
        "candidate_seeds_changed": False,
        "supervision_changed": False,
        "schedule_changed": False,
        "optimizer_changed": False,
        "learning_rate_changed": False,
        "training_budget_changed": False,
        "ranking_policy_changed": False,
        "readiness_contract_changed": False,
        "final_surfaces_changed": False,
        "previous_guard_predicate_sha256": content_sha256(
            {
                "operation_order": [
                    "clip_grad_norm_",
                    "reject finite norm above 100",
                    "optimizer_step",
                ],
                "predicate": "not isfinite(gradient_norm) or gradient_norm > 100",
            }
        ),
        "corrected_source_sha256": sha256_file(source_path),
        "regression_test_sha256": sha256_file(test_path),
        "forensic_audit_sha256": audit_manifest["content_sha256"],
        "repository_head": _git_value("rev-parse", "HEAD"),
        "dirty_worktree_sha256": _dirty_worktree_sha256(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    repair["content_sha256"] = content_sha256(repair)
    if GUARD_REPAIR_PATH.exists():
        stored_repair = _json(GUARD_REPAIR_PATH)
        invariant_fields = {
            key: value
            for key, value in repair.items()
            if key not in {"created_at", "dirty_worktree_sha256", "content_sha256"}
        }
        stored_invariants = {
            key: value
            for key, value in stored_repair.items()
            if key not in {"created_at", "dirty_worktree_sha256", "content_sha256"}
        }
        if stored_invariants != invariant_fields:
            raise ValueError("guard repair lineage already exists with different invariants")
        repair = stored_repair
    else:
        write_atomic_file(GUARD_REPAIR_PATH, canonical_json_bytes(repair) + b"\n")
    run_directory = output_root / f"anchored-multistart-repaired-{repair['content_sha256'][:16]}"
    if run_directory.exists():
        sidecar = run_directory / "canonical_plan.sha256"
        if not sidecar.exists():
            write_atomic_file(
                sidecar,
                f"{plan['canonical_multistart_plan_sha256']}\n".encode(),
            )
        verify_multistart_plan(run_directory)
        return run_directory

    def build(staging: Path) -> None:
        for source_name, target_name in (
            ("canonical_plan.json", "canonical_plan.json"),
            ("canonical_plan.json", "canonical_plan_reference.json"),
            ("canonical_plan.sha256", "canonical_plan.sha256"),
            ("protocol_amendment_reference.json", "protocol_amendment_reference.json"),
            ("seed_manifest.json", "seed_manifest.json"),
            ("fresh_surface_manifest.json", "fresh_surface_reference.json"),
            ("candidate_ranking_policy.json", "candidate_ranking_policy.json"),
            (
                "metric_identity_crosswalk_reference.json",
                "metric_identity_crosswalk_reference.json",
            ),
        ):
            shutil.copy2(original / source_name, staging / target_name)
        _raw_json(staging / "guard_repair_lineage.json", repair)
        _raw_json(
            staging / "readiness_contract_reference.json",
            {
                "relative_path": "capabilities/opsroute/v0.2.0/rules/readiness.yaml",
                "sha256": plan["readiness_contract"]["byte_sha256"],
                "version": plan["readiness_contract"]["rules"]["version"],
            },
        )
        _raw_json(
            staging / "guard_repair_preflight.json",
            {
                "schema_version": "inheritbench.guard-repair-preflight.v0.1",
                "status": "NUMERICAL_GUARD_REPAIR_PREFLIGHT_PASS",
                "repair_lineage_sha256": repair["content_sha256"],
                "finite_large_preclip_allowed": True,
                "configured_clipping_applied": True,
                "pre_post_clip_telemetry_separate": True,
                "nonfinite_loss_gradient_parameter_optimizer_rejected": True,
                "scientific_protocol_changed": False,
            },
        )
        decisions = {
            "schema_version": "inheritbench.multistart-resume-decisions.v0.1",
            "policy": "PREFER_RESTART_WHEN_ANY_UNCERTAINTY_EXISTS",
            "candidates": [
                {
                    "candidate_index": index,
                    "decision": "RESTART_REQUIRED",
                    "checkpoint_used": None,
                    "starting_optimizer_step": 0,
                    "reason": (
                        "No checkpoint exists before checkpoint 56."
                        if index < 2
                        else (
                            "Step-56 checkpoint is finite but lacks a terminal-step "
                            "gradient/accumulation receipt under the repaired guard."
                        )
                    ),
                    "prior_failed_execution": (
                        f"anchored-multistart-b0b3b78e5354a40b-candidate-{index}"
                    ),
                }
                for index in range(EXPECTED_CANDIDATES)
            ],
        }
        decisions["content_sha256"] = content_sha256(decisions)
        _raw_json(staging / "candidate_resume_decisions.json", decisions)
        (staging / "corrected-candidates").mkdir()

    write_atomic_directory(run_directory, build)
    verify_multistart_plan(run_directory)
    return run_directory


def verify_multistart_plan(run_directory: Path) -> dict[str, Any]:
    plan = _json(run_directory / "canonical_plan.json")
    stored = str(plan["canonical_multistart_plan_sha256"])
    unsigned = dict(plan)
    unsigned.pop("canonical_multistart_plan_id", None)
    unsigned.pop("canonical_multistart_plan_sha256", None)
    if content_sha256(unsigned) != stored:
        raise ValueError("canonical multi-start plan hash mismatch")
    if (run_directory / "canonical_plan.sha256").read_text().strip() != stored:
        raise ValueError("canonical multi-start plan sidecar mismatch")
    amendment = verify_bounded_multistart_amendment(DEFAULT_AMENDMENT_PATH)
    seeds = verify_bounded_multistart_seeds(DEFAULT_SEED_PATH)
    surfaces = verify_final_surfaces(FINAL_SURFACE_ROOT)
    if plan["amendment_sha256"] != amendment["content_sha256"]:
        raise ValueError("multi-start plan amendment binding mismatch")
    if plan["seed_manifest_sha256"] != seeds["content_sha256"]:
        raise ValueError("multi-start plan seed binding mismatch")
    if plan["final_surfaces"]["manifest_sha256"] != surfaces["content_sha256"]:
        raise ValueError("multi-start plan final-surface binding mismatch")
    if plan["candidate_ranking"] != CANDIDATE_RANKING:
        raise ValueError("multi-start ranking-policy drift")
    return plan


def preflight_multistart_candidates(
    run_directory: Path,
    *,
    device: str = "mps",
) -> list[Path]:
    plan = verify_multistart_plan(run_directory)
    if list(_candidate_root(run_directory).glob("*/training_trajectory.json")):
        raise ValueError("candidate preflight cannot run after training begins")
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    profile = _anchored_profile(pack)
    target_config = load_model_config(TARGET_CONFIG_PATH)
    target_adapter = default_registry().resolve(
        pack.config.models.target_registry_ids[0], target_config
    )
    supervision = _supervision_records()
    schedule = _schedule()
    encoding = target_adapter.training_encoding_manifest(target_config, supervision)
    encoding_sha256 = content_sha256(encoding)
    plan_projection = {
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "canonical_multistart_plan_sha256": plan["canonical_multistart_plan_sha256"],
        "target_model": plan["target"],
        "strategy_id": plan["strategy_id"],
        "supervision": plan["supervision"],
        "schedule": plan["schedule"],
        "training_profile": plan["training_profile"],
        "recovery_validation": plan["recovery_validation"],
        "candidate_ranking": plan["candidate_ranking"],
        "generation": plan["generation"],
        "final_surface_hashes_known_but_data_accessible": False,
    }
    invariant_sha256 = content_sha256(plan_projection)
    candidates: list[Path] = []
    initial_hashes: set[str] = set()
    for candidate in verify_bounded_multistart_seeds(DEFAULT_SEED_PATH)["candidates"]:
        index = int(candidate["candidate_index"])
        seed = int(candidate["initialization_seed"])
        candidate_directory = _candidate_root(run_directory) / f"candidate-{index}"
        candidate_directory.mkdir(exist_ok=True)
        initialization = target_adapter.training_initialization(
            target_config,
            profile.training,
            device=device,
            seed=seed,
        )
        if initialization.initial_adapter_sha256 in initial_hashes:
            raise ValueError("candidate initial adapter hashes must be unique")
        initial_hashes.add(initialization.initial_adapter_sha256)
        candidate_plan = {
            **plan_projection,
            "candidate_execution_id": _candidate_execution_id(run_directory, plan, index),
            "candidate_index": index,
            "initialization_seed": seed,
            "candidate_invariant_sha256": invariant_sha256,
        }
        preflight = {
            "schema_version": "inheritbench.multistart-candidate-preflight.v0.1",
            "status": (
                "MULTISTART_CANDIDATE_REPAIR_PREFLIGHT_PASS"
                if (run_directory / "guard_repair_lineage.json").is_file()
                else "MULTISTART_CANDIDATE_PREFLIGHT_PASS"
            ),
            "candidate_index": index,
            "initialization_seed": seed,
            "initial_adapter_sha256": initialization.initial_adapter_sha256,
            "rng_hashes": {
                "before_model_load": initialization.rng_before_model_load_sha256,
                "before_lora": initialization.rng_before_lora_sha256,
                "after_lora": initialization.rng_after_lora_sha256,
            },
            "trainable_parameter_names": initialization.trainable_parameter_names,
            "trainable_parameter_shapes": initialization.trainable_parameter_shapes,
            "trainable_parameters": initialization.trainable_parameters,
            "total_parameters": initialization.total_parameters,
            "candidate_invariant_sha256": invariant_sha256,
            "encoding_sha256": encoding_sha256,
            "schedule_sha256": schedule.content_sha256,
            "supervision_sha256": plan["supervision"]["records_sha256"],
            "final_surface_inputs_or_oracles_accessed": False,
        }
        _write_or_verify_json(candidate_directory / "plan_projection.json", candidate_plan)
        if (run_directory / "guard_repair_lineage.json").is_file():
            _write_or_verify_json(
                candidate_directory / "execution_identity.json",
                {
                    "candidate_index": index,
                    "execution_id": candidate_plan["candidate_execution_id"],
                    "canonical_plan_id": plan["canonical_multistart_plan_id"],
                    "repair_lineage_sha256": _json(run_directory / "guard_repair_lineage.json")[
                        "content_sha256"
                    ],
                },
            )
            resume = _json(run_directory / "candidate_resume_decisions.json")
            decision = next(
                item for item in resume["candidates"] if item["candidate_index"] == index
            )
            _write_or_verify_json(candidate_directory / "resume_or_restart_manifest.json", decision)
        _write_or_verify_json(candidate_directory / "parity_preflight.json", preflight)
        _write_or_verify_json(
            candidate_directory / "initialization_manifest.json",
            initialization.model_dump(mode="json"),
        )
        _write_or_verify_json(
            candidate_directory / "rng_manifest.json",
            {
                "seed": seed,
                "before_model_load": initialization.rng_before_model_load_sha256,
                "before_lora": initialization.rng_before_lora_sha256,
                "after_lora": initialization.rng_after_lora_sha256,
            },
        )
        _write_or_verify_json(
            candidate_directory / "schedule_manifest.json",
            schedule.model_dump(mode="json"),
        )
        _write_or_verify_json(
            candidate_directory / "encoding_manifest.json",
            {
                "records": encoding,
                "content_sha256": encoding_sha256,
            },
        )
        candidates.append(candidate_directory)
    _verify_candidate_preflights(run_directory)
    return candidates


def train_multistart_candidates(
    run_directory: Path,
    *,
    device: str = "mps",
) -> list[Path]:
    plan = verify_multistart_plan(run_directory)
    _verify_candidate_preflights(run_directory)
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    profile = _anchored_profile(pack)
    target_config = load_model_config(TARGET_CONFIG_PATH)
    target_adapter = default_registry().resolve(
        pack.config.models.target_registry_ids[0], target_config
    )
    supervision = _supervision_records()
    schedule = _schedule()
    completed: list[Path] = []
    seeds = verify_bounded_multistart_seeds(DEFAULT_SEED_PATH)["candidates"]
    for candidate in seeds:
        index = int(candidate["candidate_index"])
        seed = int(candidate["initialization_seed"])
        candidate_directory = _candidate_root(run_directory) / f"candidate-{index}"
        trajectory_path = candidate_directory / "training_trajectory.json"
        if trajectory_path.exists():
            _write_partial_checkpoint_evidence(candidate_directory)
            _verify_candidate_terminal(candidate_directory, plan)
            completed.append(candidate_directory)
            continue
        try:
            result = target_adapter.train(
                target_config,
                supervision,
                schedule,
                profile.training,
                device=device,
                run_id=_candidate_execution_id(run_directory, plan, index),
                output_root=candidate_directory / "checkpoints",
                seed=seed,
            )
        except FloatingPointError as exc:
            _write_partial_checkpoint_evidence(candidate_directory)
            _finalize_numerically_failed_candidate(
                candidate_directory,
                index=index,
                seed=seed,
                error=f"{type(exc).__name__}: {exc}",
            )
            _verify_candidate_terminal(candidate_directory, plan)
            completed.append(candidate_directory)
            continue
        if result.status != "COMPLETED":
            raise RuntimeError(f"candidate {index} training failed: {result.error}")
        preflight = _json(candidate_directory / "parity_preflight.json")
        if result.initial_adapter_sha256 != preflight["initial_adapter_sha256"]:
            raise ValueError(f"candidate {index} initialization changed after preflight")
        _write_or_verify_json(
            trajectory_path,
            {
                "schema_version": "inheritbench.multistart-training-trajectory.v0.1",
                "status": "COMPLETED",
                "candidate_index": index,
                "training_result": result.model_dump(mode="json"),
                "failure_code": None,
                "error": None,
            },
        )
        _write_or_verify_json(
            candidate_directory / "numerical_telemetry.json",
            {
                "schema_version": "inheritbench.multistart-numerical-telemetry.v0.1",
                "candidate_index": index,
                "clip_threshold": profile.training.gradient_clip_norm,
                "telemetry": [item.model_dump(mode="json") for item in result.telemetry],
            },
        )
        decision, evaluations = checkpoint_decision(
            pack=pack,
            adapter=target_adapter,
            model_config=target_config,
            checkpoints=result.checkpoints,
            validation_inputs=pack.inputs["validation"],
            validation_oracles=pack.oracles["validation"],
            device=device,
            maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
            seed=pack.config.seed,
            policy=profile.checkpoint_policy,
        )
        _write_or_verify_json(
            candidate_directory / "checkpoint_manifest.json",
            {
                "checkpoints": [item.model_dump(mode="json") for item in result.checkpoints],
                "decision": decision.model_dump(mode="json"),
                "checkpoint_evaluations": {
                    key: [item.model_dump(mode="json") for item in values]
                    for key, values in evaluations.items()
                },
            },
        )
        selected_records = (
            []
            if decision.selected_checkpoint_id is None
            else evaluations[decision.selected_checkpoint_id]
        )
        _write_or_verify_jsonl(
            candidate_directory / "validation_atomic_results.jsonl",
            [item.model_dump(mode="json") for item in selected_records],
        )
        selected_score = next(
            (
                item
                for item in decision.scores
                if item.checkpoint_id == decision.selected_checkpoint_id
            ),
            None,
        )
        validation_summary = _atomic_summary("recovery_validation", selected_records)
        _write_or_verify_json(
            candidate_directory / "validation_summary.json",
            {
                "checkpoint_decision": decision.model_dump(mode="json"),
                "selected_score": (
                    None if selected_score is None else selected_score.model_dump(mode="json")
                ),
                "atomic_summary": validation_summary,
            },
        )
        _write_or_verify_json(
            candidate_directory / "adapter_reference.json",
            {
                "candidate_index": index,
                "checkpoint_id": decision.selected_checkpoint_id,
                "adapter_directory": decision.selected_adapter_directory,
                "adapter_sha256": decision.selected_adapter_sha256,
            },
        )
        _write_or_verify_json(
            candidate_directory / "compute_accounting.json",
            {
                "candidate_index": index,
                "processed_tokens": result.processed_tokens,
                "optimizer_steps": result.optimizer_steps_completed,
                "duration_seconds": result.duration_seconds,
                "validation_model_passes": len(result.checkpoints),
                "training_model_loaded_fresh": True,
                "final_surface_generation_calls": 0,
            },
        )
        _write_or_verify_json(
            candidate_directory / "terminal_status.json",
            {
                "candidate_index": index,
                "status": "COMPLETED",
                "failure_code": None,
                "optimizer_steps": result.optimizer_steps_completed,
                "processed_tokens": result.processed_tokens,
            },
        )
        _write_partial_checkpoint_evidence(candidate_directory)
        _verify_candidate_terminal(candidate_directory, plan)
        completed.append(candidate_directory)
    if len(completed) != EXPECTED_CANDIDATES:
        raise ValueError("all four candidates must complete before ranking")
    return completed


def rank_multistart_candidates(run_directory: Path) -> Path:
    plan = verify_multistart_plan(run_directory)
    if (run_directory / "selected_candidate_receipt.json").exists():
        return run_directory / "multistart_candidate_ranking.json"
    rows: list[dict[str, Any]] = []
    prediction_maps: dict[int, dict[str, str]] = {}
    for index in range(EXPECTED_CANDIDATES):
        candidate_directory = _candidate_root(run_directory) / f"candidate-{index}"
        _verify_candidate_terminal(candidate_directory, plan)
        validation = _json(candidate_directory / "validation_summary.json")
        adapter = _json(candidate_directory / "adapter_reference.json")
        trajectory_document = _json(candidate_directory / "training_trajectory.json")
        training_failed = trajectory_document["status"] == "FAILED"
        atomic = validation["atomic_summary"]
        selected_score = validation["selected_score"]
        eligible = bool(
            not training_failed
            and selected_score is not None
            and selected_score["eligible"]
            and adapter["adapter_sha256"] is not None
        )
        row = {
            "candidate_index": index,
            "initialization_seed": (
                _json(candidate_directory / "parity_preflight.json")["initialization_seed"]
            ),
            "initial_adapter_sha256": (
                _json(candidate_directory / "parity_preflight.json")["initial_adapter_sha256"]
            ),
            "training_status": trajectory_document["status"],
            "failure_code": trajectory_document["failure_code"],
            "error": trajectory_document["error"],
            "safety_eligible": eligible,
            "validation_operational_semantic_correct": (
                None if training_failed else atomic["operational_semantic_correct"]
            ),
            "validation_operational_semantic_rate": (
                None if training_failed else atomic["operational_semantic_rate"]
            ),
            "validation_minimum_group_operational_semantic_rate": (
                None if training_failed else atomic["minimum_group_operational_semantic_rate"]
            ),
            "validation_historical_strict_valid": (
                None if training_failed else atomic["historical_strict_valid"]
            ),
            "validation_mean_declared_field_correctness": (
                None if training_failed else atomic["mean_declared_field_correctness"]
            ),
            "validation_loss": (
                None if selected_score is None else selected_score["validation_loss"]
            ),
            "selected_optimizer_step": (
                None if selected_score is None else selected_score["optimizer_step"]
            ),
            "selected_checkpoint_id": adapter["checkpoint_id"],
            "adapter_sha256": adapter["adapter_sha256"],
            "blocker_safety_findings": (
                None if training_failed else atomic["blocker_safety_findings"]
            ),
            "compute": _json(candidate_directory / "compute_accounting.json"),
        }
        rows.append(row)
        prediction_maps[index] = (
            {}
            if training_failed
            else {
                item["generation"]["record_id"]: str(item["evaluation"].get("parsed_output"))
                for item in _read_jsonl(candidate_directory / "validation_atomic_results.jsonl")
            }
        )
    eligible_rows = [row for row in rows if row["safety_eligible"]]
    selected = max(eligible_rows, key=_candidate_rank) if eligible_rows else None
    ranking = {
        "schema_version": "inheritbench.multistart-candidate-ranking.v0.1",
        "status": ("COMPLETED" if selected is not None else "NO_SAFETY_ELIGIBLE_CANDIDATE"),
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "policy": CANDIDATE_RANKING,
        "final_surface_information_used": False,
        "all_candidates_completed_before_ranking": True,
        "candidates": rows,
        "selected_candidate_index": (None if selected is None else selected["candidate_index"]),
        "selected_candidate_execution_id": (
            None
            if selected is None
            else _candidate_execution_id(run_directory, plan, int(selected["candidate_index"]))
        ),
        "selected_checkpoint_id": (
            None if selected is None else selected["selected_checkpoint_id"]
        ),
        "selected_adapter_sha256": (None if selected is None else selected["adapter_sha256"]),
        "selection_rank_tuple": (None if selected is None else list(_candidate_rank(selected))),
    }
    ranking["content_sha256"] = content_sha256(ranking)
    _write_or_verify_json(run_directory / "multistart_candidate_ranking.json", ranking)
    _write_ranking_markdown(run_directory / "multistart_candidate_ranking.md", ranking)
    stability = _stability_report(rows, prediction_maps)
    _write_or_verify_json(run_directory / "stability_report.json", stability)
    if selected is None:
        finalize_blocked_before_final_evaluation(run_directory)
    return run_directory / "multistart_candidate_ranking.json"


def freeze_selected_candidate(
    run_directory: Path,
    *,
    device: str = "mps",
) -> Path:
    plan = verify_multistart_plan(run_directory)
    ranking = _json(run_directory / "multistart_candidate_ranking.json")
    index = int(ranking["selected_candidate_index"])
    candidate_directory = _candidate_root(run_directory) / f"candidate-{index}"
    adapter_reference = _json(candidate_directory / "adapter_reference.json")
    if adapter_reference["adapter_sha256"] != ranking["selected_adapter_sha256"]:
        raise ValueError("selected candidate adapter binding mismatch")
    target_config = load_model_config(TARGET_CONFIG_PATH)
    target_adapter = default_registry().resolve(plan["target"]["registry_id"], target_config)
    checkpoint_directory = Path(str(adapter_reference["adapter_directory"]))
    identity = target_adapter.verify_adapter(target_config, checkpoint_directory, device=device)
    if identity.adapter_sha256 != ranking["selected_adapter_sha256"]:
        raise ValueError("selected checkpoint fresh-reload hash mismatch")
    successor = run_directory / "successor"
    if not successor.exists():

        def build(staging: Path) -> None:
            for name in ("adapter_config.json", "adapter_model.safetensors"):
                shutil.copy2(checkpoint_directory / name, staging / name)
            _raw_json(
                staging / "lineage.json",
                {
                    "schema_version": "inheritbench.multistart-successor-lineage.v0.1",
                    "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
                    "candidate_index": index,
                    "candidate_execution_id": ranking["selected_candidate_execution_id"],
                    "selected_checkpoint_id": ranking["selected_checkpoint_id"],
                    "adapter_sha256": ranking["selected_adapter_sha256"],
                    "selection_sha256": ranking["content_sha256"],
                },
            )

        write_atomic_directory(successor, build)
    exported_identity = target_adapter.verify_adapter(target_config, successor, device=device)
    if exported_identity.adapter_sha256 != ranking["selected_adapter_sha256"]:
        raise ValueError("exported selected adapter hash mismatch")
    receipt = {
        "schema_version": "inheritbench.selected-candidate-receipt.v0.1",
        "status": "SELECTED_CANDIDATE_FROZEN",
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "candidate_index": index,
        "candidate_execution_id": ranking["selected_candidate_execution_id"],
        "selected_checkpoint_id": ranking["selected_checkpoint_id"],
        "selected_checkpoint_adapter_sha256": ranking["selected_adapter_sha256"],
        "ranking_sha256": ranking["content_sha256"],
        "fresh_base_reload_verified": True,
        "exported_adapter_sha256": exported_identity.adapter_sha256,
        "final_surface_generation_calls_before_freeze": 0,
    }
    receipt["content_sha256"] = content_sha256(receipt)
    _write_or_verify_json(run_directory / "selected_candidate_receipt.json", receipt)
    _write_or_verify_json(
        run_directory / "adapter_reference.json",
        {
            "adapter_directory": str(successor),
            "adapter_sha256": exported_identity.adapter_sha256,
            "checkpoint_id": ranking["selected_checkpoint_id"],
            "model": exported_identity.model_dump(mode="json"),
        },
    )
    return run_directory / "selected_candidate_receipt.json"


def finalize_blocked_before_final_evaluation(run_directory: Path) -> Path:
    plan = verify_multistart_plan(run_directory)
    ranking = _json(run_directory / "multistart_candidate_ranking.json")
    if ranking["status"] != "NO_SAFETY_ELIGIBLE_CANDIDATE":
        raise ValueError("blocked finalization requires no safety-eligible candidate")
    selected_receipt = {
        "schema_version": "inheritbench.selected-candidate-receipt.v0.1",
        "status": "NO_CANDIDATE_SELECTED",
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "candidate_index": None,
        "candidate_execution_id": None,
        "selected_checkpoint_id": None,
        "selected_checkpoint_adapter_sha256": None,
        "ranking_sha256": ranking["content_sha256"],
        "fresh_base_reload_verified": False,
        "exported_adapter_sha256": None,
        "final_surface_generation_calls_before_freeze": 0,
        "reason_code": "NO_SAFETY_ELIGIBLE_MULTISTART_CANDIDATE",
    }
    selected_receipt["content_sha256"] = content_sha256(selected_receipt)
    _write_or_verify_json(run_directory / "selected_candidate_receipt.json", selected_receipt)
    _write_or_verify_json(
        run_directory / "adapter_reference.json",
        {
            "status": "NOT_EXPORTED",
            "adapter_directory": None,
            "adapter_sha256": None,
            "checkpoint_id": None,
            "reason_code": "NO_SAFETY_ELIGIBLE_MULTISTART_CANDIDATE",
        },
    )
    _write_or_verify_json(
        run_directory / "readiness_report.json",
        {
            "schema_version": "inheritbench.multistart-readiness-not-run.v0.1",
            "status": "NOT_RUN",
            "reason_code": "BLOCKED_BEFORE_FINAL_EVALUATION",
            "numeric_scores": None,
            "readiness_contract_changed": False,
        },
    )
    _write_or_verify_json(
        run_directory / "final_comparison.json",
        {
            "schema_version": "inheritbench.multistart-final-comparison.v0.1",
            "status": "NOT_RUN",
            "reason_code": "BLOCKED_BEFORE_FINAL_EVALUATION",
            "direct": None,
            "anchored": None,
            "anchored_minus_direct": None,
            "surface_manifest_sha256": plan["final_surfaces"]["manifest_sha256"],
            "final_surface_generation_calls": 0,
        },
    )
    _write_or_verify_json(
        run_directory / "label_accounting.json",
        SupervisionAccounting.model_validate(
            _json(REFERENCE_ANCHORED_RUN / "stages/09-supervision_frozen/stage.json")["payload"][
                "supervision"
            ]["accounting"],
            strict=True,
        ).model_dump(mode="json"),
    )
    compute = _compute_accounting(run_directory)
    _write_or_verify_json(run_directory / "compute_accounting.json", compute)
    _write_or_verify_json(
        run_directory / "residual_failures.json",
        {
            "schema_version": "inheritbench.multistart-residuals.v0.1",
            "status": "NOT_RUN",
            "reason_code": "BLOCKED_BEFORE_FINAL_EVALUATION",
            "direct": None,
            "anchored": None,
        },
    )
    historical = {
        "schema_version": "inheritbench.multistart-historical-comparison.v0.1",
        "status": "HISTORICAL_BEHAVIORAL_PARITY_NOT_CONFIRMED",
        "reason_code": "PRIMARY_FINAL_EVALUATION_NOT_RUN",
        "historical_surfaces_are_secondary": True,
        "metric_crosswalk_sha256": _json(CROSSWALK_PATH)["content_sha256"],
    }
    historical["content_sha256"] = content_sha256(historical)
    _write_or_verify_json(run_directory / "historical_comparison_report.json", historical)
    replay = _replay_blocked_multistart(run_directory)
    decision = {
        "schema_version": "inheritbench.bounded-multistart-decision.v0.1",
        "classification": "BLOCKED_BEFORE_FINAL_EVALUATION",
        "reason_code": "NO_SAFETY_ELIGIBLE_MULTISTART_CANDIDATE",
        "metric_crosswalk_status": "METRIC_IDENTITY_RESOLVED",
        "fresh_final_surface_status": "FRESH_FINAL_SURFACES_FROZEN",
        "multistart_training_status": "FOUR_TERMINAL_NUMERICAL_FAILURES",
        "selected_candidate_status": "NO_CANDIDATE_SELECTED",
        "candidate_failure_codes": {
            str(row["candidate_index"]): row["failure_code"] for row in ranking["candidates"]
        },
        "readiness": "NOT_RUN",
        "readiness_contract_changed": False,
        "supervision_changed": False,
        "schedule_changed": False,
        "final_surfaces_frozen_before_training": True,
        "candidate_selection_used_recovery_validation_only": True,
        "final_evaluation_exactly_once": False,
        "final_evaluation_calls": 0,
        "replay_verified": replay["status"] == "PASSED",
        "live_generic_teacher_generation_proven": False,
    }
    decision["content_sha256"] = content_sha256(decision)
    _write_or_verify_json(run_directory / "decision.json", decision)
    _write_evidence_manifest(run_directory)
    _write_blocked_web_bundle(
        run_directory,
        plan=plan,
        ranking=ranking,
        decision=decision,
        historical=historical,
        compute=compute,
        replay=replay,
    )
    return run_directory / "decision.json"


def run_locked_final_evaluations(
    run_directory: Path,
    *,
    device: str = "mps",
) -> Path:
    plan = verify_multistart_plan(run_directory)
    selected = _json(run_directory / "selected_candidate_receipt.json")
    if selected.get("status") != "SELECTED_CANDIDATE_FROZEN":
        raise ValueError("selected candidate must be frozen before final evaluation")
    surfaces = verify_final_surfaces(FINAL_SURFACE_ROOT)
    if surfaces["content_sha256"] != plan["final_surfaces"]["manifest_sha256"]:
        raise ValueError("final surface changed after candidate selection")
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    target_config = load_model_config(TARGET_CONFIG_PATH)
    target_adapter = default_registry().resolve(plan["target"]["registry_id"], target_config)
    direct_adapter = Path(
        str(_json(CORRECTED_DIRECT_RUN / "adapter_reference.json")["adapter_directory"])
    )
    anchored_adapter = run_directory / "successor"
    final_inputs = {
        "confirmatory": _read_models(
            FINAL_SURFACE_ROOT / "confirmatory.inputs.jsonl",
            CapabilityInputRecord,
        ),
        "adversarial": _read_models(
            FINAL_SURFACE_ROOT / "adversarial.inputs.jsonl",
            CapabilityInputRecord,
        ),
    }
    final_oracles = {
        "confirmatory": _read_models(
            FINAL_SURFACE_ROOT / "confirmatory.oracles.jsonl",
            CapabilityOracleRecord,
        ),
        "adversarial": _read_models(
            FINAL_SURFACE_ROOT / "adversarial.oracles.jsonl",
            CapabilityOracleRecord,
        ),
    }
    _evaluate_adapter_once(
        run_directory / "direct_final_evaluation",
        role="corrected_direct_baseline",
        adapter_directory=direct_adapter,
        adapter=target_adapter,
        config=target_config,
        pack=pack,
        inputs=final_inputs,
        oracles=final_oracles,
        device=device,
        seed=pack.config.seed,
        surface_manifest_sha256=surfaces["content_sha256"],
        selected_candidate_sha256=None,
    )
    _evaluate_adapter_once(
        run_directory / "anchored_final_evaluation",
        role="selected_anchored_candidate",
        adapter_directory=anchored_adapter,
        adapter=target_adapter,
        config=target_config,
        pack=pack,
        inputs=final_inputs,
        oracles=final_oracles,
        device=device,
        seed=pack.config.seed,
        surface_manifest_sha256=surfaces["content_sha256"],
        selected_candidate_sha256=selected["content_sha256"],
    )
    return finalize_multistart_result(run_directory)


def finalize_multistart_result(run_directory: Path) -> Path:
    plan = verify_multistart_plan(run_directory)
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    selected = _json(run_directory / "selected_candidate_receipt.json")
    adapter_reference = _json(run_directory / "adapter_reference.json")
    direct = _json(run_directory / "direct_final_evaluation/evaluation_summary.json")
    anchored = _json(run_directory / "anchored_final_evaluation/evaluation_summary.json")
    reference_summary = _json(REFERENCE_ANCHORED_RUN / "evaluation_summary.json")
    source_gate = SurfaceSummary.model_validate(reference_summary["source_gate"], strict=True)
    target_baseline = SurfaceSummary.model_validate(
        reference_summary["target_baseline"], strict=True
    )
    supervision_accounting = SupervisionAccounting.model_validate(
        _json(REFERENCE_ANCHORED_RUN / "stages/09-supervision_frozen/stage.json")["payload"][
            "supervision"
        ]["accounting"],
        strict=True,
    )
    anchored_readiness = derive_readiness(
        run_id=plan["canonical_multistart_plan_id"],
        rules=pack.readiness_rules,
        source_gate=source_gate,
        target_baseline=target_baseline,
        confirmatory=SurfaceSummary.model_validate(
            anchored["generic_summary"]["confirmatory"], strict=True
        ),
        adversarial=SurfaceSummary.model_validate(
            anchored["generic_summary"]["adversarial"], strict=True
        ),
        supervision=supervision_accounting,
        selected_checkpoint_id=str(selected["selected_checkpoint_id"]),
        adapter_sha256=str(adapter_reference["adapter_sha256"]),
    )
    direct_adapter = _json(CORRECTED_DIRECT_RUN / "adapter_reference.json")
    direct_readiness = derive_readiness(
        run_id=f"{plan['canonical_multistart_plan_id']}-direct-control",
        rules=pack.readiness_rules,
        source_gate=source_gate,
        target_baseline=target_baseline,
        confirmatory=SurfaceSummary.model_validate(
            direct["generic_summary"]["confirmatory"], strict=True
        ),
        adversarial=SurfaceSummary.model_validate(
            direct["generic_summary"]["adversarial"], strict=True
        ),
        supervision=supervision_accounting,
        selected_checkpoint_id=str(direct_adapter["checkpoint_id"]),
        adapter_sha256=str(direct_adapter["adapter_sha256"]),
    )
    _write_or_verify_json(
        run_directory / "direct_final_evaluation/readiness_report.json",
        direct_readiness.model_dump(mode="json"),
    )
    _write_or_verify_json(
        run_directory / "readiness_report.json",
        anchored_readiness.model_dump(mode="json"),
    )
    comparison = {
        "schema_version": "inheritbench.multistart-final-comparison.v0.1",
        "surface_manifest_sha256": plan["final_surfaces"]["manifest_sha256"],
        "direct": {
            "adapter_sha256": direct_adapter["adapter_sha256"],
            "metrics": direct["atomic_summary"],
            "readiness": direct_readiness.status,
            "readiness_reason_codes": direct_readiness.reason_codes,
        },
        "anchored": {
            "adapter_sha256": adapter_reference["adapter_sha256"],
            "metrics": anchored["atomic_summary"],
            "readiness": anchored_readiness.status,
            "readiness_reason_codes": anchored_readiness.reason_codes,
        },
        "anchored_minus_direct": _metric_delta(
            anchored["atomic_summary"], direct["atomic_summary"]
        ),
        "readiness_contract_changed": False,
    }
    comparison["content_sha256"] = content_sha256(comparison)
    _write_or_verify_json(run_directory / "final_comparison.json", comparison)
    _write_or_verify_json(
        run_directory / "label_accounting.json",
        supervision_accounting.model_dump(mode="json"),
    )
    compute = _compute_accounting(run_directory)
    _write_or_verify_json(run_directory / "compute_accounting.json", compute)
    _write_or_verify_json(
        run_directory / "residual_failures.json",
        {
            "schema_version": "inheritbench.multistart-residuals.v0.1",
            "direct": _residuals(
                _read_jsonl(
                    run_directory / "direct_final_evaluation/confirmatory.atomic-results.jsonl"
                ),
                _read_jsonl(
                    run_directory / "direct_final_evaluation/adversarial.atomic-results.jsonl"
                ),
            ),
            "anchored": _residuals(
                _read_jsonl(
                    run_directory / "anchored_final_evaluation/confirmatory.atomic-results.jsonl"
                ),
                _read_jsonl(
                    run_directory / "anchored_final_evaluation/adversarial.atomic-results.jsonl"
                ),
            ),
        },
    )
    replay_multistart_result(run_directory)
    replay = _json(run_directory / "replay_receipt.json")
    classification = (
        "GENERIC_ANCHORED_RECOVERY_CONFIRMED"
        if anchored_readiness.status in {"PASS", "CONDITIONAL_PASS"}
        and selected["fresh_base_reload_verified"] is True
        and replay["status"] == "PASSED"
        else "GENERIC_ANCHORED_RECOVERY_FAILED"
    )
    decision = {
        "schema_version": "inheritbench.bounded-multistart-decision.v0.1",
        "classification": classification,
        "metric_crosswalk_status": "METRIC_IDENTITY_RESOLVED",
        "fresh_final_surface_status": "FRESH_FINAL_SURFACES_FROZEN",
        "multistart_training_status": "COMPLETED",
        "selected_candidate_status": "SELECTED_CANDIDATE_FROZEN",
        "selected_candidate_index": selected["candidate_index"],
        "selected_checkpoint_id": selected["selected_checkpoint_id"],
        "selected_adapter_sha256": selected["exported_adapter_sha256"],
        "readiness": anchored_readiness.status,
        "readiness_reason_codes": anchored_readiness.reason_codes,
        "readiness_contract_changed": False,
        "supervision_changed": False,
        "schedule_changed": False,
        "final_surfaces_frozen_before_training": True,
        "candidate_selection_used_recovery_validation_only": True,
        "final_evaluation_exactly_once": True,
        "fresh_base_reload_verified": selected["fresh_base_reload_verified"],
        "replay_verified": replay["status"] == "PASSED",
        "live_generic_teacher_generation_proven": False,
    }
    decision["content_sha256"] = content_sha256(decision)
    _write_or_verify_json(run_directory / "decision.json", decision)
    historical = build_historical_comparison(run_directory)
    _write_evidence_manifest(run_directory)
    _write_web_bundle(
        run_directory,
        decision=decision,
        comparison=comparison,
        historical=historical,
        compute=compute,
    )
    write_repaired_execution_report(run_directory)
    return run_directory / "decision.json"


def write_repaired_execution_report(run_directory: Path) -> Path:
    """Consolidate repaired execution-only evidence without changing readiness."""

    ranking = _json(run_directory / "multistart_candidate_ranking.json")
    resume = _json(run_directory / "candidate_resume_decisions.json")
    resume_by_index = {int(item["candidate_index"]): item for item in resume["candidates"]}
    candidates: list[dict[str, Any]] = []
    for row in ranking["candidates"]:
        index = int(row["candidate_index"])
        directory = _candidate_root(run_directory) / f"candidate-{index}"
        validation = _json(directory / "validation_summary.json")
        telemetry = _json(directory / "numerical_telemetry.json")["telemetry"]
        pre = [float(item["pre_clip_gradient_norm"]) for item in telemetry]
        post = [float(item["post_clip_gradient_norm"]) for item in telemetry]
        candidates.append(
            {
                **row,
                "restart_or_resume": resume_by_index[index]["decision"],
                "starting_optimizer_step": resume_by_index[index]["starting_optimizer_step"],
                "validation_exact_full_contract": validation["atomic_summary"][
                    "exact_full_contract"
                ],
                "pre_clip_gradient_norm_range": [min(pre), max(pre)],
                "post_clip_gradient_norm_range": [min(post), max(post)],
                "telemetry_steps": len(telemetry),
            }
        )
    comparison = _json(run_directory / "final_comparison.json")
    decision = _json(run_directory / "decision.json")
    selected = _json(run_directory / "selected_candidate_receipt.json")
    payload = {
        "schema_version": "inheritbench.repaired-multistart-execution-report.v0.1",
        "repair_lineage_sha256": _json(run_directory / "guard_repair_lineage.json")[
            "content_sha256"
        ],
        "parent_canonical_plan_sha256": _json(run_directory / "canonical_plan.json")[
            "canonical_multistart_plan_sha256"
        ],
        "guard_repair_preflight": _json(run_directory / "guard_repair_preflight.json")["status"],
        "candidates": candidates,
        "selected_candidate": selected,
        "direct_final": comparison["direct"],
        "anchored_final": comparison["anchored"],
        "anchored_minus_direct": comparison["anchored_minus_direct"],
        "decision": decision,
        "sealed_surface_invocations": {
            "direct": 1,
            "anchored": 1,
            "rejected_candidates": 0,
        },
        "scientific_protocol_changed": False,
        "live_generic_teacher_generation_proven": False,
    }
    payload["content_sha256"] = content_sha256(payload)
    path = run_directory / "repair_execution_report.json"
    _write_or_verify_json(path, payload)
    return path


def replay_multistart_result(run_directory: Path) -> Path:
    plan = verify_multistart_plan(run_directory)
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    selected = _json(run_directory / "selected_candidate_receipt.json")
    adapter = _json(run_directory / "adapter_reference.json")
    if (
        sha256_file(run_directory / "successor/adapter_model.safetensors")
        != adapter["adapter_sha256"]
    ):
        raise ValueError("selected adapter payload hash mismatch during replay")
    direct_records = _final_records(run_directory / "direct_final_evaluation")
    anchored_records = _final_records(run_directory / "anchored_final_evaluation")
    stored_direct = _json(run_directory / "direct_final_evaluation/evaluation_summary.json")
    stored_anchored = _json(run_directory / "anchored_final_evaluation/evaluation_summary.json")
    replayed_direct = _summaries_from_records(direct_records)
    replayed_anchored = _summaries_from_records(anchored_records)
    if replayed_direct != stored_direct:
        raise ValueError("direct final evaluation replay mismatch")
    if replayed_anchored != stored_anchored:
        raise ValueError("anchored final evaluation replay mismatch")
    reference_summary = _json(REFERENCE_ANCHORED_RUN / "evaluation_summary.json")
    supervision = SupervisionAccounting.model_validate(
        _json(REFERENCE_ANCHORED_RUN / "stages/09-supervision_frozen/stage.json")["payload"][
            "supervision"
        ]["accounting"],
        strict=True,
    )
    replayed_readiness = derive_readiness(
        run_id=plan["canonical_multistart_plan_id"],
        rules=pack.readiness_rules,
        source_gate=SurfaceSummary.model_validate(reference_summary["source_gate"], strict=True),
        target_baseline=SurfaceSummary.model_validate(
            reference_summary["target_baseline"], strict=True
        ),
        confirmatory=SurfaceSummary.model_validate(
            replayed_anchored["generic_summary"]["confirmatory"], strict=True
        ),
        adversarial=SurfaceSummary.model_validate(
            replayed_anchored["generic_summary"]["adversarial"], strict=True
        ),
        supervision=supervision,
        selected_checkpoint_id=str(selected["selected_checkpoint_id"]),
        adapter_sha256=str(adapter["adapter_sha256"]),
    )
    stored_readiness = _json(run_directory / "readiness_report.json")
    if replayed_readiness.model_dump(mode="json") != stored_readiness:
        raise ValueError("bounded multi-start readiness replay mismatch")
    verified_names = [
        "canonical_plan.json",
        "multistart_candidate_ranking.json",
        "selected_candidate_receipt.json",
        "final_comparison.json",
        "readiness_report.json",
        "stability_report.json",
        "adapter_reference.json",
    ]
    verified = {
        name: sha256_file(run_directory / name)
        for name in verified_names
        if (run_directory / name).is_file()
    }
    manifest = {
        "schema_version": "inheritbench.multistart-replay-manifest.v0.1",
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "operation": (
            "model-free atomic metric, aggregate, readiness, selection, and adapter replay"
        ),
        "verified_files": verified,
    }
    manifest["content_sha256"] = content_sha256(manifest)
    receipt = {
        "schema_version": "inheritbench.multistart-replay-receipt.v0.1",
        "status": "PASSED",
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "manifest_sha256": manifest["content_sha256"],
        "readiness_sha256": replayed_readiness.content_sha256,
        "adapter_sha256": adapter["adapter_sha256"],
        "direct_record_count": sum(len(value) for value in direct_records.values()),
        "anchored_record_count": sum(len(value) for value in anchored_records.values()),
    }
    receipt["content_sha256"] = content_sha256(receipt)
    _write_or_verify_json(run_directory / "replay_manifest.json", manifest)
    _write_or_verify_json(run_directory / "replay_receipt.json", receipt)
    return run_directory / "replay_receipt.json"


def _replay_blocked_multistart(run_directory: Path) -> dict[str, Any]:
    plan = verify_multistart_plan(run_directory)
    ranking = _json(run_directory / "multistart_candidate_ranking.json")
    if ranking["status"] != "NO_SAFETY_ELIGIBLE_CANDIDATE":
        raise ValueError("blocked replay requires a terminal no-candidate ranking")
    for index in range(EXPECTED_CANDIDATES):
        _verify_candidate_terminal(_candidate_root(run_directory) / f"candidate-{index}", plan)
    if any(
        (run_directory / name).exists()
        for name in ("direct_final_evaluation", "anchored_final_evaluation")
    ):
        raise ValueError("blocked multi-start replay found prohibited final evaluation")
    manifest = {
        "schema_version": "inheritbench.multistart-replay-manifest.v0.1",
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "operation": (
            "model-free protocol, candidate-terminal-state, ranking, holdout-seal, "
            "and no-final-evaluation replay"
        ),
        "candidate_terminal_statuses": {
            str(index): _json(
                _candidate_root(run_directory) / f"candidate-{index}/training_trajectory.json"
            )["status"]
            for index in range(EXPECTED_CANDIDATES)
        },
        "ranking_sha256": ranking["content_sha256"],
        "final_surface_manifest_sha256": plan["final_surfaces"]["manifest_sha256"],
        "final_evaluation_calls": 0,
    }
    manifest["content_sha256"] = content_sha256(manifest)
    receipt = {
        "schema_version": "inheritbench.multistart-replay-receipt.v0.1",
        "status": "PASSED",
        "canonical_multistart_plan_id": plan["canonical_multistart_plan_id"],
        "manifest_sha256": manifest["content_sha256"],
        "readiness_sha256": None,
        "adapter_sha256": None,
        "candidate_terminal_count": EXPECTED_CANDIDATES,
        "final_evaluation_calls": 0,
    }
    receipt["content_sha256"] = content_sha256(receipt)
    _write_or_verify_json(run_directory / "replay_manifest.json", manifest)
    _write_or_verify_json(run_directory / "replay_receipt.json", receipt)
    return receipt


def build_historical_comparison(run_directory: Path) -> dict[str, Any]:
    anchored_final = _json(run_directory / "anchored_final_evaluation/evaluation_summary.json")
    old_generic = _json(REFERENCE_ANCHORED_RUN / "strict_metric_decomposition.json")
    crosswalk = _json(CROSSWALK_PATH)
    historical_counts = crosswalk["atomic_results"]["historical_phase3b_anchored"]
    comparison = {
        "schema_version": "inheritbench.multistart-historical-comparison.v0.1",
        "status": "HISTORICAL_BEHAVIORAL_PARITY_NOT_CONFIRMED",
        "primary_surface": "opsroute-final-surfaces-v0.3",
        "historical_surfaces_are_secondary": True,
        "metric_crosswalk_sha256": crosswalk["content_sha256"],
        "selected_candidate_v0.3": anchored_final["atomic_summary"],
        "previous_generic_anchored_old_surfaces": old_generic,
        "historical_phase3b_old_surfaces": historical_counts,
        "cross_surface_scores_not_treated_as_direct_parity": True,
        "operational_semantic_and_full_contract_kept_separate": True,
    }
    comparison["content_sha256"] = content_sha256(comparison)
    _write_or_verify_json(run_directory / "historical_comparison_report.json", comparison)
    return comparison


def _evaluate_adapter_once(
    output: Path,
    *,
    role: str,
    adapter_directory: Path,
    adapter: Any,
    config: ModelConfig,
    pack: LoadedCapabilityPack,
    inputs: dict[str, list[CapabilityInputRecord]],
    oracles: dict[str, list[CapabilityOracleRecord]],
    device: str,
    seed: int,
    surface_manifest_sha256: str,
    selected_candidate_sha256: str | None,
) -> None:
    summary_path = output / "evaluation_summary.json"
    if summary_path.exists():
        stored = _json(summary_path)
        if stored != _summaries_from_records(_final_records(output)):
            raise ValueError(f"stored final evaluation differs during idempotent read: {role}")
        return
    output.mkdir(parents=True, exist_ok=False)
    _write_or_verify_json(
        output / "attempt_started.json",
        {
            "schema_version": "inheritbench.final-evaluation-attempt.v0.1",
            "role": role,
            "surface_manifest_sha256": surface_manifest_sha256,
            "selected_candidate_sha256": selected_candidate_sha256,
            "adapter_sha256": sha256_file(adapter_directory / "adapter_model.safetensors"),
            "exactly_once_logical_attempt": True,
            "started_after_selected_candidate_frozen": selected_candidate_sha256 is not None
            or role == "corrected_direct_baseline",
        },
    )
    for surface in ("confirmatory", "adversarial"):
        identity, generations = adapter.generate(
            config,
            inputs[surface],
            device=device,
            maximum_new_tokens=pack.config.prompt.maximum_new_tokens,
            seed=seed,
            adapter_directory=adapter_directory,
        )
        records = evaluate_generations(
            pack=pack,
            surface=f"final_{surface}_v0.3",
            system_role="target_selected",
            checkpoint_id=None,
            model=identity,
            inputs=inputs[surface],
            oracles=oracles[surface],
            generations=generations,
        )
        _write_or_verify_json(
            output / f"{surface}.generation.json",
            {
                "model": identity.model_dump(mode="json"),
                "generations": [item.model_dump(mode="json") for item in generations],
            },
        )
        _write_or_verify_jsonl(
            output / f"{surface}.atomic-results.jsonl",
            [item.model_dump(mode="json") for item in records],
        )
    summaries = _summaries_from_records(_final_records(output))
    _write_or_verify_json(summary_path, summaries)
    _write_or_verify_json(
        output / "attempt_completed.json",
        {
            "schema_version": "inheritbench.final-evaluation-completion.v0.1",
            "role": role,
            "surface_manifest_sha256": surface_manifest_sha256,
            "confirmatory_records": 64,
            "adversarial_records": 32,
            "all_terminal": True,
            "logical_attempts": 1,
        },
    )


def _summaries_from_records(
    records: dict[str, list[EvaluationRecord]],
) -> dict[str, Any]:
    generic = {
        surface: summarize(f"final_{surface}_v0.3", values).model_dump(mode="json")
        for surface, values in records.items()
    }
    atomic = {
        surface: _atomic_summary(f"final_{surface}_v0.3", values)
        for surface, values in records.items()
    }
    return {
        "schema_version": "inheritbench.multistart-final-evaluation-summary.v0.1",
        "generic_summary": generic,
        "atomic_summary": atomic,
    }


def _final_records(output: Path) -> dict[str, list[EvaluationRecord]]:
    return {
        surface: [
            EvaluationRecord.model_validate(item, strict=True)
            for item in _read_jsonl(output / f"{surface}.atomic-results.jsonl")
        ]
        for surface in ("confirmatory", "adversarial")
    }


def _atomic_summary(surface: str, records: list[EvaluationRecord]) -> dict[str, Any]:
    field_names = sorted(
        {name for record in records for name in record.evaluation["field_correctness"]}
    )
    field_counts = {
        name: sum(
            bool(record.evaluation["field_correctness"].get(name, False)) for record in records
        )
        for name in field_names
    }
    operational_by_record = {
        record.generation.record_id: all(
            bool(record.evaluation["field_correctness"].get(name, False))
            for name in OPERATIONAL_FIELDS
        )
        for record in records
    }
    group_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    blocker_codes: Counter[str] = Counter()
    blocker_cases: dict[str, list[str]] = {}
    for record in records:
        group = str(record.evaluation["coverage"].get("group", "all"))
        group_counts[group][0] += int(operational_by_record[record.generation.record_id])
        group_counts[group][1] += 1
        codes = [
            str(item["code"])
            for item in record.evaluation["safety_findings"]
            if item["severity"] == "blocker"
        ]
        if codes:
            blocker_cases[record.generation.record_id] = codes
            blocker_codes.update(codes)
    group_operational = {
        group: {
            "correct": counts[0],
            "total": counts[1],
            "rate": counts[0] / counts[1],
        }
        for group, counts in sorted(group_counts.items())
    }
    total = len(records)
    operational = sum(operational_by_record.values())
    mean_declared = (
        sum(sum(record.evaluation["field_correctness"].values()) for record in records)
        / (total * len(field_names))
        if total and field_names
        else 0.0
    )
    return {
        "surface": surface,
        "records": total,
        "terminal": sum(record.generation.status in {"COMPLETED", "FAILED"} for record in records),
        "operational_semantic_fields": list(OPERATIONAL_FIELDS),
        "operational_semantic_correct": operational,
        "operational_semantic_rate": operational / total if total else 0.0,
        "field_correct": field_counts,
        "policy_code_correct": field_counts.get("policy_code", 0),
        "exact_full_contract": sum(
            bool(record.evaluation["structural_exact"]) for record in records
        ),
        "historical_strict_valid": sum(
            bool(record.evaluation["historical_strict_valid"]) for record in records
        ),
        "vocabulary_conformant": sum(
            bool(record.evaluation["vocabulary_conformant"]) for record in records
        ),
        "cross_field_conformant": sum(
            bool(record.evaluation["cross_field_conformant"]) for record in records
        ),
        "mean_declared_field_correctness": mean_declared,
        "group_operational": group_operational,
        "minimum_group_operational_semantic_rate": min(
            (float(item["rate"]) for item in group_operational.values()),
            default=0.0,
        ),
        "blocker_safety_findings": sum(blocker_codes.values()),
        "blocker_codes": dict(sorted(blocker_codes.items())),
        "blocker_cases": blocker_cases,
        "parser_classifications": dict(
            sorted(
                Counter(
                    str(record.evaluation["parser_classification"]) for record in records
                ).items()
            )
        ),
    }


def _candidate_rank(row: dict[str, Any]) -> tuple[float, ...]:
    validation_loss = row["validation_loss"]
    selected_step = row["selected_optimizer_step"]
    return (
        float(bool(row["safety_eligible"])),
        float(row["validation_operational_semantic_correct"]),
        float(row["validation_minimum_group_operational_semantic_rate"]),
        float(row["validation_historical_strict_valid"]),
        float(row["validation_mean_declared_field_correctness"]),
        -float(validation_loss) if validation_loss is not None else -math.inf,
        -float(selected_step) if selected_step is not None else -math.inf,
        -float(row["candidate_index"]),
    )


def _stability_report(
    rows: list[dict[str, Any]],
    predictions: dict[int, dict[str, str]],
) -> dict[str, Any]:
    validated = [
        item for item in rows if item["validation_operational_semantic_correct"] is not None
    ]
    scores = [float(item["validation_operational_semantic_correct"]) for item in validated]
    group_floors = [
        float(item["validation_minimum_group_operational_semantic_rate"]) for item in validated
    ]
    pairwise = []
    for left, right in combinations(sorted(predictions), 2):
        ids = sorted(set(predictions[left]) & set(predictions[right]))
        disagreement = sum(
            predictions[left][record_id] != predictions[right][record_id] for record_id in ids
        )
        pairwise.append(
            {
                "left_candidate_index": left,
                "right_candidate_index": right,
                "records_compared": len(ids),
                "prediction_disagreements": disagreement,
                "disagreement_rate": disagreement / len(ids) if ids else 0.0,
            }
        )
    payload = {
        "schema_version": "inheritbench.multistart-stability.v0.1",
        "candidate_count": len(rows),
        "validation_completed_candidates": len(validated),
        "metric": "validation_operational_semantic_correct",
        "mean": statistics.mean(scores) if scores else None,
        "minimum": min(scores) if scores else None,
        "maximum": max(scores) if scores else None,
        "population_standard_deviation": (statistics.pstdev(scores) if scores else None),
        "weakest_group_mean": statistics.mean(group_floors) if group_floors else None,
        "weakest_group_population_variance": (
            statistics.pvariance(group_floors) if group_floors else None
        ),
        "safety_eligible_candidates": [
            item["candidate_index"] for item in rows if item["safety_eligible"]
        ],
        "pairwise_prediction_disagreement": pairwise,
        "interpretation": (
            "All four candidate trajectories terminated under the frozen numerical "
            "instability guard before validation, demonstrating strong initialization "
            "sensitivity but preventing outcome-score stability estimation."
            if not validated
            else (
                "A bounded four-seed experiment provides direct evidence about LoRA "
                "initialization sensitivity under this fixed protocol; it is not a "
                "statistically complete seed study."
            )
        ),
    }
    payload["content_sha256"] = content_sha256(payload)
    return payload


def _write_ranking_markdown(path: Path, ranking: dict[str, Any]) -> None:
    lines = [
        "# Bounded Multi-Start Candidate Ranking",
        "",
        "Selection used recovery validation only. Final v0.3 inputs and oracles were unavailable.",
        "",
        "| Candidate | Seed | Eligible | Operational | Weakest group | Strict | Loss | Step |",
        "|---:|---:|:---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranking["candidates"]:
        loss = "n/a" if row["validation_loss"] is None else f"{row['validation_loss']:.10f}"
        step = (
            "n/a" if row["selected_optimizer_step"] is None else str(row["selected_optimizer_step"])
        )
        operational = (
            "n/a"
            if row["validation_operational_semantic_correct"] is None
            else f"{row['validation_operational_semantic_correct']}/32"
        )
        weakest = (
            "n/a"
            if row["validation_minimum_group_operational_semantic_rate"] is None
            else f"{row['validation_minimum_group_operational_semantic_rate']:.4f}"
        )
        strict = (
            "n/a"
            if row["validation_historical_strict_valid"] is None
            else f"{row['validation_historical_strict_valid']}/32"
        )
        prefix = (
            "| {candidate_index} | {initialization_seed} | {safety_eligible} | "
            "{operational} | {weakest} | {strict} | "
        ).format(**row, operational=operational, weakest=weakest, strict=strict)
        lines.append(f"{prefix}{loss} | {step} |")
    lines.extend(
        [
            "",
            f"Status: `{ranking['status']}`",
            f"Selected candidate: `{ranking['selected_candidate_index']}`",
            f"Selected checkpoint: `{ranking['selected_checkpoint_id']}`",
            "",
        ]
    )
    payload = "\n".join(lines).encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("persisted ranking Markdown differs")
        return
    write_atomic_file(path, payload)


def _verify_candidate_preflights(run_directory: Path) -> None:
    plans = []
    initialization_hashes = set()
    seeds = set()
    for index in range(EXPECTED_CANDIDATES):
        directory = _candidate_root(run_directory) / f"candidate-{index}"
        preflight = _json(directory / "parity_preflight.json")
        allowed_status = (
            "MULTISTART_CANDIDATE_REPAIR_PREFLIGHT_PASS"
            if (run_directory / "guard_repair_lineage.json").is_file()
            else "MULTISTART_CANDIDATE_PREFLIGHT_PASS"
        )
        if preflight["status"] != allowed_status:
            raise ValueError(f"candidate {index} preflight did not pass")
        if preflight["final_surface_inputs_or_oracles_accessed"]:
            raise ValueError(f"candidate {index} accessed final-surface evidence")
        plans.append(_json(directory / "plan_projection.json"))
        initialization_hashes.add(preflight["initial_adapter_sha256"])
        seeds.add(preflight["initialization_seed"])
    if len(initialization_hashes) != EXPECTED_CANDIDATES:
        raise ValueError("candidate initial adapters are not unique")
    if len(seeds) != EXPECTED_CANDIDATES:
        raise ValueError("candidate initialization seeds are not unique")
    invariants = {item["candidate_invariant_sha256"] for item in plans}
    if len(invariants) != 1:
        raise ValueError("candidate training invariants differ")


def _finalize_numerically_failed_candidate(
    candidate_directory: Path,
    *,
    index: int,
    seed: int,
    error: str,
) -> None:
    preflight = _json(candidate_directory / "parity_preflight.json")
    partial = _json(candidate_directory / "partial_checkpoint_evidence.json")
    progress = _failed_candidate_progress(partial)
    _write_or_verify_json(
        candidate_directory / "training_trajectory.json",
        {
            "schema_version": "inheritbench.multistart-training-trajectory.v0.1",
            "status": "FAILED",
            "candidate_index": index,
            "training_result": None,
            "failure_code": "NUMERICAL_INSTABILITY",
            "error": error,
            "initialization_seed": seed,
            "initial_adapter_sha256": preflight["initial_adapter_sha256"],
            "scientific_settings_changed": False,
            "retry_performed": False,
            "minimum_evidenced_optimizer_steps": progress["optimizer_steps"],
            "minimum_evidenced_processed_tokens": progress["processed_tokens"],
            "partial_checkpoint_count": progress["checkpoint_count"],
        },
    )
    empty_atomic = {
        "surface": "recovery_validation",
        "records": 0,
        "terminal": 0,
        "operational_semantic_fields": list(OPERATIONAL_FIELDS),
        "operational_semantic_correct": 0,
        "operational_semantic_rate": 0.0,
        "field_correct": {},
        "policy_code_correct": 0,
        "exact_full_contract": 0,
        "historical_strict_valid": 0,
        "vocabulary_conformant": 0,
        "cross_field_conformant": 0,
        "mean_declared_field_correctness": 0.0,
        "group_operational": {},
        "minimum_group_operational_semantic_rate": 0.0,
        "blocker_safety_findings": 0,
        "blocker_codes": {},
        "blocker_cases": {},
        "parser_classifications": {},
    }
    _write_or_verify_json(
        candidate_directory / "checkpoint_manifest.json",
        {
            "checkpoints": partial["checkpoints"],
            "decision": {
                "status": "TRAINING_FAILED",
                "failure_code": "NUMERICAL_INSTABILITY",
            },
            "checkpoint_evaluations": {},
            "partial_checkpoints_not_eligible_for_selection": True,
        },
    )
    _write_or_verify_jsonl(candidate_directory / "validation_atomic_results.jsonl", [])
    _write_or_verify_json(
        candidate_directory / "validation_summary.json",
        {
            "checkpoint_decision": {
                "status": "TRAINING_FAILED",
                "failure_code": "NUMERICAL_INSTABILITY",
            },
            "selected_score": None,
            "atomic_summary": empty_atomic,
        },
    )
    _write_or_verify_json(
        candidate_directory / "adapter_reference.json",
        {
            "candidate_index": index,
            "checkpoint_id": None,
            "adapter_directory": None,
            "adapter_sha256": None,
        },
    )
    _write_or_verify_json(
        candidate_directory / "compute_accounting.json",
        {
            "candidate_index": index,
            "processed_tokens": progress["processed_tokens"],
            "optimizer_steps": progress["optimizer_steps"],
            "duration_seconds": 0.0,
            "validation_model_passes": 0,
            "training_model_loaded_fresh": True,
            "final_surface_generation_calls": 0,
            "failure_code": "NUMERICAL_INSTABILITY",
            "partial_checkpoint_count": progress["checkpoint_count"],
            "progress_is_lower_bound": True,
        },
    )


def _verify_candidate_terminal(
    candidate_directory: Path,
    plan: dict[str, Any],
) -> None:
    document = _json(candidate_directory / "training_trajectory.json")
    preflight = _json(candidate_directory / "parity_preflight.json")
    if preflight["schedule_sha256"] != plan["schedule"]["content_sha256"]:
        raise ValueError("candidate schedule binding mismatch")
    if preflight["supervision_sha256"] != plan["supervision"]["records_sha256"]:
        raise ValueError("candidate supervision binding mismatch")
    if document["status"] == "FAILED":
        if document["failure_code"] != "NUMERICAL_INSTABILITY":
            raise ValueError("unexpected candidate training failure")
        if document["initialization_seed"] != preflight["initialization_seed"]:
            raise ValueError("failed candidate seed mismatch")
        if document["initial_adapter_sha256"] != preflight["initial_adapter_sha256"]:
            raise ValueError("failed candidate initialization mismatch")
        partial = _json(candidate_directory / "partial_checkpoint_evidence.json")
        allowed_steps = {56, 112, 168}
        if any(item["optimizer_step"] not in allowed_steps for item in partial["checkpoints"]):
            raise ValueError("failed candidate persisted an undeclared checkpoint")
        return
    result = TrainingResult.model_validate(document["training_result"], strict=True)
    if result.status != "COMPLETED":
        raise ValueError("candidate training is not completed")
    if result.processed_tokens != 272568 or result.optimizer_steps_completed != 168:
        raise ValueError("candidate training budget mismatch")
    if [item.optimizer_step for item in result.checkpoints] != [56, 112, 168]:
        raise ValueError("candidate checkpoint cadence mismatch")
    if result.initial_adapter_sha256 != preflight["initial_adapter_sha256"]:
        raise ValueError("candidate initialization hash mismatch")
    if result.seed != preflight["initialization_seed"]:
        raise ValueError("candidate initialization seed mismatch")
    validation = _json(candidate_directory / "validation_summary.json")
    if validation["checkpoint_decision"]["status"] != "SELECTED":
        raise ValueError("candidate lacks a safety-eligible checkpoint")
    if not (candidate_directory / "validation_atomic_results.jsonl").is_file():
        raise ValueError("candidate validation atomic evidence is missing")


def _write_partial_checkpoint_evidence(candidate_directory: Path) -> None:
    checkpoints = []
    for directory in sorted((candidate_directory / "checkpoints").glob("*-step-*")):
        if not directory.is_dir():
            continue
        step = int(directory.name.rsplit("-step-", 1)[1])
        state_path = directory / "trainer_state.pt"
        adapter_path = directory / "adapter_model.safetensors"
        if not state_path.is_file() or not adapter_path.is_file():
            raise ValueError(f"incomplete partial candidate checkpoint: {directory}")
        import torch

        state = torch.load(state_path, map_location="cpu", weights_only=False)
        checkpoints.append(
            {
                "checkpoint_id": directory.name,
                "optimizer_step": step,
                "schedule_cursor": int(state["schedule_cursor"]),
                "processed_tokens": int(state["processed_tokens"]),
                "adapter_sha256": sha256_file(adapter_path),
                "trainer_state_sha256": sha256_file(state_path),
            }
        )
    payload = {
        "schema_version": "inheritbench.multistart-partial-checkpoints.v0.1",
        "checkpoints": checkpoints,
        "not_eligible_for_selection": True,
    }
    payload["content_sha256"] = content_sha256(payload)
    _write_or_verify_json(candidate_directory / "partial_checkpoint_evidence.json", payload)


def _failed_candidate_progress(partial: dict[str, Any]) -> dict[str, int]:
    checkpoints = list(partial["checkpoints"])
    return {
        "optimizer_steps": max(
            (int(item["optimizer_step"]) for item in checkpoints),
            default=0,
        ),
        "processed_tokens": max(
            (int(item["processed_tokens"]) for item in checkpoints),
            default=0,
        ),
        "checkpoint_count": len(checkpoints),
    }


def _validate_frozen_training_inputs(
    records: list[CapabilityLabeledRecord],
    schedule: TrainingSchedule,
    profile: StrategyProfile,
) -> None:
    if len(records) != 224:
        raise ValueError("bounded multi-start supervision must contain 224 records")
    if sum(item.label_origin == "teacher" for item in records) != 214:
        raise ValueError("bounded multi-start teacher-label count mismatch")
    if sum(item.label_origin == "anchor" for item in records) != 10:
        raise ValueError("bounded multi-start anchor-label count mismatch")
    if (
        len(schedule.items) != 672
        or schedule.processed_tokens != 272568
        or schedule.optimizer_steps != 168
        or schedule.checkpoint_steps != [56, 112, 168]
    ):
        raise ValueError("bounded multi-start frozen schedule mismatch")
    if profile.training.target_processed_tokens != 272568:
        raise ValueError("bounded multi-start training profile budget mismatch")
    ids = {item.record_id for item in records}
    if {item.record_id for item in schedule.items} - ids:
        raise ValueError("bounded multi-start schedule contains unknown records")


def _supervision_records() -> list[CapabilityLabeledRecord]:
    values = _json(REFERENCE_ANCHORED_RUN / "stages/09-supervision_frozen/stage.json")["payload"][
        "supervision"
    ]["records"]
    return [CapabilityLabeledRecord.model_validate(item, strict=True) for item in values]


def _schedule() -> TrainingSchedule:
    return TrainingSchedule.model_validate(
        _json(REFERENCE_ANCHORED_RUN / "schedule_manifest.json"), strict=True
    )


def _anchored_profile(pack: LoadedCapabilityPack) -> StrategyProfile:
    matches = [
        item
        for item in pack.config.strategies
        if item.strategy_id == "anchored-behavioral-transfer-v0.1"
    ]
    if len(matches) != 1:
        raise ValueError("expected one anchored strategy profile")
    return matches[0]


def _model_binding(path: Path, registry_id: str) -> dict[str, Any]:
    config = load_model_config(path)
    return {
        "config_path": str(path.relative_to(REPOSITORY_ROOT)),
        "config_byte_sha256": sha256_file(path),
        "registry_id": registry_id,
        "model_id": config.model_id,
        "revision": config.revision,
        "tokenizer_id": config.tokenizer_id,
        "tokenizer_revision": config.tokenizer_revision,
        "attention_implementation": config.attention_implementation,
        "trust_remote_code": config.trust_remote_code,
        "lora_targets": config.intended_lora_target_modules,
    }


def _reference(path: Path, artifact_content_sha256: str) -> dict[str, Any]:
    return {
        "relative_path": str(path.relative_to(REPOSITORY_ROOT)),
        "bytes": path.stat().st_size,
        "byte_sha256": sha256_file(path),
        "content_sha256": artifact_content_sha256,
    }


def _metric_delta(anchored: dict[str, Any], direct: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    count_fields = (
        "operational_semantic_correct",
        "exact_full_contract",
        "historical_strict_valid",
        "vocabulary_conformant",
        "cross_field_conformant",
        "blocker_safety_findings",
    )
    for surface in ("confirmatory", "adversarial"):
        result[surface] = {
            field: anchored[surface][field] - direct[surface][field] for field in count_fields
        }
        result[surface]["field_correct"] = {
            field: anchored[surface]["field_correct"].get(field, 0)
            - direct[surface]["field_correct"].get(field, 0)
            for field in sorted(
                set(anchored[surface]["field_correct"]) | set(direct[surface]["field_correct"])
            )
        }
    return result


def _residuals(
    confirmatory: list[dict[str, Any]],
    adversarial: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for surface, records in (
        ("confirmatory", confirmatory),
        ("adversarial", adversarial),
    ):
        for record in records:
            evaluation = record["evaluation"]
            operational = all(
                evaluation["field_correctness"].get(field, False) for field in OPERATIONAL_FIELDS
            )
            if evaluation["structural_exact"] and operational and not evaluation["safety_findings"]:
                continue
            results.append(
                {
                    "surface": surface,
                    "record_id": record["generation"]["record_id"],
                    "group": evaluation["coverage"].get("group"),
                    "operational_semantic_correct": operational,
                    "structural_exact": evaluation["structural_exact"],
                    "historical_strict_valid": evaluation["historical_strict_valid"],
                    "field_correctness": evaluation["field_correctness"],
                    "safety_findings": evaluation["safety_findings"],
                    "parser_classification": evaluation["parser_classification"],
                }
            )
    return results


def _compute_accounting(run_directory: Path) -> dict[str, Any]:
    candidates = []
    for index in range(EXPECTED_CANDIDATES):
        candidate = _json(
            _candidate_root(run_directory) / f"candidate-{index}/compute_accounting.json"
        )
        partial = _json(
            _candidate_root(run_directory) / f"candidate-{index}/partial_checkpoint_evidence.json"
        )
        minimum_processed = max(
            (item["processed_tokens"] for item in partial["checkpoints"]),
            default=candidate["processed_tokens"],
        )
        candidates.append(
            {
                **candidate,
                "minimum_evidenced_processed_tokens": minimum_processed,
                "partial_checkpoint_count": len(partial["checkpoints"]),
            }
        )
    return {
        "schema_version": "inheritbench.multistart-compute.v0.1",
        "candidate_count": EXPECTED_CANDIDATES,
        "per_candidate_processed_tokens": 272568,
        "total_candidate_processed_tokens": sum(item["processed_tokens"] for item in candidates),
        "minimum_evidenced_candidate_processed_tokens": sum(
            item["minimum_evidenced_processed_tokens"] for item in candidates
        ),
        "per_candidate_optimizer_steps": 168,
        "total_optimizer_steps": sum(item["optimizer_steps"] for item in candidates),
        "candidate_training_duration_seconds": sum(item["duration_seconds"] for item in candidates),
        "candidate_compute": candidates,
        "direct_baseline_retrained": False,
        "final_direct_generation_records": 96,
        "final_anchored_generation_records": 96,
    }


def _write_evidence_manifest(run_directory: Path) -> None:
    names = [
        "canonical_plan.json",
        "protocol_amendment_reference.json",
        "metric_identity_crosswalk_reference.json",
        "seed_manifest.json",
        "fresh_surface_manifest.json",
        "final_surface_sealing_receipt.json",
        "candidate_ranking_policy.json",
        "multistart_candidate_ranking.json",
        "selected_candidate_receipt.json",
        "final_comparison.json",
        "readiness_report.json",
        "stability_report.json",
        "historical_comparison_report.json",
        "adapter_reference.json",
        "replay_manifest.json",
        "replay_receipt.json",
        "decision.json",
    ]
    files = {
        name: {
            "bytes": (run_directory / name).stat().st_size,
            "sha256": sha256_file(run_directory / name),
        }
        for name in names
        if (run_directory / name).is_file()
    }
    for role in ("direct_final_evaluation", "anchored_final_evaluation"):
        for path in sorted((run_directory / role).glob("*")):
            if path.is_file():
                relative = str(path.relative_to(run_directory))
                files[relative] = {
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
    _write_or_verify_json(
        run_directory / "evidence_manifest.json",
        {
            "schema_version": "inheritbench.multistart-evidence-manifest.v0.1",
            "files": files,
        },
    )


def _write_web_bundle(
    run_directory: Path,
    *,
    decision: dict[str, Any],
    comparison: dict[str, Any],
    historical: dict[str, Any],
    compute: dict[str, Any],
) -> None:
    plan = verify_multistart_plan(run_directory)
    ranking = _json(run_directory / "multistart_candidate_ranking.json")
    selected = _json(run_directory / "selected_candidate_receipt.json")
    payload = {
        "schema_version": "inheritbench.web-bundle.v0.4",
        "run_id": plan["canonical_multistart_plan_id"],
        "capability": {"id": "opsroute", "version": "0.1.0"},
        "strategy": "anchored-behavioral-transfer-v0.1",
        "protocol": {
            "type": "BOUNDED_MULTISTART_RECOVERY",
            "amendment_id": plan["amendment_id"],
            "amendment_sha256": plan["amendment_sha256"],
            "candidate_count": EXPECTED_CANDIDATES,
            "seed_manifest_sha256": plan["seed_manifest_sha256"],
            "final_surface_manifest_sha256": plan["final_surfaces"]["manifest_sha256"],
            "validation_only_ranking": True,
            "final_surfaces_frozen_before_training": True,
        },
        "candidates": ranking["candidates"],
        "selection": selected,
        "final_comparison": comparison,
        "readiness": _json(run_directory / "readiness_report.json"),
        "decision": decision,
        "stability": _json(run_directory / "stability_report.json"),
        "historical_comparison": historical,
        "residuals": _json(run_directory / "residual_failures.json"),
        "label_accounting": _json(run_directory / "label_accounting.json"),
        "compute_accounting": compute,
        "adapter": _json(run_directory / "adapter_reference.json"),
        "reload_verification": {
            "fresh_base_reload_verified": selected["fresh_base_reload_verified"],
            "adapter_sha256": selected["exported_adapter_sha256"],
        },
        "replay_verification": _json(run_directory / "replay_receipt.json"),
        "live_generic_teacher_generation_proven": False,
    }
    payload["content_sha256"] = content_sha256(payload)
    _write_or_verify_json(run_directory / "web_bundle.json", payload)


def _write_blocked_web_bundle(
    run_directory: Path,
    *,
    plan: dict[str, Any],
    ranking: dict[str, Any],
    decision: dict[str, Any],
    historical: dict[str, Any],
    compute: dict[str, Any],
    replay: dict[str, Any],
) -> None:
    payload = {
        "schema_version": "inheritbench.web-bundle.v0.4",
        "run_id": plan["canonical_multistart_plan_id"],
        "capability": {"id": "opsroute", "version": "0.1.0"},
        "strategy": "anchored-behavioral-transfer-v0.1",
        "protocol": {
            "type": "BOUNDED_MULTISTART_RECOVERY",
            "amendment_id": plan["amendment_id"],
            "amendment_sha256": plan["amendment_sha256"],
            "candidate_count": EXPECTED_CANDIDATES,
            "seed_manifest_sha256": plan["seed_manifest_sha256"],
            "final_surface_manifest_sha256": plan["final_surfaces"]["manifest_sha256"],
            "validation_only_ranking": True,
            "final_surfaces_frozen_before_training": True,
        },
        "candidates": ranking["candidates"],
        "selection": _json(run_directory / "selected_candidate_receipt.json"),
        "final_comparison": _json(run_directory / "final_comparison.json"),
        "readiness": _json(run_directory / "readiness_report.json"),
        "decision": decision,
        "stability": _json(run_directory / "stability_report.json"),
        "historical_comparison": historical,
        "residuals": _json(run_directory / "residual_failures.json"),
        "label_accounting": _json(run_directory / "label_accounting.json"),
        "compute_accounting": compute,
        "adapter": _json(run_directory / "adapter_reference.json"),
        "reload_verification": None,
        "replay_verification": replay,
        "live_generic_teacher_generation_proven": False,
    }
    payload["content_sha256"] = content_sha256(payload)
    _write_or_verify_json(run_directory / "web_bundle.json", payload)


def _raw_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _dirty_worktree_sha256() -> str:
    status = _git_value("status", "--porcelain")
    return hashlib.sha256(status.encode()).hexdigest()


def _read_models(path: Path, schema: Any) -> list[Any]:
    return [
        schema.model_validate_json(line, strict=True)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    values = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not all(isinstance(item, dict) for item in values):
        raise ValueError(f"expected JSON objects: {path}")
    return values


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value
